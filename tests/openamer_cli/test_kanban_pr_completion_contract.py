"""Completion contracts exercised against real isolated Kanban transactions."""
import json
import os

import pytest

from openamer_cli import kanban_db as kb
from openamer_cli import kanban_pr_acceptance as pr


@pytest.fixture
def board(tmp_path, monkeypatch):
    for key in tuple(os.environ):
        if key.startswith(('OPENAMER_KANBAN_', 'KANBAN_', 'TERMINAL_')):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('OPENAMER_HOME', str(tmp_path / 'home'))
    monkeypatch.setattr(kb, '_fire_kanban_lifecycle_hook', lambda *a, **k: None)
    monkeypatch.setattr(kb, '_cleanup_workspace', lambda *a, **k: None)
    monkeypatch.setattr(pr, '_api', lambda *a, **k: pytest.fail('Unexpected network request'))
    conn = kb.connect(tmp_path / 'kanban.db')
    parent = kb.create_task(conn, title='Contract parent', assignee='test',
                            workspace_kind='dir', workspace_path=str(tmp_path),
                            completion_contract='openamer/openamer')
    child = kb.create_task(conn, title='Dependent', assignee='test', parents=[parent],
                           workspace_kind='dir', workspace_path=str(tmp_path))
    yield conn, parent, child
    conn.close()


def test_missing_pr_cannot_complete_or_release_child(board):
    conn, parent, child = board
    before = kb.get_task(conn, parent).status
    assert kb.complete_task(conn, parent, summary='Unverified claim') is False
    assert kb.get_task(conn, parent).status == before
    assert kb.get_task(conn, child).status == 'todo'
    events = conn.execute("SELECT payload FROM task_events WHERE task_id=? AND kind='pr_acceptance'", (parent,)).fetchall()
    assert json.loads(events[-1][0])['classification'] == 'missing'


def test_local_contract_changed_during_preparation_is_not_bypassed(board, monkeypatch):
    conn, parent, child = board
    with kb.write_txn(conn):
        conn.execute('UPDATE tasks SET completion_contract=? WHERE id=?', ('local-only', parent))
    original = kb._merge_completion_prose_artifacts

    def changed_contract(*args, **kwargs):
        with kb.write_txn(conn):
            conn.execute('UPDATE tasks SET completion_contract=? WHERE id=?', ('openamer/openamer', parent))
        return original(*args, **kwargs)

    monkeypatch.setattr(kb, '_merge_completion_prose_artifacts', changed_contract)
    assert kb.complete_task(conn, parent) is False
    assert kb.get_task(conn, child).status == 'todo'


URL = 'https://github.com/openamer/openamer/pull/42'
SHA = 'a' * 40


def github(monkeypatch, conn, outcome='success', race=None):
    """Only GitHub transport is simulated; run the actual policy and store."""
    def api(endpoint, **kwargs):
        assert not conn.in_transaction, 'Network must be outside the writer transaction'
        if endpoint == 'graphql':
            return {'data': {'repository': {'pullRequest': {
                'headRefOid': SHA, 'baseRefName': 'main', 'state': 'OPEN',
                'baseRef': {'branchProtectionRule': {'requiredStatusChecks': [
                    {'context': 'tests', 'app': {'databaseId': 7}}]}}}}}}
        if '/rules/' in endpoint:
            return [[]]
        if '/check-runs?' in endpoint:
            if outcome == 'infra':
                raise OSError('Transport unavailable')
            runs = [] if outcome == 'missing' else [{
                'id': 1, 'name': 'tests', 'app': {'id': 7},
                'head_sha': 'b' * 40 if outcome == 'old-head' else SHA,
                'status': 'in_progress' if outcome == 'pending' else 'completed',
                'conclusion': 'failure' if outcome == 'failure' else 'success'}]
            return [{'total_count': len(runs), 'check_runs': runs}]
        if '/statuses?' in endpoint:
            return [[]]
        if '/pulls/' in endpoint:
            if race:
                race()
            return {'head': {'sha': 'b' * 40 if outcome == 'changed-head' else SHA},
                    'base': {'ref': 'other' if outcome == 'changed-base' else 'main'},
                    'state': 'open'}
        pytest.fail(f'Unexpected endpoint: {endpoint}')
    monkeypatch.setattr(pr, '_api', api)


def receipt(conn, parent):
    row = conn.execute("SELECT payload FROM task_events WHERE task_id=? AND kind='pr_acceptance' ORDER BY id DESC LIMIT 1", (parent,)).fetchone()
    return json.loads(row[0])


def test_successful_exact_head_completes_and_releases_child(board, monkeypatch):
    conn, parent, child = board
    github(monkeypatch, conn)
    run = kb.claim_task(conn, parent)
    assert run is not None
    assert kb.complete_task(conn, parent, expected_run_id=run.current_run_id,
                            metadata={'published_pr': URL}) is True
    assert kb.get_task(conn, parent).status == 'done'
    assert kb.get_task(conn, child).status == 'ready'
    assert receipt(conn, parent)['head_sha'] == SHA
    assert receipt(conn, parent)['ok'] is True
    assert kb.get_task(conn, parent).completion_contract == URL


@pytest.mark.parametrize(('outcome', 'classification'), [
    ('missing', 'missing'), ('pending', 'pending'), ('failure', 'failure'),
    ('infra', 'infra'), ('old-head', 'stale'), ('changed-head', 'stale'),
    ('changed-base', 'stale')])
def test_rejection_preserves_claim_run_failure_and_artifact(board, monkeypatch, tmp_path, outcome, classification):
    conn, parent, child = board
    github(monkeypatch, conn, outcome)
    run = kb.claim_task(conn, parent)
    artifact = tmp_path / 'deliverable.txt'
    artifact.write_text('preserve me', encoding='utf-8')
    with kb.write_txn(conn):
        conn.execute('UPDATE tasks SET consecutive_failures=1 WHERE id=?', (parent,))
    cleanup = []
    monkeypatch.setattr(kb, '_cleanup_workspace', lambda *a, **k: cleanup.append(True))
    assert kb.complete_task(conn, parent, expected_run_id=run.current_run_id,
                            metadata={'published_pr': URL, 'artifacts': [str(artifact)]}) is False
    current = kb.get_task(conn, parent)
    assert (current.status, current.current_run_id, current.claim_lock, current.consecutive_failures) == (
        'running', run.current_run_id, run.claim_lock, 1)
    assert kb.get_task(conn, child).status == 'todo'
    assert conn.execute('SELECT ended_at FROM task_runs WHERE id=?', (run.current_run_id,)).fetchone()[0] is None
    assert artifact.read_text(encoding='utf-8') == 'preserve me'
    assert not cleanup
    assert receipt(conn, parent)['classification'] == classification
    assert classification in current.last_failure_error


def test_local_only_remains_compatible(board):
    conn, parent, child = board
    with kb.write_txn(conn):
        conn.execute('UPDATE tasks SET completion_contract=? WHERE id=?', ('local-only', parent))
    assert kb.complete_task(conn, parent) is True
    assert kb.get_task(conn, child).status == 'ready'
    assert conn.execute("SELECT COUNT(*) FROM task_events WHERE task_id=? AND kind='pr_acceptance'", (parent,)).fetchone()[0] == 0


def test_wrong_repo_and_green_sibling_cannot_rebind(board, monkeypatch):
    conn, parent, child = board
    assert kb.complete_task(conn, parent, metadata={'published_pr': URL.replace('openamer/openamer', 'other/repo')}) is False
    github(monkeypatch, conn, 'failure')
    assert kb.complete_task(conn, parent, metadata={'published_pr': URL}) is False
    assert kb.get_task(conn, parent).completion_contract == URL
    monkeypatch.setattr(pr, '_api', lambda *a, **k: pytest.fail('Sibling must not be queried'))
    assert kb.complete_task(conn, parent, metadata={'published_pr': URL.replace('/42', '/43')}) is False
    assert kb.get_task(conn, child).status == 'todo'


@pytest.mark.parametrize('column,value', [('status', 'blocked'), ('current_run_id', None), ('completion_contract', 'local-only')])
def test_snapshot_race_rejects_without_terminal_write(board, monkeypatch, column, value):
    conn, parent, child = board
    run = kb.claim_task(conn, parent)

    def race():
        with kb.write_txn(conn):
            conn.execute(f'UPDATE tasks SET {column}=? WHERE id=?', (value, parent))

    github(monkeypatch, conn, race=race)
    assert kb.complete_task(conn, parent, expected_run_id=run.current_run_id,
                            metadata={'published_pr': URL}) is False
    assert kb.get_task(conn, parent).status != 'done'
    assert kb.get_task(conn, child).status == 'todo'
    assert conn.execute("SELECT COUNT(*) FROM task_events WHERE task_id=? AND kind='pr_acceptance'", (parent,)).fetchone()[0] == 0


@pytest.mark.parametrize('contract', ['local-only', 'openamer/openamer'])
def test_stale_worker_cannot_bind_or_complete(board, contract):
    conn, parent, child = board
    with kb.write_txn(conn):
        conn.execute('UPDATE tasks SET completion_contract=? WHERE id=?', (contract, parent))
    run = kb.claim_task(conn, parent)
    assert kb.complete_task(conn, parent, expected_run_id=run.current_run_id + 1,
                            metadata={'published_pr': URL}) is False
    assert kb.get_task(conn, parent).completion_contract == contract
    assert kb.get_task(conn, parent).claim_lock == run.claim_lock
    assert kb.get_task(conn, child).status == 'todo'

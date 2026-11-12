"""Acceptance-revision regression tests for the ACE completion journal.

The core acceptance-change paths are covered together with transaction-window,
stale-worker, restart, and event-ticket provenance regressions:

1. amend         — add/clear subgoals invalidate receipts from the old definition.
2. contract      — replacing the completion contract does the same.
3. pending       — a goal change between before_call and after_call never promotes
                   the delayed result to a verified receipt.
4. concurrency   — stale goal snapshots and tickets cannot complete newer state.

These tests exercise the real GoalManager + goal_completion APIs against a
real SQLite session DB in a temporary OPENAMER_HOME. No mocks.
"""
import json
import subprocess
import sys

import pytest

from openamer_cli.goals import GoalManager, GoalContract, save_goal
from tools.registry import ToolRegistry


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAMER_HOME', str(tmp_path / 'home'))
    from openamer_cli import goal_completion as ace
    manager = GoalManager('ace-test')
    manager.set('Produce a verified development artifact')
    registry = ToolRegistry()
    calls = []

    def terminal(args, **kw):
        calls.append(args)
        p = subprocess.run(args['command'], cwd=args.get('workdir'), shell=True,
                           capture_output=True, text=True, timeout=10)
        return json.dumps({'exit_code': p.returncode, 'output': p.stdout + p.stderr})

    registry.register(name='terminal', toolset='terminal', schema={}, handler=terminal)
    command = f'"{sys.executable}" -c "print(42)"'
    checks = [{'id': 'artifact', 'tool': 'terminal',
               'args': {'command': command, 'workdir': str(tmp_path)}}]
    ace.configure('ace-test', checks=checks)
    return ace, manager, registry, calls, checks


def run(registry, args):
    return json.loads(registry.dispatch('terminal', args, session_id='ace-test'))


# --------------------------------------------------------------------------- #
# 1. amend — a later goal amendment invalidates old receipts
# --------------------------------------------------------------------------- #
def test_amend_invalidates_old_receipts(setup):
    ace, manager, registry, calls, checks = setup
    # Gather a real receipt under the original definition.
    assert run(registry, checks[0]['args'])['exit_code'] == 0
    assert ace.read('ace-test')['receipts']['artifact']['revision'] == 0

    # Amend the goal: a new subgoal is added. The acceptance definition moves.
    manager.add_subgoal('Also produce a changelog entry')

    # The old receipt must not satisfy the amended goal.
    with pytest.raises((ValueError, RuntimeError)):
        manager.mark_done('old evidence still valid after amendment')

    data = ace.read('ace-test')
    assert data['outcome'] != 'done'
    # The journal revision moved forward and the old receipt was cleared.
    assert data['revision'] == 1
    assert 'artifact' not in data['receipts']
    assert ace.completion_error('ace-test') is not None

    # Re-running the check under the amended definition must produce a fresh
    # receipt at the new revision, and only then may the goal complete.
    assert run(registry, checks[0]['args'])['exit_code'] == 0
    assert ace.read('ace-test')['receipts']['artifact']['revision'] == data['revision']
    manager.mark_done('fresh evidence after amendment')
    assert GoalManager('ace-test').state.status == 'done'


# --------------------------------------------------------------------------- #
# 2. contract — a later contract change invalidates old receipts
# --------------------------------------------------------------------------- #
def test_contract_change_invalidates_old_receipts(setup):
    ace, manager, registry, calls, checks = setup
    assert run(registry, checks[0]['args'])['exit_code'] == 0
    assert ace.read('ace-test')['receipts']['artifact']['revision'] == 0

    # Replace the completion contract. The acceptance definition moves.
    manager.set_contract(GoalContract(
        verification='Create a new required artifact and verify its bytes'))

    with pytest.raises((ValueError, RuntimeError)):
        manager.mark_done('old evidence still valid after contract change')

    data = ace.read('ace-test')
    assert data['outcome'] != 'done'
    assert data['revision'] == 1
    assert 'artifact' not in data['receipts']
    assert ace.completion_error('ace-test') is not None

    assert run(registry, checks[0]['args'])['exit_code'] == 0
    assert ace.read('ace-test')['receipts']['artifact']['revision'] == data['revision']
    manager.mark_done('fresh evidence after contract change')
    assert GoalManager('ace-test').state.status == 'done'


def test_clear_subgoals_invalidates_receipts(setup):
    ace, manager, registry, calls, checks = setup
    manager.add_subgoal('Produce a changelog entry')
    assert run(registry, checks[0]['args'])['exit_code'] == 0
    before = ace.read('ace-test')
    assert before['receipts']['artifact']['revision'] == before['revision']

    assert manager.clear_subgoals() == 1
    after = ace.read('ace-test')
    assert after['revision'] == before['revision'] + 1
    assert not after['receipts']
    with pytest.raises((ValueError, RuntimeError)):
        manager.mark_done('receipt predates clearing the acceptance criteria')


# --------------------------------------------------------------------------- #
# 3. pending-amend — a goal change during an in-flight tool call
# --------------------------------------------------------------------------- #
def test_pending_amend_does_not_promote_or_crash(setup):
    ace, manager, registry, calls, checks = setup
    # Reserve a pending event without letting the result land.
    ticket = ace.before_call('ace-test', 'terminal', checks[0]['args'])
    assert ticket is not None and 'event_id' in ticket
    pending_id = ticket['event_id']
    before = ace.read('ace-test')
    assert before['revision'] == 0

    # The goal is amended while the call is still in flight.
    manager.add_subgoal('Also produce a changelog entry')
    after_amend = ace.read('ace-test')
    # The journal revision must have moved while the in-flight event keeps the
    # revision under which it started. That mismatch is what makes it stale.
    assert after_amend['revision'] > before['revision']
    pending = next(e for e in after_amend['events'] if e['id'] == pending_id)
    assert pending['revision'] == before['revision']
    assert pending['revision'] < after_amend['revision']

    # Land the delayed result. This must NOT raise an unhandled exception
    # and must NOT promote the stale pending event to a verified receipt.
    ace.after_call('ace-test', ticket, {'exit_code': 0, 'output': '42\n'})

    data = ace.read('ace-test')
    event = next(e for e in data['events'] if e['id'] == pending_id)
    assert event['status'] != 'verified', \
        'a pending result gathered before an amendment must not become a receipt'
    assert 'artifact' not in data['receipts'], \
        'a stale event may keep its original revision but must never issue a receipt'
    # The criterion is still unverified, so completion must still be refused.
    with pytest.raises((ValueError, RuntimeError)):
        manager.mark_done('stale pending result after amendment')

    # A fresh call under the amended definition produces a valid receipt.
    assert run(registry, checks[0]['args'])['exit_code'] == 0
    assert ace.read('ace-test')['receipts']['artifact']['revision'] == data['revision']
    manager.mark_done('fresh evidence after pending amendment')
    assert GoalManager('ace-test').state.status == 'done'


def test_pending_contract_change_does_not_promote_or_crash(setup):
    ace, manager, registry, calls, checks = setup
    ticket = ace.before_call('ace-test', 'terminal', checks[0]['args'])
    assert ticket is not None and 'event_id' in ticket
    pending_id = ticket['event_id']

    manager.set_contract(GoalContract(
        verification='Create a new required artifact and verify its bytes'))

    # Must not raise; must not promote.
    ace.after_call('ace-test', ticket, {'exit_code': 0, 'output': '42\n'})

    data = ace.read('ace-test')
    event = next(e for e in data['events'] if e['id'] == pending_id)
    assert event['status'] != 'verified'
    with pytest.raises((ValueError, RuntimeError)):
        manager.mark_done('stale pending result after contract change')


def test_pending_result_is_stale_during_goal_journal_update_window(setup):
    ace, manager, registry, calls, checks = setup
    ticket = ace.before_call('ace-test', 'terminal', checks[0]['args'])
    assert ticket is not None and 'event_id' in ticket

    # Reproduce the transaction boundary inside an amendment: the goal row has
    # the new acceptance revision, but the ACE journal bump has not committed.
    state = manager.state
    state.subgoals.append('Also produce a changelog entry')
    state.bump_acceptance()
    save_goal('ace-test', state)

    # The delayed old-revision result must close safely without issuing a
    # receipt, even in this narrow inter-transaction window.
    ace.after_call('ace-test', ticket, {'exit_code': 0, 'output': '42\n'})
    data = ace.read('ace-test')
    event = next(e for e in data['events'] if e['id'] == ticket['event_id'])
    assert event['status'] != 'verified'
    assert 'artifact' not in data['receipts']


def test_atomic_completion_rejects_stale_goal_snapshot(setup):
    ace, manager, registry, calls, checks = setup
    assert run(registry, checks[0]['args'])['exit_code'] == 0
    stale_manager = GoalManager('ace-test')

    # Simulate another agent committing an acceptance amendment after the
    # completing worker loaded its GoalState but before mark_done() acquires
    # the SQLite write lock.
    live = manager.state
    live.subgoals.append('Concurrent acceptance criterion')
    live.bump_acceptance()
    save_goal('ace-test', live)

    with pytest.raises(RuntimeError, match='Goal changed'):
        stale_manager.mark_done('stale worker attempted completion')
    assert GoalManager('ace-test').state.status != 'done'
    assert ace.read('ace-test')['outcome'] != 'done'


def test_old_ticket_cannot_complete_reconfigured_goal_event(setup):
    ace, manager, registry, calls, checks = setup
    old_ticket = ace.before_call('ace-test', 'terminal', checks[0]['args'])
    assert old_ticket is not None and old_ticket['event_id'] == 1

    # Reconfigure the same session with a new goal/check. Event ids restart at
    # one, so event_id alone is insufficient provenance for after_call().
    manager.set('Produce a replacement verified artifact')
    replacement_args = {
        'command': f'"{sys.executable}" -c "print(99)"',
        'workdir': checks[0]['args']['workdir'],
    }
    ace.configure('ace-test', checks=[{
        'id': 'replacement', 'tool': 'terminal', 'args': replacement_args,
    }])
    new_ticket = ace.before_call('ace-test', 'terminal', replacement_args)
    assert new_ticket is not None and new_ticket['event_id'] == 1

    # Landing the old result must not verify the replacement event/receipt.
    ace.after_call('ace-test', old_ticket, {'exit_code': 0, 'output': '42\n'})
    data = ace.read('ace-test')
    event = next(e for e in data['events'] if e['id'] == new_ticket['event_id'])
    assert event['status'] == 'pending'
    assert 'replacement' not in data['receipts']

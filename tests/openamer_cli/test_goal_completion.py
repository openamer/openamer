"""ACE contracts exercised through real registry dispatch and persistent SQLite."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from openamer_cli.goals import GoalManager
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


def test_real_verification_not_a_claim(setup):
    ace, manager, registry, calls, checks = setup
    with pytest.raises(ValueError, match='verification'):
        manager.mark_done('all tests pass')
    run(registry, checks[0]['args'])
    manager.mark_done('verified actual command output')
    assert GoalManager('ace-test').state.status == 'done'
    assert ace.read('ace-test')['outcome'] == 'done'
    from agent.goal_engine import GoalEngine
    records = GoalEngine().recent_outcomes()
    assert records[0]['success'] is True
    assert records[0]['metadata']['verification'][0]['id'] == 'artifact'


def test_interrupt_survives_new_process(setup):
    ace, manager, registry, calls, checks = setup
    ace.checkpoint('ace-test', progress='Implementation compiled', next_step='artifact')
    ace.before_call('ace-test', 'terminal', checks[0]['args'])
    script = ('from openamer_cli.goal_completion import read; import json; '
              'print(json.dumps(read("ace-test")))')
    p = subprocess.run([sys.executable, '-c', script], capture_output=True,
                       text=True, env=dict(os.environ), check=True)
    restored = json.loads(p.stdout)
    assert restored['checkpoint']['progress'] == 'Implementation compiled'
    assert restored['events'][-1]['status'] == 'pending'
    result = run(registry, checks[0]['args'])
    assert 'uncertain' in result['error']
    assert not calls


def test_broken_python_and_repeated_repairs_are_bounded(setup):
    ace, manager, registry, calls, checks = setup
    args = {'command': f'"{sys.executable}" -c "import ace_dependency_that_does_not_exist"'}
    assert run(registry, args)['exit_code'] != 0
    assert run(registry, args)['exit_code'] != 0
    denied = run(registry, args)
    assert 'repeat' in denied['error']
    assert len(calls) == 2
    assert ace.read('ace-test')['outcome'] != 'done'


def test_budget_persists_and_does_not_reset_on_resume(setup):
    ace, manager, registry, calls, checks = setup
    ace.configure('ace-test', checks=checks, max_calls=1)
    run(registry, {'command': f'"{sys.executable}" -c "raise SystemExit(1)"'})
    manager.pause('restart')
    with pytest.raises(ValueError, match='budget'):
        manager.resume()
    denied = run(registry, checks[0]['args'])
    assert 'budget' in denied['error']
    assert len(calls) == 1


def test_no_fabricated_receipt_from_background_start(setup):
    ace, manager, registry, calls, checks = setup
    registry.register(name='terminal', toolset='terminal', schema={},
                      handler=lambda *a, **k: json.dumps({'session_id': 'bg', 'status': 'running'}))
    run(registry, checks[0]['args'])
    with pytest.raises(ValueError, match='verification'):
        manager.mark_done('started the test')


def test_later_work_invalidates_previous_verification(setup):
    ace, manager, registry, calls, checks = setup
    run(registry, checks[0]['args'])
    run(registry, {'command': f'"{sys.executable}" -c "print(99)"'})
    with pytest.raises(ValueError, match='verification'):
        manager.mark_done('stale verification')
    run(registry, checks[0]['args'])
    manager.mark_done('fresh verification')


def test_missing_skill_and_provider_failure_are_not_success(setup):
    ace, manager, registry, calls, checks = setup
    registry.register(name='skill_view', toolset='skills', schema={},
                      handler=lambda *a, **k: '{"error":"Skill not found"}')
    registry.dispatch('skill_view', {'name': 'missing'}, session_id='ace-test')
    registry.register(name='provider_probe', toolset='test', schema={},
                      handler=lambda *a, **k: (_ for _ in ()).throw(ConnectionError('provider down')))
    registry.dispatch('provider_probe', {}, session_id='ace-test')
    assert [e['status'] for e in ace.read('ace-test')['events']] == ['failed', 'failed']
    run(registry, checks[0]['args'])
    manager.mark_done('fallback command verified')


def test_parallel_accounting_is_atomic(setup):
    ace, manager, registry, calls, checks = setup
    ace.configure('ace-test', checks=checks, max_calls=3)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: run(registry, {'command': f'"{sys.executable}" -c "print({n})"'}), range(8)))
    assert len(calls) == 3
    assert ace.read('ace-test')['calls_used'] == 3


def test_checkpoint_reanchors_without_changing_original_goal(setup):
    ace, manager, registry, calls, checks = setup
    ace.checkpoint('ace-test', progress='Repair environment', next_step='artifact')
    assert 'artifact' in manager.next_continuation_prompt()
    with pytest.raises(ValueError, match='criterion'):
        ace.checkpoint('ace-test', progress='Unrelated task', next_step='unrelated')
    assert GoalManager('ace-test').state.goal == 'Produce a verified development artifact'


@pytest.mark.parametrize('outcome', ['partial', 'blocked', 'failed'])
def test_distinct_outcomes_survive_restart(setup, outcome):
    ace, manager, registry, calls, checks = setup
    manager.report_outcome(outcome, 'Verification not yet complete')
    assert GoalManager('ace-test').state.status == 'paused'
    assert ace.read('ace-test')['outcome'] == outcome


def test_session_rotation_carries_guard_and_budget(setup):
    ace, manager, registry, calls, checks = setup
    from openamer_cli.goals import migrate_goal_to_session
    run(registry, checks[0]['args'])
    assert migrate_goal_to_session('ace-test', 'ace-child')
    assert ace.read('ace-child')['calls_used'] == 1
    GoalManager('ace-child').mark_done('resumed verified task')


def test_without_ace_legacy_dispatch_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAMER_HOME', str(tmp_path / 'home'))
    r = ToolRegistry()
    r.register(name='test', toolset='test', schema={}, handler=lambda *a, **k: 'ok')
    assert r.dispatch('test', {}, session_id='plain') == 'ok'


def test_judge_cannot_bypass_missing_evidence(setup, monkeypatch):
    ace, manager, registry, calls, checks = setup
    from openamer_cli import goals
    monkeypatch.setattr(goals, 'judge_goal', lambda *a, **kw: ('done', 'looks good', False, None, False))
    decision = manager.evaluate_after_turn('Done')
    assert decision['should_continue']
    assert decision['status'] == 'active'
    assert 'verification' in decision['reason']


@pytest.mark.parametrize('outcome', ['partial', 'blocked', 'failed'])
def test_judge_preserves_non_success_outcomes(setup, monkeypatch, outcome):
    ace, manager, registry, calls, checks = setup
    from openamer_cli import goals
    assert goals._parse_judge_response(json.dumps({'verdict': outcome, 'reason': 'obstacle'}))[0] == outcome
    monkeypatch.setattr(goals, 'judge_goal', lambda *a, **kw: (outcome, 'obstacle', False, None, False))
    decision = manager.evaluate_after_turn('Obstacle')
    assert not decision['should_continue']
    assert decision['verdict'] == outcome
    assert ace.read('ace-test')['outcome'] == outcome


def test_failed_reverification_revokes_previous_receipt(setup):
    ace, manager, registry, calls, checks = setup
    run(registry, checks[0]['args'])
    registry.register(name='terminal', toolset='terminal', schema={},
                      handler=lambda *a, **k: '{"exit_code":1,"output":"failed"}')
    run(registry, checks[0]['args'])
    with pytest.raises(ValueError, match='verification'):
        manager.mark_done('earlier result was successful')


def test_budget_stops_continuation_without_judge_call(setup, monkeypatch):
    ace, manager, registry, calls, checks = setup
    ace.configure('ace-test', checks=checks, max_calls=1)
    run(registry, {'command': f'"{sys.executable}" -c "print(0)"'})
    run(registry, checks[0]['args'])
    from openamer_cli import goals
    monkeypatch.setattr(goals, 'judge_goal', lambda *a, **k: pytest.fail('budget must stop before judge'))
    decision = manager.evaluate_after_turn('budget hit')
    assert decision['verdict'] == 'failed'
    assert decision['should_continue'] is False


def test_new_goal_and_clear_do_not_inherit_old_budget(setup):
    ace, manager, registry, calls, checks = setup
    ace.configure('ace-test', checks=checks, max_calls=1)
    run(registry, checks[0]['args'])
    manager.clear()
    assert ace.read('ace-test') is None
    manager.set('A new task')
    assert ace.read('ace-test') is None
    assert run(registry, checks[0]['args'])['exit_code'] == 0


def test_profile_switch_and_restart_use_same_database(tmp_path, monkeypatch):
    from openamer_cli import goals
    homes = [tmp_path / 'first', tmp_path / 'second']
    for index, home in enumerate(homes):
        monkeypatch.setenv('OPENAMER_HOME', str(home))
        manager = GoalManager('same-session-id')
        assert manager.state is None
        manager.set(f'goal-{index}')
    for index, home in enumerate(homes):
        monkeypatch.setenv('OPENAMER_HOME', str(home))
        assert GoalManager('same-session-id').state.goal == f'goal-{index}'
        assert goals._get_session_db().db_path == home / 'state.db'


def test_goal_tool_exposes_contract_checkpoint_and_actual_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAMER_HOME', str(tmp_path / 'home'))
    from tools.goal_tool import goal_tool, GOAL_SCHEMA
    names = GOAL_SCHEMA['parameters']['properties']
    assert 'checks' in names and 'budget' in names and 'next_step' in names
    args = {'command': f'"{sys.executable}" -c "print(1)"'}
    out = json.loads(goal_tool(action='set', goal='Build\nverify: executable result',
                              checks=[{'id': 'build', 'tool': 'terminal', 'args': args}],
                              session_id='tool-session'))
    assert out['completion']['outcome'] == 'active'
    assert 'executable result' in out['contract']
    assert out['execution_context']['shell']['family'] == 'posix'
    blocked = json.loads(goal_tool(action='report', status='done', session_id='tool-session'))
    assert 'verification' in blocked['error']
    partial = json.loads(goal_tool(action='report', status='partial', reason='Build not verified', session_id='tool-session'))
    assert partial['completion']['outcome'] == 'partial'


def test_progress_stall_warns_and_checkpoint_reanchors(setup):
    ace, manager, registry, calls, checks = setup
    registry.register(name='read_file', toolset='file', schema={}, handler=lambda *a, **k: '{"content":"read"}')
    for n in range(8):
        registry.dispatch('read_file', {'path': f'file-{n}'}, session_id='ace-test')
    assert 'goal drift' in manager.next_continuation_prompt()
    ace.checkpoint('ace-test', progress='Inspection complete', next_step='artifact')
    assert 'goal drift' not in manager.next_continuation_prompt()


def test_failed_call_can_be_retried_after_successful_intervention(setup):
    ace, manager, registry, calls, checks = setup
    failing = {'command': f'"{sys.executable}" -c "raise SystemExit(1)"'}
    run(registry, failing); run(registry, failing)
    assert 'error' in run(registry, failing)
    run(registry, {'command': f'"{sys.executable}" -c "print(\'intervention completed\')"'})
    assert run(registry, failing)['exit_code'] == 1
    assert ace.read('ace-test')['failed_calls'] == 3


def test_verified_strategy_is_recalled_not_invented(setup):
    ace, manager, registry, calls, checks = setup
    assert not ace.read('ace-test')['known_strategies']
    run(registry, checks[0]['args'])
    manager.mark_done('executed')
    manager.set('Similar artifact task')
    ace.configure('ace-test', checks=checks)
    known = ace.read('ace-test')['known_strategies']
    assert len(known) == 1
    assert known[0]['verification'][0]['exit_code'] == 0
    assert known[0]['tool_usage']['terminal']['calls'] == 1


def test_invalid_contract_does_not_replace_existing_goal(setup):
    ace, manager, registry, calls, checks = setup
    from tools.goal_tool import goal_tool
    out = json.loads(goal_tool(action='set', goal='Invalid replacement', checks=[], session_id='ace-test'))
    assert out['error']
    assert GoalManager('ace-test').state.goal == 'Produce a verified development artifact'
    assert ace.read('ace-test')['checks'] == checks


@pytest.mark.parametrize('outcome', ['blocked', 'partial', 'failed'])
def test_kanban_non_success_does_not_spend_more_turns(monkeypatch, outcome):
    from openamer_cli import goals
    monkeypatch.setattr(goals, 'judge_goal', lambda *a, **kw: (outcome, 'needs input', False, None, False))
    blocked = []
    result = goals.run_kanban_goal_loop(task_id='test', goal_text='artifact',
        run_turn=lambda *a: pytest.fail('must not continue blocked work'),
        task_status_fn=lambda: 'running', block_fn=blocked.append,
        first_response='needs input')
    assert result['outcome'] == 'blocked_by_judge'
    assert blocked == [f'Goal {outcome}: needs input']


def test_real_registry_repair_restart_and_artifact_smoke():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    p = subprocess.run([sys.executable, str(root / 'scripts/ace_smoke.py')],
                       cwd=root, env=dict(os.environ), capture_output=True,
                       text=True, encoding='utf-8', timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    result = json.loads(p.stdout)
    assert result['outcome'] == 'done'
    assert result['resumed_in_new_process']
    assert result['initial_failure_exit_code'] != 0
    assert result['verification']['exit_code'] == 0
    assert result['failed_calls'] == 1
    assert result['learned']


def test_cached_controller_observes_model_tool_goal_updates(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAMER_HOME', str(tmp_path / 'home'))
    cached = GoalManager('cached-session')
    assert not cached.is_active()
    from tools.goal_tool import goal_tool
    json.loads(goal_tool(action='set', goal='New durable goal', session_id='cached-session'))
    assert cached.is_active()
    json.loads(goal_tool(action='report', status='blocked', reason='permission required', session_id='cached-session'))
    assert not cached.is_active()
    assert cached.state.last_verdict == 'blocked'


def test_torn_goal_replacement_cannot_reuse_old_receipts(setup):
    ace, manager, registry, calls, checks = setup
    run(registry, checks[0]['args'])
    from openamer_cli import goals
    replacement = goals.GoalState(goal='Different goal', created_at=manager.state.created_at + 1)
    goals.save_goal('ace-test', replacement)
    with pytest.raises(RuntimeError, match='another goal'):
        GoalManager('ace-test').mark_done('use old receipt')

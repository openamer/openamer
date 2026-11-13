"""Evidence and repair budgets for the EXISTING persistent goal loop (ACE).

No task scheduler, shell executor or provider client lives here. Commands still
pass through the normal registry, approval middleware and terminal backend.
Only structured, foreground terminal results can satisfy executable checks.
The journal uses SessionDB.state_meta and its serialized write transactions.
"""
from __future__ import annotations

import json
import time
from typing import Any

from agent.tool_guardrails import (IDEMPOTENT_TOOL_NAMES, ToolCallSignature,
                                   classify_tool_failure)
from agent.tool_result_classification import file_mutation_result_landed

# Reuse runtime classifications, but arbitrary browser JS may mutate state.
_READ_ONLY = (IDEMPOTENT_TOOL_NAMES | {'skill_view', 'skills_list', 'browser_vision'}) - {'browser_console'}
_CONTROL = frozenset({'goal'})


def _db():
    from openamer_cli.goals import _get_session_db
    db = _get_session_db()
    if db is None:
        raise RuntimeError('ACE persistence unavailable; refusing unrecorded work')
    return db


def _key(session_id: str) -> str:
    return f'goal_completion:{session_id}'


def read(session_id: str) -> dict | None:
    if not session_id:
        return None
    raw = _db().get_meta(_key(session_id))
    return json.loads(raw) if raw else None


def _update(session_id: str, change, *, check_acceptance: bool = True,
            allow_stale_acceptance: bool = False):
    """Read/modify/write within one SQLite BEGIN IMMEDIATE transaction.

    Unlike a process-local mutex this also protects two independent resumed
    workers. No subprocess or network call runs while the transaction is held.

    Goal identity is always checked. ``check_acceptance`` is False only for
    ``bump_journal_revision``, which synchronizes the journal to a goal
    amendment. ``allow_stale_acceptance`` lets ``after_call`` close an event
    that was already in flight while exposing the mismatch to its callback;
    it never permits that event to issue a receipt.
    """
    result = None

    def write(conn):
        nonlocal result
        row = conn.execute('SELECT value FROM state_meta WHERE key = ?',
                           (_key(session_id),)).fetchone()
        data = json.loads(row[0]) if row else None
        acceptance_mismatch = False
        if data is not None:
            goal_row = conn.execute('SELECT value FROM state_meta WHERE key = ?',
                                    (f'goal:{session_id}',)).fetchone()
            if not goal_row:
                raise RuntimeError(
                    'ACE contract belongs to another goal; configure verification again')
            goal_data = json.loads(goal_row[0])
            if goal_data.get('created_at') != data['goal_created_at']:
                raise RuntimeError(
                    'ACE contract belongs to another goal; configure verification again')
            goal_rev = int(goal_data.get('acceptance_revision', 0) or 0)
            journal_rev = int(data.get('acceptance_revision', 0) or 0)
            acceptance_mismatch = goal_rev != journal_rev
            if not check_acceptance:
                # Only bump_journal_revision uses this path. Read the live goal
                # revision under the same SQLite lock so concurrent amendments
                # cannot regress the journal snapshot with a stale pre-read.
                data['acceptance_revision'] = goal_rev
                acceptance_mismatch = False
            elif acceptance_mismatch and not allow_stale_acceptance:
                raise RuntimeError(
                    'ACE acceptance definition changed after verification was configured; '
                    're-run configure() before completing')
        if allow_stale_acceptance:
            result = change(data, acceptance_mismatch)
        else:
            result = change(data)
        if data is not None:
            conn.execute('INSERT INTO state_meta(key, value) VALUES (?, ?) '
                         'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                         (_key(session_id), json.dumps(data, ensure_ascii=False)))

    _db()._execute_write(write)
    return result


def bump_journal_revision(session_id: str) -> None:
    """Drop every ACE receipt and bump the journal revision.

    Called by GoalManager whenever the acceptance definition changes
    (add/remove subgoal, set_contract). The journal's ``revision`` is the
    version the receipts are bound to; bumping it invalidates every receipt
    gathered under the old definition, including any that is still in flight
    (a pending check whose result has not landed yet). Receipts are cleared
    here rather than lazily, so a stale proof can never satisfy the amended
    goal — the missing-criterion check in ``_verification_error`` fires.

    This is the one journal write that must succeed *after* a goal amendment,
    so it skips the acceptance-revision guard that every other write enforces.
    It also re-syncs the journal's snapshot of the goal's acceptance revision,
    so later writes do not see a phantom mismatch.
    """
    def change(data):
        if not data:
            return None
        data['revision'] += 1
        data['receipts'] = {}
        return data
    _update(session_id, change, check_acceptance=False)


def validate_configuration(*, checks: list[dict], max_calls: int = 100,
                           max_seconds: float = 3600, max_repeats: int = 2) -> list[dict]:
    """Validate BEFORE replacing a user's existing persistent goal."""
    if not isinstance(checks, list) or not checks or len(checks) > 32:
        raise ValueError('Declare between 1 and 32 verification checks')
    ids = set()
    cleaned = []
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError('Each verification check must be an object')
        cid = str(check.get('id', '')).strip()
        args = check.get('args')
        if (not cid or cid in ids or check.get('tool') != 'terminal'
                or not isinstance(args, dict) or not isinstance(args.get('command'), str)
                or not args['command'].strip() or args.get('background') or args.get('pty')):
            raise ValueError('Each verification check needs a unique id and foreground terminal command')
        ids.add(cid)
        cleaned.append({'id': cid, 'tool': 'terminal', 'args': dict(args)})
    if not (type(max_calls) is int and type(max_repeats) is int
            and isinstance(max_seconds, (int, float))
            and 1 <= max_calls <= 10000 and 0 < max_seconds <= 604800
            and 1 <= max_repeats <= 20):
        raise ValueError('Invalid ACE resource budget')
    return cleaned


def configure(session_id: str, *, checks: list[dict], max_calls: int = 100,
              max_seconds: float = 3600, max_repeats: int = 2) -> dict:
    from openamer_cli.goals import load_goal
    state = load_goal(session_id)
    if state is None or state.status != 'active':
        raise ValueError('ACE requires an active persistent goal')
    cleaned = validate_configuration(checks=checks, max_calls=max_calls,
                                     max_seconds=max_seconds, max_repeats=max_repeats)
    strategy_key = _fingerprint('verification_strategy', {'checks': [
        {'id': c['id'], 'command': c['args']['command']} for c in cleaned]})
    from agent.goal_engine import GoalEngine
    known = [r['metadata'] for r in GoalEngine().recent_outcomes(n=100)
             if r.get('success') and r.get('metadata', {}).get('strategy_key') == strategy_key][-3:]
    data = {'strategy_key': strategy_key, 'known_strategies': known,
            'goal_created_at': state.created_at,
            'acceptance_revision': state.acceptance_revision, 'checks': cleaned,
            'calls_used': 0, 'max_calls': max_calls, 'max_repeats': max_repeats,
            'deadline': time.time() + max_seconds, 'events': [], 'failures': {},
            'receipts': {}, 'revision': 0, 'outcome': 'active', 'checkpoint': {},
            'failed_calls': 0, 'no_progress_calls': 0, 'tool_usage': {}, 'learned': False}
    _db().set_meta(_key(session_id), json.dumps(data))
    return data


def reset(session_id: str) -> None:
    # An explicit NEW goal gets a new budget, /resume does not.
    _db().set_meta(_key(session_id), 'null')


def migrate(old: str, new: str) -> None:
    data = read(old)
    if data:
        _db().set_meta(_key(new), json.dumps(data))
        reset(old)


def _fingerprint(tool: str, args: dict) -> str:
    signature = ToolCallSignature.from_call(tool, args)
    return signature.tool_name + ':' + signature.args_hash


def _check_ids(data: dict, tool: str, args: dict) -> list[str]:
    # Exact command AND explicit cwd. Extra execution-affecting arguments must
    # also match; do not let background=True satisfy a foreground check.
    return [c['id'] for c in data['checks']
            if c['tool'] == tool and c['args'] == args]


def before_call(session_id: str, tool: str, args: dict) -> dict | None:
    if not session_id or tool in _CONTROL:
        return None
    # Ordinary sessions only read metadata; do not take a SQLite write lock
    # for every tool call when no executable completion contract is enabled.
    if read(session_id) is None:
        return None
    def reserve(data):
        if not data or data['outcome'] == 'done':
            return None
        if data['outcome'] != 'active':
            if tool in _READ_ONLY:
                return None
            return {'error': 'ACE goal stopped: ' + data.get('reason', data['outcome'])}
        fp = _fingerprint(tool, args)
        if any(e['fingerprint'] == fp and e['status'] == 'pending' for e in data['events']):
            return {'error': 'ACE: uncertain result from interrupted/in-flight call; inspect it before retrying'}
        if data['calls_used'] >= data['max_calls'] or time.time() >= data['deadline']:
            data['outcome'] = 'failed'
            data['reason'] = 'ACE resource budget exhausted'
            return {'error': data['reason']}
        if data['failures'].get(fp, 0) >= data['max_repeats']:
            return {'error': 'ACE: repeated failed repair blocked; change strategy or environment'}
        data['calls_used'] += 1
        data['no_progress_calls'] += 1
        check_ids = _check_ids(data, tool, args)
        for cid in check_ids:
            data['receipts'].pop(cid, None)
        if not check_ids and tool not in _READ_ONLY:
            data['revision'] += 1
            data['receipts'] = {}
        event = {'id': data['calls_used'], 'tool': tool, 'fingerprint': fp,
                 'status': 'pending', 'started_at': time.time(),
                 'revision': data['revision'], 'checks': check_ids}
        data['events'].append(event)
        # Bound storage, but NEVER drop unresolved work from the journal.
        pending = [e for e in data['events'] if e['status'] == 'pending']
        finished = [e for e in data['events'] if e['status'] != 'pending'][-64:]
        data['events'] = sorted(pending + finished, key=lambda e: e['id'])
        return {'event_id': event['id'], 'fingerprint': event['fingerprint'],
                'revision': event['revision'],
                'goal_created_at': data['goal_created_at']}
    return _update(session_id, reserve)


def after_call(session_id: str, ticket: dict | None, result: Any) -> None:
    if not ticket or 'event_id' not in ticket:
        return
    parsed = result
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except (ValueError, TypeError):
            parsed = None
    def finish(data, acceptance_mismatch):
        # The goal or its journal may have been replaced while the tool was
        # running. An old result has no authority over the replacement.
        if not data:
            return None
        event = next((e for e in data['events']
                      if e['id'] == ticket['event_id']), None)
        if event is None:
            return None
        provenance = {
            'fingerprint': event['fingerprint'],
            'revision': event['revision'],
            'goal_created_at': data['goal_created_at'],
        }
        if any(key in ticket and ticket[key] != value
               for key, value in provenance.items()):
            return None

        stale = acceptance_mismatch or event['revision'] < data.get('revision', 0)
        # A non-JSON tool response is not executable verification evidence.
        text = result if isinstance(result, str) else json.dumps(result, default=str)
        failed, _ = classify_tool_failure(event['tool'], text)
        if not file_mutation_result_landed(event['tool'], text):
            failed = failed or (isinstance(parsed, dict) and
                               (bool(parsed.get('error')) or parsed.get('success') is False
                                or parsed.get('exit_code') not in (None, 0)))
        if stale:
            # Result gathered under a superseded definition: never a receipt.
            event['status'] = 'failed'
            event['seconds'] = max(0, time.time() - event['started_at'])
            return None
        event['status'] = 'failed' if failed else 'returned'
        event['seconds'] = max(0, time.time() - event['started_at'])
        usage = data['tool_usage'].setdefault(event['tool'], {'calls': 0, 'failures': 0, 'seconds': 0.0})
        usage['calls'] += 1
        usage['seconds'] += event['seconds']
        if failed:
            data['failed_calls'] += 1
            usage['failures'] += 1
            fp = event['fingerprint']
            data['failures'][fp] = data['failures'].get(fp, 0) + 1
        elif (event['tool'] not in _READ_ONLY and not event['checks']
              and isinstance(parsed, dict) and not parsed.get('session_id')
              and (parsed.get('success') is True or
                   (type(parsed.get('exit_code')) is int and parsed['exit_code'] == 0))):
            # A successful intervention may have repaired the environment.
            # Keep failed events for learning, but permit a fresh bounded retry.
            # Read-only operations and failed interventions do not reset it.
            data['failures'] = {}
        if (not failed and isinstance(parsed, dict)
                and type(parsed.get('exit_code')) is int and parsed['exit_code'] == 0
                and not parsed.get('session_id') and parsed.get('status') != 'running'
                and event['revision'] == data['revision']):
            event['status'] = 'verified' if event['checks'] else 'returned'
            if event['checks']:
                data['no_progress_calls'] = 0
            for cid in event['checks']:
                data['receipts'][cid] = {'id': cid, 'event_id': event['id'],
                                         'fingerprint': event['fingerprint'],
                                         'revision': data['revision'], 'exit_code': 0}
    _update(session_id, finish, allow_stale_acceptance=True)


def dispatch(session_id: str, tool: str, args: dict, invoke):
    """Wrap registry dispatch; normal approval and execution remain upstream."""
    ticket = before_call(session_id, tool, args)
    if ticket and ticket.get('error'):
        return json.dumps({'error': ticket['error']})
    try:
        result = invoke()
    except Exception as exc:
        after_call(session_id, ticket, {'error': type(exc).__name__})
        raise
    after_call(session_id, ticket, result)
    return result


def checkpoint(session_id: str, *, progress: str, next_step: str) -> dict:
    def change(data):
        if not data:
            raise ValueError('Configure ACE verification checks first')
        if next_step not in {c['id'] for c in data['checks']}:
            raise ValueError('Next step must name a declared verification criterion')
        data['checkpoint'] = {'progress': progress[:2000], 'next_step': next_step}
        data['no_progress_calls'] = 0
        return data['checkpoint']
    return _update(session_id, change)


def reactivate(session_id: str) -> None:
    def change(data):
        if data:
            if data['calls_used'] >= data['max_calls'] or time.time() >= data['deadline']:
                raise ValueError('ACE resource budget exhausted; resuming cannot reset it')
            data['outcome'] = 'active'
            data.pop('reason', None)
    _update(session_id, change)


def completion_error(session_id: str) -> str | None:
    return _verification_error(read(session_id))


def _verification_error(data: dict | None) -> str | None:
    if not data:
        return None
    journal_rev = int(data.get('revision', 0) or 0)
    stale = [c['id'] for c in data['checks']
             if c['id'] in data['receipts']
             and int(data['receipts'][c['id']].get('revision', 0) or 0) < journal_rev]
    missing = [c['id'] for c in data['checks'] if c['id'] not in data['receipts']] or stale
    if missing:
        return 'ACE verification missing or stale: ' + ', '.join(missing)
    if any(e['status'] == 'pending' for e in data['events']):
        return 'ACE verification cannot finish with uncertain pending tool results'
    return None


def _mark_done_atomic(session_id: str, reason: str,
                      goal_state_json: str | None = None) -> dict | None:
    """Validate ACE and mark both journal and goal done in one transaction."""
    completed = None
    candidate = json.loads(goal_state_json) if goal_state_json else None

    def write(conn):
        nonlocal completed
        goal_row = conn.execute(
            'SELECT value FROM state_meta WHERE key = ?',
            (f'goal:{session_id}',),
        ).fetchone()
        if not goal_row:
            return
        live_goal = json.loads(goal_row[0])
        if candidate:
            if (candidate.get('created_at') != live_goal.get('created_at')
                    or int(candidate.get('acceptance_revision', 0) or 0)
                    != int(live_goal.get('acceptance_revision', 0) or 0)):
                raise RuntimeError(
                    'Goal changed while completion was being committed; retry verification')
            goal_data = dict(candidate)
        else:
            goal_data = live_goal
        journal_row = conn.execute(
            'SELECT value FROM state_meta WHERE key = ?',
            (_key(session_id),),
        ).fetchone()
        data = json.loads(journal_row[0]) if journal_row else None
        if data:
            if goal_data.get('created_at') != data.get('goal_created_at'):
                raise RuntimeError(
                    'ACE contract belongs to another goal; configure verification again')
            goal_rev = int(goal_data.get('acceptance_revision', 0) or 0)
            journal_rev = int(data.get('acceptance_revision', 0) or 0)
            if goal_rev != journal_rev:
                raise RuntimeError(
                    'ACE acceptance definition changed after verification was configured; '
                    're-run configure() before completing')
            error = _verification_error(data)
            if error:
                raise ValueError(error)
            data['outcome'] = 'done'
            data['reason'] = reason
            conn.execute(
                'INSERT INTO state_meta(key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                (_key(session_id), json.dumps(data, ensure_ascii=False)),
            )
            completed = data
        goal_data['status'] = 'done'
        goal_data['last_verdict'] = 'done'
        goal_data['last_reason'] = reason
        conn.execute(
            'INSERT INTO state_meta(key, value) VALUES (?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (f'goal:{session_id}', json.dumps(goal_data, ensure_ascii=False)),
        )

    _db()._execute_write(write)
    return completed


def report(session_id: str, outcome: str, reason: str, *,
           goal_state_json: str | None = None) -> None:
    if outcome not in {'done', 'partial', 'blocked', 'failed'}:
        raise ValueError('Invalid completion outcome')
    if outcome == 'done':
        data = _mark_done_atomic(session_id, reason, goal_state_json)
    else:
        def change(data):
            if data:
                data['outcome'] = outcome
                data['reason'] = reason
        _update(session_id, change)
        data = read(session_id)
    if outcome == 'done' and data and not data['learned']:
        # Reuse the existing measured-goal outcome store, consumed by the
        # existing reflection system. No unverified tips enter learning data.
        from agent.goal_engine import GoalEngine
        GoalEngine().record_outcome(
            f'completion:{session_id}', True, note='ACE executable verification passed',
            metadata={'strategy_key': data['strategy_key'],
                      'verification': list(data['receipts'].values()),
                      'tool_usage': data['tool_usage'],
                      'observed_steps': [{k: e.get(k) for k in ('tool', 'fingerprint', 'status')}
                                         for e in data['events']],
                      'tools': sorted({e['tool'] for e in data['events']}),
                      'failed_attempts': data['failed_calls'],
                      'calls_used': data['calls_used'],
                      'tool_seconds': sum(e.get('seconds', 0) for e in data['events'])})
        _update(session_id, lambda d: d.update(learned=True))


def prompt_context(session_id: str) -> str:
    data = read(session_id)
    if not data:
        return ''
    missing = [c['id'] for c in data['checks'] if c['id'] not in data['receipts']]
    warning = (f'Progress review: {data["no_progress_calls"]} calls without advancing '
               'an executable criterion; check for goal drift.\n'
               if data['no_progress_calls'] >= 8 else '')
    return ('\n\n[ACE checkpoint — preserve the original goal]\n'
            f'{warning}'
            f'Checkpoint: {json.dumps(data["checkpoint"], ensure_ascii=False)}\n'
            f'Unverified criteria: {", ".join(missing) or "none"}\n'
            f'Tool budget: {data["calls_used"]}/{data["max_calls"]}; '
            f'repeated failures: {sum(data["failures"].values())}.\n'
            'If current work does not advance a declared criterion, re-anchor '
            'before spending more budget. Use existing delegation/A2A tools '
            'for independent subtasks; verify their artifacts in this session.')

#!/usr/bin/env python3
"""Reproducible ACE smoke: broken artifact -> repair -> process restart -> verify.

Runs ONLY in a new temporary profile/workspace. Uses normal registry tools,
including terminal approval checks. No providers, real user files, or services
are modified. Stdout is a machine-readable report; failures exit nonzero.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def call(name, args):
    from tools.registry import registry
    result = registry.dispatch(name, args, session_id='ace-smoke', task_id='ace-smoke')
    return json.loads(result) if isinstance(result, str) else result


def resume(home: Path, workspace: Path) -> dict:
    os.environ['OPENAMER_HOME'] = str(home)
    from openamer_cli.goals import GoalManager
    from openamer_cli.goal_completion import read
    from tools import terminal_tool  # noqa: F401 - register the actual tool
    manager = GoalManager('ace-smoke')
    assert manager.is_active(), 'Persistent goal did not survive restart'
    state = read('ace-smoke')
    assert state['checkpoint']['next_step'] == 'artifact'
    verification = call('terminal', state['checks'][0]['args'])
    assert verification.get('exit_code') == 0, verification
    manager.mark_done('Actual repaired artifact executed successfully after restart')
    state = read('ace-smoke')
    return {'outcome': state['outcome'], 'resumed_in_new_process': True,
            'verification': verification, 'calls_used': state['calls_used'],
            'failed_calls': state['failed_calls'], 'learned': state['learned'],
            'receipts': state['receipts']}


def exercise(home: Path, workspace: Path) -> dict:
    home.mkdir(); workspace.mkdir()
    os.environ['OPENAMER_HOME'] = str(home)
    # Explicit local backend; the smoke never reaches a configured SSH/container.
    os.environ['TERMINAL_ENV'] = 'local'
    os.environ['TERMINAL_SANDBOX_ENABLED'] = 'false'
    from tools import terminal_tool, file_tools  # noqa: F401
    from openamer_cli.goals import GoalManager
    from openamer_cli.goal_completion import configure, checkpoint
    artifact = workspace / 'artifact.py'
    artifact.write_text('def answer(:\n    return 42\n', encoding='utf-8')
    command = shlex.join([Path(sys.executable).as_posix(), artifact.as_posix()])
    args = {'command': command, 'workdir': workspace.as_posix(), 'timeout': 30}
    manager = GoalManager('ace-smoke')
    manager.set('Repair the Python artifact and execute its assertion after restart', max_turns=4)
    configure('ace-smoke', checks=[{'id': 'artifact', 'tool': 'terminal', 'args': args}],
              max_calls=8, max_seconds=120, max_repeats=2)
    failure = call('terminal', args)
    assert failure.get('exit_code') not in (None, 0), failure
    repair = call('write_file', {'path': artifact.as_posix(),
                                'content': 'def answer():\n    return 42\n\nassert answer() == 42\nprint("ACE_ARTIFACT_VERIFIED")\n'})
    assert not repair.get('error'), repair
    checkpoint('ace-smoke', progress='Broken Python artifact repaired; execution still unverified', next_step='artifact')
    child = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            '--resume', '--home', str(home), '--workspace', str(workspace)],
                           cwd=ROOT, env=dict(os.environ), capture_output=True,
                           text=True, encoding='utf-8', timeout=90)
    assert child.returncode == 0, child.stdout + child.stderr
    result = json.loads(child.stdout)
    assert 'ACE_ARTIFACT_VERIFIED' in result['verification']['output'], result
    result['initial_failure_exit_code'] = failure['exit_code']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--home', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--workspace', type=Path, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.resume:
        if options.home is None or options.workspace is None:
            parser.error('Resume needs isolated home and workspace')
        result = resume(options.home, options.workspace)
    else:
        with tempfile.TemporaryDirectory(prefix='openamer-ace-smoke-') as tmp:
            try:
                result = exercise(Path(tmp) / 'profile', Path(tmp) / 'workspace')
            finally:
                from tools.terminal_tool import cleanup_vm
                from openamer_cli.goals import _DB_CACHE
                cleanup_vm('ace-smoke')
                for db in list(_DB_CACHE.values()):
                    db.close()
                _DB_CACHE.clear()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

"""Shell context and real interpreter switching without changing global shell."""
import os
import shutil
import subprocess

import pytest

from tools.environments.local import describe_shell, _find_bash


@pytest.mark.parametrize('path,name,family', [
    ('C:/Program Files/Git/bin/bash.exe', 'bash', 'posix'),
    (r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe', 'powershell', 'powershell'),
    ('C:/Program Files/PowerShell/7/pwsh.exe', 'pwsh', 'powershell'),
    (r'C:\Windows\System32\cmd.exe', 'cmd', 'cmd'),
    ('/usr/bin/bash', 'bash', 'posix'), ('/bin/zsh', 'zsh', 'posix'),
    ('/bin/dash', 'dash', 'posix'), ('/bin/fish', 'fish', 'unknown'),
])
def test_shell_grammar_depends_on_executable_not_host_os(path, name, family):
    actual = describe_shell(path)
    assert actual['name'] == name
    assert actual['family'] == family


def test_bash_executes_posix_syntax_even_on_windows(monkeypatch):
    monkeypatch.setenv('SHELL', 'powershell.exe')
    shell = describe_shell()
    assert shell['family'] == 'posix'
    result = subprocess.run([_find_bash(), '-c', 'ACE_WORD=verified; printf "%s" "$ACE_WORD"'],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'verified'


def test_explicit_powershell_then_bash_switch():
    powershell = shutil.which('pwsh') or shutil.which('powershell.exe')
    if not powershell:
        pytest.skip('PowerShell not installed; Windows CI exercises this real interpreter')
    ps = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command',
                         "$value='ACE_PS'; Write-Output $value"],
                        capture_output=True, text=True, timeout=30)
    assert ps.returncode == 0, ps.stderr
    assert ps.stdout.strip() == 'ACE_PS'
    bash = subprocess.run([_find_bash(), '-c', "printf 'ACE_BASH'"],
                          capture_output=True, text=True, timeout=20)
    assert bash.returncode == 0, bash.stderr
    assert bash.stdout == 'ACE_BASH'


@pytest.mark.skipif(os.name != 'nt', reason='CMD is a Windows interpreter')
def test_cmd_interpreter():
    cmd = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', 'echo ACE_CMD'],
                         capture_output=True, text=True, timeout=20)
    assert cmd.returncode == 0, cmd.stderr
    assert cmd.stdout.strip() == 'ACE_CMD'


def test_remote_context_never_reports_host_as_target(monkeypatch):
    from tools import terminal_tool
    from openamer_cli.goal_execution import execution_context
    monkeypatch.setattr(terminal_tool, '_get_env_config', lambda: {'env_type': 'ssh'})
    data = execution_context()
    assert data['backend'] == 'ssh'
    assert data['target_os'] == 'unknown'
    assert data['shell'] is None


def test_active_remote_backend_overrides_local_process_config(monkeypatch):
    from tools import terminal_tool
    from openamer_cli.goal_execution import execution_context
    class SSHEnvironment:
        pass
    monkeypatch.setattr(terminal_tool, '_get_env_config', lambda: {'env_type': 'local'})
    monkeypatch.setattr(terminal_tool, 'get_active_env', lambda task: SSHEnvironment())
    data = execution_context('remote-task')
    assert data['backend'] == 'ssh'
    assert data['target_os'] == 'unknown'
    assert data['shell'] is None

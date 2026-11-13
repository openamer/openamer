"""Execution context for ACE, using the actual terminal backend resolver."""
import platform
import sys


def execution_context(task_id: str = '') -> dict:
    from tools.terminal_tool import _get_env_config, get_active_env
    config = _get_env_config()
    backend = config.get('env_type', 'local')
    env = get_active_env(task_id) if task_id else None
    if env is not None:
        # Per-task overrides may differ from process-wide terminal config.
        backend = type(env).__name__.removesuffix('Environment').lower()
    data = {'backend': backend, 'host_os': platform.system(),
            'python': sys.executable, 'target_os': 'unknown', 'shell': None}
    if backend == 'local':
        from tools.environments.local import describe_shell
        data['target_os'] = platform.system()
        data['shell'] = describe_shell()
    else:
        data['note'] = 'Remote target OS/shell must be probed through its terminal; host OS is not target evidence.'
    if env is not None:
        data['backend_class'] = type(env).__name__
    return data

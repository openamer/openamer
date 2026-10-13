"""Live verification for the Windows containment module — real OS calls, no mocks.

Run:  python scripts/verify_win_sandbox.py

Prints evidence for: job-object creation, real process-tree kill, credential
masking via the existing sanitizer, and the filesystem boundary.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.win_sandbox import (  # noqa: E402
    JobLimits,
    SandboxPolicy,
    assign_pid_to_job,
    build_job_object,
    check_write_path,
    describe_enforcement,
    enforce_environment,
    protected_paths,
)


def main() -> int:
    print("== 1. enforcement report ==")
    report = describe_enforcement()
    print("  mechanism:", report["mechanism"])
    for name, value in report["enforced"].items():
        print(f"  enforced  {name}: {value}")
    for name, value in report["partial"].items():
        print(f"  partial   {name}: {value}")

    print("== 2. job object + real process tree kill ==")
    child = subprocess.Popen(
        ["cmd", "/c", "ping -n 60 127.0.0.1 > NUL"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    job = build_job_object(JobLimits(kill_on_close=True, max_processes=16, max_memory_mb=512))
    print("  job active:", job.active, "| error:", job.error)
    ok, detail = assign_pid_to_job(job, child.pid)
    print(f"  assign pid {child.pid}: {ok} ({detail})")
    print("  child alive before close:", child.poll() is None)
    job.close()
    for _ in range(50):
        if child.poll() is not None:
            break
        time.sleep(0.1)
    print("  child alive after close :", child.poll() is None, "-> exit", child.poll())
    if child.poll() is None:  # pragma: no cover
        child.kill()

    print("== 3. credential masking (existing sanitizer) ==")
    host = dict(os.environ)
    present = sorted(k for k in host if k.upper().endswith(("_KEY", "_TOKEN", "_SECRET")))
    env = enforce_environment(host)
    leaked = sorted(k for k in env if k.upper().endswith(("_KEY", "_TOKEN", "_SECRET")))
    print("  secret vars in host env :", present, f"({len(present)} total)")
    print("  secret vars in child env:", leaked, "->", "CLEAN" if not leaked else "LEAK")
    print("  shell plumbing kept     :", "PATH" in env, "| vars:", len(env))

    print("== 4. filesystem boundary ==")
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cases = [
        ("write <root>/agent/x.py", os.path.join(root, "agent", "x.py")),
        ("write <root>/.git/config", os.path.join(root, ".git", "config")),
        ("write <root>/../outside.txt", os.path.join(root, "..", "outside.txt")),
        ("write ~/.ssh/id_rsa", os.path.expanduser("~/.ssh/id_rsa")),
    ]
    for label, path in cases:
        allowed, reason = check_write_path(path, writable_root=root)
        print(f"  {label:<28}: {allowed} ({reason[:60]})")
    print("  no root configured         :", check_write_path(os.path.join(root, "x"), writable_root=None))
    print("  protected dirs             :", len(protected_paths()), "entries")

    print("== 5. terminal wiring (real spawn via tools.environments.local) ==")
    try:
        # NOTE: only import what is not already imported at module level —
        # a local `from ... import JobLimits` here makes JobLimits local to the
        # whole function and shadows the module-level import above.
        from tools.environments import local as local_env

        # Force the opt-in policy for this check without touching config.yaml.
        local_env._TERMINAL_SANDBOX_POLICY = SandboxPolicy(
            enabled=True,
            limits=JobLimits(kill_on_close=True, max_processes=8, max_memory_mb=512),
        )
        env_obj = local_env.LocalEnvironment()
        proc = env_obj._run_bash("echo wiring-ok")
        out = (proc.communicate(timeout=60)[0] or "")
        print("  command still works        :", "wiring-ok" in out)
        print("  proc carries containment   :", getattr(proc, "_openamer_sandbox_job", None) is not None)
        env_obj._kill_process(proc)
        print("  job released after kill    :", getattr(proc, "_openamer_sandbox_job", None) is None)
    except Exception as exc:  # noqa: BLE001 - report, do not hide
        print("  wiring check FAILED:", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
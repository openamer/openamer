#!/usr/bin/env python3
"""Self-test for ast-hygiene-probe.py -- does it fire AND stay quiet?

WHY A SELF-TEST FOR A PROBE
---------------------------
A hygiene probe that always reports clean is worse than none: it certifies dead
code as live. This suite asserts BOTH directions:
  * a file with a dead name and a clone      -> findings, exit 1
  * a clean file                             -> no findings, exit 0
  * an unmatched path                        -> exit 2, NOT exit 0
The last case is the false-clean trap that the probe itself once had.

Run:  python ast-hygiene-probe-selftest.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "ast-hygiene-probe.py")

DIRTY = '''
def used(x):
    return x + 1


def never_called(x):
    return x - 1


def helper_a(vals):
    total = 0
    for v in vals:
        total += v
    return total


def helper_b(vals):
    total = 0
    for v in vals:
        total += v
    return total


DEAD_CONST = 42


if __name__ == "__main__":
    print(used, helper_a, helper_b)
'''

CLEAN = '''
def used(x):
    return x + 1


if __name__ == "__main__":
    print(used(1))
'''


def run(path):
    r = subprocess.run([sys.executable, PROBE, path],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    ok = True
    with tempfile.TemporaryDirectory() as td:
        dirty = os.path.join(td, "dirty_probe_target.py")
        clean = os.path.join(td, "clean_probe_target.py")
        open(dirty, "w", encoding="utf-8").write(DIRTY)
        open(clean, "w", encoding="utf-8").write(CLEAN)

        rc_d, out_d = run(dirty)
        fired = rc_d == 1 and "never_called" in out_d
        ok &= fired
        print(f"  dirty file  -> exit {rc_d}, dead name reported: {fired}  "
              f"{'OK' if fired else 'FAIL'}")

        clone = rc_d == 1 and "helper_a" in out_d and "helper_b" in out_d
        ok &= clone
        print(f"  clone pair  -> both sites named: {clone}  "
              f"{'OK' if clone else 'FAIL'}")

        rc_c, out_c = run(clean)
        quiet = rc_c == 0 and "never_called" not in out_c
        ok &= quiet
        print(f"  clean file  -> exit {rc_c}, silent: {quiet}  "
              f"{'OK' if quiet else 'FAIL'}")

        rc_m, _ = run(os.path.join(td, "does_not_exist.py"))
        guarded = rc_m != 0
        ok &= guarded
        print(f"  bad path    -> exit {rc_m} (must NOT be 0)  "
              f"{'OK' if guarded else 'FAIL (false clean!)'}")

    print()
    print("SELFTEST:", "probe has teeth" if ok else "PROBE IS UNRELIABLE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

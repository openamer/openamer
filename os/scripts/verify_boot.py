"""Bounded, read-only QEMU BIOS boot smoke test (no physical disk writes)."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--qemu', default='qemu-system-x86_64')
    parser.add_argument('--seconds', type=float, default=15)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='openamer-boot-') as folder:
        log = Path(folder) / 'debug.log'
        proc = subprocess.Popen([
            args.qemu, '-drive', f'file={args.image.resolve()},format=raw',
            '-display', 'none', '-monitor', 'none', '-serial', 'none',
            '-debugcon', f'file:{log}', '-snapshot', '-no-reboot',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        alive = False
        try:
            _, errors = proc.communicate(timeout=args.seconds)
        except subprocess.TimeoutExpired:
            alive = True
            proc.terminate()
            _, errors = proc.communicate(timeout=10)
        text = log.read_text(errors='replace') if log.exists() else ''
        print(text)
        if errors:
            print(errors.decode(errors='replace'))
        passed = alive and 'OpenAmer OS kernel is running.' in text
        print(f'boot_marker={"OpenAmer OS kernel is running." in text} alive_at_deadline={alive}')
        return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

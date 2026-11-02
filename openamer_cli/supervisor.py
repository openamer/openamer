"""Opt-in local service supervision, independent of gateway/tool lifecycles.

The process registry manages sandbox terminal sessions, daemon_pool manages
threads, and service_manager wraps host init systems. None owns this explicit
user registry or proves application readiness. This module installs nothing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import psutil

from openamer_cli.config import get_openamer_home


class InstanceLock:
    """Nonblocking OS lock; automatically released on crash, never unlink it.

    PID files alone race and misidentify recycled PIDs. The lock is also the
    status command's source of truth, not a persisted 'running' flag.
    """

    def __init__(self, path: Path, *, create: bool = True):
        self.path = path
        self.create = create
        self.file = None

    def __enter__(self):
        if self.create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b" if self.create else "r+b")
        try:
            if os.name == "nt":
                import msvcrt

                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise RuntimeError("supervisor lock held by another instance") from exc
        return self

    def __exit__(self, *_):
        if self.file is not None:
            if os.name == "nt":
                import msvcrt

                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def number(value, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return float(value)


def load_registry(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("registry requires version: 1")
    services = raw.get("services")
    if not isinstance(services, list) or len(services) > 128:
        raise ValueError("services must be a list (maximum 128)")
    names = set()
    for service in services:
        if not isinstance(service, dict):
            raise ValueError("service must be an object")
        name = service.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("service names must be nonempty and unique")
        names.add(name)
        if not isinstance(service.get("observe_only", True), bool):
            raise ValueError(f"{name}: observe_only must be boolean")
        start = service.get("start", {})
        if not isinstance(start, dict):
            raise ValueError(f"{name}: start must be an object")
        argv = start.get("argv")
        if argv is not None and (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in argv)
        ):
            raise ValueError(f"{name}: start.argv must be a nonempty string array")
        if argv and Path(argv[0]).suffix.lower() in {".bat", ".cmd"}:
            raise ValueError(
                "batch scripts invoke an implicit shell; use an executable"
            )
        if not service.get("observe_only", True) and argv is None:
            raise ValueError(f"{name}: managed service needs start.argv")
        if "cwd" in start and not isinstance(start["cwd"], str):
            raise ValueError(f"{name}: cwd must be a string")
        for key, default, low, high in (
            ("ready_timeout_s", 15, 0.1, 300),
            ("backoff_s", 5, 0.1, 3600),
            ("restart_budget_per_hour", 6, 0, 100),
        ):
            value = number(service.get(key, default), key, low, high)
            if key == "restart_budget_per_hour" and not value.is_integer():
                raise ValueError("restart budget must be an integer")
        probe = service.get("probe")
        if not isinstance(probe, dict) or probe.get("kind") not in {
            "http_status",
            "http_json",
            "tcp",
        }:
            raise ValueError(f"{name}: probe requires http_status, http_json or tcp")
        number(probe.get("timeout_s", 1), "timeout_s", 0.05, 30)
        if probe["kind"] == "tcp":
            host = probe.get("host", "127.0.0.1")
            number(probe.get("port"), "port", 1, 65535)
            if not float(probe["port"]).is_integer():
                raise ValueError("port must be an integer")
        else:
            url = urllib.parse.urlsplit(probe.get("url", ""))
            host = url.hostname
            if url.scheme not in {"http", "https"} or url.username or url.password:
                raise ValueError("probe URL must be HTTP(S), without credentials")
            number(probe.get("status", 200), "status", 100, 599)
            if "expect" in probe and not isinstance(probe["expect"], dict):
                raise ValueError("probe.expect must be an object")
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("supervisor probes must target loopback")
    return services


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe_service(probe: dict, *, timeout: float | None = None) -> tuple[bool, str]:
    timeout = min(probe.get("timeout_s", 1), timeout or 30)
    try:
        if probe["kind"] == "tcp":
            with socket.create_connection(
                (probe.get("host", "127.0.0.1"), int(probe["port"])), timeout
            ):
                return True, "TCP connection accepted (not application identity)"
        # No proxy or redirects: local probes must remain local.
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )
        with opener.open(probe["url"], timeout=timeout) as response:
            if response.status != probe.get("status", 200):
                return False, f"unexpected HTTP status {response.status}"
            if probe["kind"] == "http_json":
                body = json.loads(response.read(1048577))
                if not isinstance(body, dict) or any(
                    k not in body or body[k] != v
                    for k, v in probe.get("expect", {}).items()
                ):
                    return False, "JSON health assertions failed"
        return True, "health probe passed"
    except (OSError, ValueError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def owned_process(record: dict):
    """Never signal a process based on a recycled PID or an endpoint alone."""
    try:
        process = psutil.Process(record["pid"])
        if (
            process.create_time() == record["created"]
            and process.is_running()
            and process.status() != psutil.STATUS_ZOMBIE
        ):
            return process
    except (KeyError, psutil.Error):
        pass
    return None


def stop_owned(record: dict) -> bool:
    process = owned_process(record)
    if process is None:
        return True
    try:
        processes = process.children(recursive=True) + [process]
        for child in processes:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(processes, timeout=2)
        for child in alive:
            child.kill()
        _, alive = psutil.wait_procs(alive, timeout=2)
        return not alive
    except psutil.Error:
        return False


class Supervisor:
    def __init__(self, home: Path | None = None):
        self.home = home if home is not None else get_openamer_home()
        self.directory = self.home / "supervisor"
        self.registry = self.directory / "registry.json"
        self.state_path = self.directory / "state.json"
        self.lock_path = self.directory / "supervisor.lock"
        self.state = {"version": 1, "services": {}, "events": []}
        self.children: list[subprocess.Popen] = []

    def init(self) -> bool:
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            with self.registry.open("x", encoding="utf-8") as stream:
                json.dump({"version": 1, "services": []}, stream, indent=2)
                stream.write("\n")
        except FileExistsError:
            return False
        return True

    def save(self):
        self.state["updated_at"] = time.time()
        atomic_json(self.state_path, self.state)

    def transition(self, name: str, status: str, reason: str):
        record = self.state["services"].setdefault(name, {})
        previous = record.get("state", "UNKNOWN")
        record.update(state=status, reason=reason, checked_at=time.time())
        if previous != status:
            self.state["events"].append({
                "at": time.time(),
                "service": name,
                "from": previous,
                "to": status,
                "reason": reason,
            })
            self.state["events"] = self.state["events"][-200:]
        self.save()

    def cycle(self, services: list[dict], stop: threading.Event):
        # Reap our own exited children without touching adopted services.
        self.children = [child for child in self.children if child.poll() is None]
        for service in services:
            if stop.is_set():
                break
            name = service["name"]
            record = self.state["services"].setdefault(name, {})
            healthy, reason = probe_service(service["probe"])
            if healthy:
                record["adopted"] = owned_process(record.get("process", {})) is None
                self.transition(name, "UP", reason)
                continue
            if service.get("observe_only", True):
                self.transition(name, "DOWN", reason)
                continue
            if record.get("state", "UNKNOWN") in {"UNKNOWN", "UP"}:
                self.transition(name, "DOWN", reason)
            if owned_process(record.get("process", {})) is not None:
                self.transition(
                    name,
                    "DEGRADED",
                    "previously started process still alive; refusing duplicate",
                )
                continue
            now = time.time()
            attempts = [
                stamp for stamp in record.get("attempts", []) if stamp > now - 3600
            ]
            record["attempts"] = attempts
            if len(attempts) >= service.get("restart_budget_per_hour", 6):
                self.transition(
                    name, "BUDGET_EXHAUSTED", "hourly restart budget exhausted"
                )
                continue
            if now < record.get("retry_at", 0):
                self.transition(name, "BACKOFF", "waiting for retry_at")
                continue
            attempts.append(now)
            record["retry_at"] = now + min(
                3600, service.get("backoff_s", 5) * 2 ** min(len(attempts) - 1, 10)
            )
            record.pop("process", None)
            record["adopted"] = False
            self.transition(name, "STARTING", "starting argv; readiness not yet proven")
            start = service["start"]
            argv = [arg.replace("{home}", str(self.home)) for arg in start["argv"]]
            cwd = start.get("cwd", str(self.home)).replace("{home}", str(self.home))
            try:
                child = subprocess.Popen(
                    argv,
                    cwd=cwd,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=os.name != "nt",
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    if os.name == "nt"
                    else 0,
                )
                self.children.append(child)
                record["process"] = {
                    "pid": child.pid,
                    "created": psutil.Process(child.pid).create_time(),
                }
                self.save()
                deadline = time.monotonic() + service.get("ready_timeout_s", 15)
                while not stop.is_set() and time.monotonic() < deadline:
                    healthy, reason = probe_service(
                        service["probe"], timeout=max(0.01, deadline - time.monotonic())
                    )
                    if healthy:
                        self.transition(name, "UP", reason)
                        break
                    if child.poll() is not None:
                        reason = (
                            f"process exited with code {child.returncode}; {reason}"
                        )
                        break
                    stop.wait(min(0.1, max(0, deadline - time.monotonic())))
                if not healthy:
                    stopped = stop_owned(record.get("process", {}))
                    self.transition(
                        name,
                        "START_FAILED",
                        f"readiness failed: {reason}; child stopped={stopped}",
                    )
            except (OSError, psutil.Error) as exc:
                self.transition(name, "START_FAILED", f"{type(exc).__name__}: {exc}")

    def execute(
        self,
        *,
        once: bool = False,
        interval: float = 2,
        stop: threading.Event | None = None,
    ):
        stop = stop if stop is not None else threading.Event()
        with InstanceLock(self.lock_path):
            services = load_registry(
                self.registry
            )  # validate ALL entries before any start
            if self.state_path.exists():
                self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
            # Removed services are no longer supervised; never stop them implicitly.
            names = {service["name"] for service in services}
            self.state["services"] = {
                k: v for k, v in self.state["services"].items() if k in names
            }
            try:
                while not stop.is_set():
                    self.cycle(services, stop)
                    self.save()
                    if once:
                        break
                    stop.wait(interval)
            except KeyboardInterrupt:
                for name, record in self.state["services"].items():
                    if record.get("state") == "STARTING":
                        stopped = stop_owned(record.get("process", {}))
                        self.transition(
                            name,
                            "START_FAILED",
                            f"readiness interrupted; child stopped={stopped}",
                        )
            finally:
                # Ready children deliberately survive supervisor shutdown, for adoption.
                self.save()
        return self.state

    def status(self) -> dict:
        running = False
        try:
            with InstanceLock(self.lock_path, create=False):
                pass
        except FileNotFoundError:
            pass
        except RuntimeError:
            running = True
        snapshot = None
        if self.state_path.exists():
            snapshot = json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "running": running,
            "message": "running" if running else "not running",
            "snapshot": snapshot,
            "note": "snapshot is historical, not a current service health check"
            if snapshot
            else "no state",
        }


def command(args) -> int:
    supervisor = Supervisor()
    try:
        if args.supervisor_command == "init":
            created = supervisor.init()
            print(
                f"{'Created empty registry' if created else 'Registry exists; unchanged'}: {supervisor.registry}"
            )
            return 0
        if args.supervisor_command == "status":
            result = supervisor.status()
        else:
            if not supervisor.registry.exists():
                raise ValueError("no registry; run openamer supervisor init first")
            result = supervisor.execute(
                once=args.supervisor_command == "once", interval=args.interval
            )
        print(json.dumps(result, indent=2))
        if args.supervisor_command == "once":
            return int(any(row["state"] != "UP" for row in result["services"].values()))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Supervisor: {exc}")
        return 1


def register_cli(subparsers):
    parser = subparsers.add_parser(
        "supervisor", help="Opt-in native local service supervision"
    )
    commands = parser.add_subparsers(dest="supervisor_command", required=True)
    for name in ("init", "once", "run", "status"):
        subparser = commands.add_parser(name)
        if name in {"once", "run"}:
            subparser.add_argument(
                "--interval",
                type=interval_argument,
                default=2.0,
                help="Seconds between passes (run only; registry loaded at startup)",
            )
        subparser.set_defaults(func=command)
    return parser


def interval_argument(value):
    try:
        return number(float(value), "interval", 0.1, 3600)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc

#!/usr/bin/env python3
"""
Webhook Engine — Event-Triggered Automation Server
===================================================
Port 8900 HTTP server that receives webhooks, evaluates rules,
and executes actions (script, alert, restart, log).

Usage:
  python webhook-engine.py --start          Start the server
  python webhook-engine.py --add-rule JSON  Add a new rule
  python webhook-engine.py --list-rules     List all rules
  python webhook-engine.py --log            Show last 50 events
  python webhook-engine.py --health         Check if server is running
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

# ── Constants ────────────────────────────────────────────────────────────────
HOME = Path.home()
WEBHOOK_DIR = HOME / ".webhook-engine"
RULES_FILE = WEBHOOK_DIR / "rules.json"
STATE_FILE = WEBHOOK_DIR / "state.json"
SCRIPTS_DIR = HOME / "scripts"
LOCK_FILE = WEBHOOK_DIR / "server.lock"
HOST = "0.0.0.0"
PORT = 8900
MAX_LOG = 200  # max events/actions/errors kept in state

# ── Ensure directories ───────────────────────────────────────────────────────
WEBHOOK_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


# ── State helpers ────────────────────────────────────────────────────────────

def load_json(path):
    """Load JSON from file, return default on failure."""
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return [] if path == RULES_FILE else {"events": [], "actions": [], "errors": [], "total_events": 0, "total_actions": 0, "total_errors": 0}


def save_json(path, data):
    """Save JSON atomically."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def load_rules():
    return load_json(RULES_FILE)


def save_rules(rules):
    save_json(RULES_FILE, rules)


def load_state():
    return load_json(STATE_FILE)


def save_state(state):
    save_json(STATE_FILE, state)


def append_log(state, key, entry):
    """Append to a log array, trim to MAX_LOG."""
    arr = state.setdefault(key, [])
    arr.append(entry)
    if len(arr) > MAX_LOG:
        arr[:] = arr[-MAX_LOG:]
    return state


def timestamp():
    return datetime.now(timezone.utc).isoformat()


# ── Rule engine ──────────────────────────────────────────────────────────────

def evaluate_condition(condition, event_data):
    """
    Evaluate a condition dict against event data.
    Condition keys are dot-notation paths into event_data (e.g. "repo" or "payload.branch").
    All specified keys must match for the condition to pass.
    Return True if condition is empty/None (unconditional match).
    """
    if not condition:
        return True
    if not isinstance(condition, dict):
        return False
    for key, expected in condition.items():
        # Walk dot-notation path
        parts = key.split(".")
        val = event_data
        try:
            for p in parts:
                val = val[p]
        except (KeyError, TypeError, IndexError):
            return False
        # Support list matching: expected is a list, val should be in it
        if isinstance(expected, list):
            if val not in expected:
                return False
        elif isinstance(expected, str) and expected.startswith("re:"):
            # regex match
            import re
            if not re.search(expected[3:], str(val)):
                return False
        else:
            if val != expected:
                return False
    return True


def execute_action(action_def, event_data):
    """
    Execute an action. action_def is a dict with "type" and parameters.
    Returns (success: bool, result: str).
    """
    action_type = action_def.get("type", "log-event")
    params = {k: v for k, v in action_def.items() if k != "type"}
    ts = timestamp()

    try:
        if action_type == "run-script":
            script_path = params.get("path", "")
            script_args = params.get("args", [])
            full_path = Path(script_path)
            if not full_path.is_absolute():
                full_path = SCRIPTS_DIR / script_path
            if not full_path.exists():
                return False, f"Script not found: {full_path}"

            # Build command
            cmd = [sys.executable, str(full_path)] + script_args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return True, f"Script '{full_path.name}' OK: {result.stdout.strip()[:200]}"
            else:
                return False, f"Script '{full_path.name}' failed ({result.returncode}): {result.stderr.strip()[:200]}"

        elif action_type == "send-alert":
            message = params.get("message", "Webhook Alert")
            # Format with event data
            try:
                message = message.format(**event_data)
            except (KeyError, ValueError):
                pass
            # Print alert to stdout (can be piped, logged, or caught by monitoring)
            alert_line = f"[ALERT] {ts} | {message}"
            print(alert_line, flush=True)
            return True, f"Alert sent: {message[:200]}"

        elif action_type == "restart-service":
            service = params.get("name", "")
            if not service:
                return False, "No service name specified"
            # On Windows, use taskkill + start; on Linux use systemctl
            if sys.platform == "win32":
                kill_cmd = ["taskkill", "/F", "/IM", service, "/T"]
                subprocess.run(kill_cmd, capture_output=True, timeout=10)
                time.sleep(1)
                start_cmd = ["start", "", service]
                subprocess.run(start_cmd, capture_output=True, timeout=10, shell=True)  # noqa:SEC "start" is a cmd builtin, service name is static
            else:
                subprocess.run(["systemctl", "restart", service], capture_output=True, timeout=30)
            return True, f"Restart issued for '{service}'"

        elif action_type == "log-event":
            data = params.get("data", event_data.get("event_type", "unknown"))
            return True, f"Logged: {str(data)[:200]}"

        else:
            return False, f"Unknown action type: {action_type}"

    except subprocess.TimeoutExpired:
        return False, "Action timed out after 60s"
    except Exception as e:
        return False, f"Action error: {e}"


def process_event(event_type, event_data):
    """Process an incoming event against all rules."""
    state = load_state()
    state["total_events"] += 1

    event_entry = {
        "ts": timestamp(),
        "event_type": event_type,
        "data": event_data,
    }
    append_log(state, "events", event_entry)

    rules = load_rules()
    matched_actions = []

    for rule in rules:
        # Check event type match
        rule_event = rule.get("event", "")
        if rule_event != event_type and rule_event != "*":
            continue
        # Check condition
        condition = rule.get("condition", {})
        if not evaluate_condition(condition, event_data):
            continue
        # Execute action
        action_def = rule.get("action", {})
        if isinstance(action_def, str):
            # Shorthand: convert string to {"type": string}
            action_def = {"type": action_def}
        success, result = execute_action(action_def, event_data)

        action_entry = {
            "ts": timestamp(),
            "rule": rule.get("id", "unknown"),
            "event_type": event_type,
            "action": action_def,
            "success": success,
            "result": result,
        }
        state["total_actions"] += 1
        append_log(state, "actions", action_entry)
        matched_actions.append(action_entry)

        if not success:
            state["total_errors"] += 1
            append_log(state, "errors", {
                "ts": timestamp(),
                "rule": rule.get("id", "unknown"),
                "error": result,
            })

    save_state(state)
    return matched_actions


# ── HTTP Server ──────────────────────────────────────────────────────────────

class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhook endpoints."""

    def log_message(self, format, *args):
        """Quiet logging — skip default stderr noise."""
        pass

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw.decode("utf-8", errors="replace")}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/health":
            self._send_json(200, {
                "status": "ok",
                "service": "webhook-engine",
                "ts": timestamp(),
                "uptime_seconds": int(time.time() - server_start_time),
            })
        elif path == "/rules":
            rules = load_rules()
            self._send_json(200, {"count": len(rules), "rules": rules})
        elif path == "/state":
            state = load_state()
            self._send_json(200, state)
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/webhook/"):
            name = path[len("/webhook/"):]
            if not name:
                self._send_json(400, {"error": "Missing webhook name"})
                return
            body = self._read_body()
            # Merge event type from URL
            event_data = {
                "webhook_name": name,
                **body,
            }
            # Determine event type
            event_type = body.get("event", body.get("event_type", name))
            matched = process_event(event_type, event_data)
            self._send_json(200, {
                "status": "received",
                "event_type": event_type,
                "webhook_name": name,
                "matched_rules": len(matched),
                "actions": matched,
            })
        elif path == "/webhook":
            body = self._read_body()
            event_type = body.get("event", body.get("event_type", "generic"))
            event_data = {**body}
            matched = process_event(event_type, event_data)
            self._send_json(200, {
                "status": "received",
                "event_type": event_type,
                "matched_rules": len(matched),
                "actions": matched,
            })
        else:
            self._send_json(404, {"error": "Not found"})

    do_PUT = do_POST

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ── Server lifecycle ─────────────────────────────────────────────────────────

server_start_time = 0.0
server = None
server_thread = None


def start_server():
    global server, server_thread, server_start_time

    # Check lock
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            # Check if process is still alive (Windows-friendly)
            if sys.platform == "win32":
                check = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                                       capture_output=True, timeout=5)
                tasklist_out = (check.stdout or b"").decode("cp1252", errors="replace")
                if str(pid) in tasklist_out:
                    print(f"Server already running (PID {pid}) on port {PORT}")
                    return
            else:
                try:
                    os.kill(pid, 0)  # signal 0 = existence check
                    print(f"Server already running (PID {pid}) on port {PORT}")
                    return
                except OSError:
                    pass
        except (ValueError, OSError, subprocess.TimeoutExpired):
            pass
        # Stale lock — remove
        LOCK_FILE.unlink(missing_ok=True)

    server_start_time = time.time()
    server = HTTPServer((HOST, PORT), WebhookHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Write PID lock
    LOCK_FILE.write_text(str(os.getpid()))

    print(f"✓ Webhook Engine started on http://{HOST}:{PORT}")
    print(f"  Rules: {RULES_FILE}")
    print(f"  State: {STATE_FILE}")
    print(f"  PID:   {os.getpid()}")
    print("  Endpoints:")
    print("    POST /webhook/<name>  — Receive webhook events")
    print("    POST /webhook         — Receive generic event")
    print("    GET  /health          — Health check")
    print("    GET  /rules           — List rules")
    print("    GET  /state           — Show state")
    print("")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
        LOCK_FILE.unlink(missing_ok=True)
        print("Stopped.")


def check_health():
    """Quick health check via HTTP."""
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "ok":
                print(f"✓ Webhook Engine is RUNNING on port {PORT}")
                print(f"  Uptime: {data.get('uptime_seconds', '?')}s")
                return True
    except Exception as e:
        print(f"✗ Webhook Engine is NOT running ({e})")
    return False


# ── CLI commands ─────────────────────────────────────────────────────────────

def cmd_start():
    start_server()


def cmd_add_rule(json_str):
    rules = load_rules()
    try:
        rule = json.loads(json_str) if isinstance(json_str, str) else json_str
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON — {e}")
        return 1

    # Validate required fields
    if "event" not in rule:
        print("Error: Rule must have an 'event' field")
        return 1
    if "action" not in rule:
        print("Error: Rule must have an 'action' field")
        return 1

    # Generate ID if not provided
    if "id" not in rule:
        rule["id"] = f"rule-{len(rules) + 1}-{int(time.time())}"

    # Normalize action to dict
    if isinstance(rule["action"], str):
        rule["action"] = {"type": rule["action"]}

    rules.append(rule)
    save_rules(rules)
    print(f"✓ Rule added [{rule['id']}]: event={rule['event']}, action={rule['action']['type']}")
    return 0


def cmd_list_rules():
    rules = load_rules()
    if not rules:
        print("No rules defined.")
        return
    print(f"Rules ({len(rules)}):")
    print("─" * 60)
    for i, rule in enumerate(rules, 1):
        action_type = rule.get("action", {}).get("type", rule.get("action", "?"))
        cond = rule.get("condition", {})
        cond_str = f" when {json.dumps(cond)}" if cond else ""
        print(f"  {i}. [{rule.get('id', '?')}]")
        print(f"     Event: {rule.get('event', '*')}{cond_str}")
        print(f"     Action: {action_type} → {json.dumps(rule.get('action', {}))}")
        print()


def cmd_log():
    state = load_state()
    events = state.get("events", [])
    actions = state.get("actions", [])
    errors = state.get("errors", [])

    print(f"Webhook Engine Log (last {MAX_LOG} entries)")
    print(f"  Total events:  {state.get('total_events', 0)}")
    print(f"  Total actions: {state.get('total_actions', 0)}")
    print(f"  Total errors:  {state.get('total_errors', 0)}")
    print()

    if errors:
        print("── Errors ──")
        for e in errors[-5:]:
            print(f"  [{e.get('ts', '?')}] rule={e.get('rule', '?')} → {e.get('error', '?')}")
        print()

    if actions:
        print("── Recent Actions ──")
        for a in actions[-10:]:
            mark = "✓" if a.get("success") else "✗"
            print(f"  {mark} [{a.get('ts', '?')}] event={a.get('event_type', '?')} "
                  f"action={a.get('action', {}).get('type', '?')} → {a.get('result', '?')[:120]}")
        print()

    if events:
        print("── Recent Events ──")
        for e in events[-10:]:
            data_str = json.dumps(e.get("data", {}), ensure_ascii=False)
            print(f"  [{e.get('ts', '?')}] type={e.get('event_type', '?')} data={data_str[:150]}")


def cmd_remove_rule(rule_id):
    rules = load_rules()
    before = len(rules)
    rules = [r for r in rules if r.get("id") != rule_id]
    if len(rules) < before:
        save_rules(rules)
        print(f"✓ Rule removed: {rule_id}")
    else:
        print(f"Rule not found: {rule_id}")
    return 0


def cmd_clear_log():
    state = {
        "events": [],
        "actions": [],
        "errors": [],
        "total_events": 0,
        "total_actions": 0,
        "total_errors": 0,
    }
    save_state(state)
    print("✓ Log cleared")


# ── Health-check mode (for cron) ─────────────────────────────────────────────

def cmd_health_check():
    """Non-interactive health check for cron. Exits 0 if running, 1 if not."""
    if check_health():
        sys.exit(0)
    else:
        sys.exit(1)


# ── Helper: auto-restart server if not running (cron mode) ───────────────────

def cmd_ensure_running():
    """Cron helper: check health and restart if down."""
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "ok":
                print(f"✓ Webhook Engine is running (uptime: {data.get('uptime_seconds', '?')}s)")
                return
    except Exception:
        pass
    # Not running — restart
    print(f"✗ Webhook Engine is DOWN. Attempting restart...")
    # Start in background (platform-appropriate)
    script_path = Path(__file__).resolve()
    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP — survives console close,
        # no shell indirection needed (start /B is a cmd builtin, not required here)
        subprocess.Popen([sys.executable, str(script_path), "--start"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x00000008 | 0x00000200)
    else:
        subprocess.Popen(
            [sys.executable, str(script_path), "--start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    print("✓ Restart initiated. Check in 5 seconds...")
    time.sleep(5)
    check_health()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Webhook Engine — Event-Triggered Automation Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --start                          # Start server
  %(prog)s --add-rule '{"event":"git-push","action":"send-alert"}'  
  %(prog)s --add-rule '{"event":"cron-fail","condition":{"job_id":"backup"},"action":{"type":"run-script","path":"notify.py"}}'
  %(prog)s --list-rules                     # List rules
  %(prog)s --log                            # Show log
  %(prog)s --remove-rule rule-1             # Remove a rule by ID
  %(prog)s --clear-log                      # Clear all logs
  %(prog)s --health                         # Quick health check
  %(prog)s --ensure-running                 # Cron: restart if down
        """,
    )
    parser.add_argument("--start", action="store_true", help="Start the webhook server")
    parser.add_argument("--add-rule", type=str, metavar="JSON", help="Add a new rule (JSON string)")
    parser.add_argument("--list-rules", action="store_true", help="List all rules")
    parser.add_argument("--log", action="store_true", help="Show last events/actions/errors")
    parser.add_argument("--remove-rule", type=str, metavar="ID", help="Remove a rule by ID")
    parser.add_argument("--clear-log", action="store_true", help="Clear event log")
    parser.add_argument("--health", action="store_true", help="Check if server is running")
    parser.add_argument("--ensure-running", action="store_true", help="Cron mode: restart if down")

    args = parser.parse_args()

    if args.start:
        cmd_start()
    elif args.add_rule:
        return cmd_add_rule(args.add_rule)
    elif args.list_rules:
        cmd_list_rules()
    elif args.log:
        cmd_log()
    elif args.remove_rule:
        return cmd_remove_rule(args.remove_rule)
    elif args.clear_log:
        cmd_clear_log()
    elif args.health:
        cmd_health_check()
    elif args.ensure_running:
        cmd_ensure_running()
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
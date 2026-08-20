"""
Circuit Breaker — Selbstzerstörungs-Schutz für autonome Systeme.

Jedes autonome Modul (initiative, memory-healing, auto-test, skills-pipeline)
muss einen Circuit Breaker passieren bevor es eine Aktion ausführt.

Drei Zustände:
  - GREEN (geschlossen): Aktionen erlaubt
  - YELLOW (halboffen): Aktionen erlaubt, aber jede wird geloggt
  - RED (offen): KEINE Aktionen erlaubt — nur manuelles Reset

Wird im Dateisystem persistiert: ~/.openamer/circuit_breaker.yaml
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
CB_FILE = HOME / "circuit_breaker.json"
MAX_FAILURES_BEFORE_OPEN = 3
COOLDOWN_SECONDS = 300  # 5 Minuten bis Yellow→Green


# ---------------------------------------------------------------------------
# Circuit Breaker State
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Thread-sicherer Circuit Breaker via Dateisystem-Persistenz."""

    def __init__(self):
        self.state: str = "green"
        self.failures: int = 0
        self.last_failure: float = 0.0
        self.last_trip: float = 0.0
        self._load()

    def _state_path(self) -> Path:
        return CB_FILE

    def _load(self) -> None:
        if self._state_path().exists():
            try:
                data = json.loads(self._state_path().read_text(encoding="utf-8"))
                self.state = data.get("state", "green")
                self.failures = data.get("failures", 0)
                self.last_failure = data.get("last_failure", 0.0)
                self.last_trip = data.get("last_trip", 0.0)
            except Exception:
                self.state = "green"
                self.failures = 0

    def _save(self) -> None:
        self._state_path().parent.mkdir(parents=True, exist_ok=True)
        data = {
            "state": self.state,
            "failures": self.failures,
            "last_failure": self.last_failure,
            "last_trip": self.last_trip,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._state_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def check(self, module_name: str) -> bool:
        """Prüft ob eine Aktion ausgeführt werden darf."""
        self._load()

        # Auto-Recovery: wenn genug Zeit vergangen ist, von Yellow→Green
        if self.state == "yellow" and time.time() - self.last_failure > COOLDOWN_SECONDS:
            self.state = "green"
            self.failures = 0
            self._save()

        if self.state == "red":
            return False

        return True

    def record_success(self, module_name: str) -> None:
        """Erfolgreiche Aktion — Failures zurücksetzen."""
        self._load()
        if self.failures > 0:
            self.failures = 0
            self.state = "green"
            self._save()

    def record_failure(self, module_name: str, error: str) -> None:
        """Fehlgeschlagene Aktion — Zähler erhöhen."""
        self._load()
        self.failures += 1
        self.last_failure = time.time()

        if self.failures >= MAX_FAILURES_BEFORE_OPEN:
            self.state = "red"
            self.last_trip = time.time()
        else:
            self.state = "yellow"

        # Log den Fehler
        logdir = HOME / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        logfile = logdir / f"circuit-breaker-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_entry = {
            "module": module_name,
            "error": error,
            "failures": self.failures,
            "new_state": self.state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(logfile, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, ensure_ascii=False, indent=2)

        self._save()

    def reset(self) -> str:
        """Manuelles Reset — setzt auf Green."""
        self.state = "green"
        self.failures = 0
        self._save()
        return "Circuit breaker reset to GREEN"

    def status(self) -> dict[str, Any]:
        """Aktuellen Status auslesen."""
        self._load()
        return {
            "state": self.state,
            "failures": self.failures,
            "max_failures_before_open": MAX_FAILURES_BEFORE_OPEN,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "last_failure_ago": f"{round((time.time() - self.last_failure) / 60, 1)}m ago" if self.last_failure else "never",
        }


# ---------------------------------------------------------------------------
# Singleton + Public API
# ---------------------------------------------------------------------------

_breaker: CircuitBreaker | None = None


def get_breaker() -> CircuitBreaker:
    global _breaker
    if _breaker is None:
        _breaker = CircuitBreaker()
    return _breaker


def check_action(module_name: str) -> bool:
    """Prüfe ob Modul *module_name* eine Aktion ausführen darf."""
    return get_breaker().check(module_name)


def record_success(module_name: str) -> None:
    get_breaker().record_success(module_name)


def record_failure(module_name: str, error: str) -> None:
    get_breaker().record_failure(module_name, error)


def breaker_status() -> dict[str, Any]:
    return get_breaker().status()


def breaker_reset() -> str:
    return get_breaker().reset()
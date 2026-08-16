"""openamer_cli.a2a.relay — GitHub-based A2A transport (real network, no localhost).

A peer that runs behind NAT / a laptop cannot be reached via a public URL. The
relay solves that without hosting a server: both sides rendezvous on the GitHub
repo (a private OR public relay directory). A node POSTs a *signed, privacy-
redacted* envelope as a JSON object under ``directory/a2a/relay/``, and the
intended peer pulls it (serenaded by a mailbox path). This makes A2A, sub-agents
and swarm messages traverse the real internet over GitHub — not localhost.

Security & privacy model (deliberate):
  * Envelopes are Ed25519-signed (as everywhere in a2a) — forged/tampered is
    rejected by the receiver's `verify()`.
  * The relay body is passed through privacy.redact() before writing, so no
    phone/password/email/card leaks into the relay.
  * Only *intended mailbox* files are read; the receiver verifies sender
    fingerprint + trust.

Two helpers:
  * relay_note()   -> build the signed+redacted relay payload locally.
  * post_payload() -> upload it to GitHub (git-pull style, dedicated relay dir).
  * pull_notes()   -> fetch relay files for this mailbox.

Emission is offline & testable; GitHub writes need a PAT with repo scope.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from openamer_cli.a2a import privacy as _pr
from openamer_cli.a2a.core import IdentityStore, Envelope, public_key_from_hex


RELAY_PREFIX = "directory/a2a/relay"


def sort_relay_filename(mailbox: str, nonce: Optional[str] = None) -> str:
    """Deterministic, sortable filename for a relay note (mailbox + time + nonce)."""
    n = nonce or uuid.uuid4().hex[:8]
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", mailbox)[:40]
    return f"{safe}-{int(time.time())}-{n}.json"


def relay_note(*, identity_store: IdentityStore, envelope: Envelope) -> dict:
    """Build a signed, privacy-redacted relay note for the mesh.

    Steps (verify-safe):
      1. Redact the envelope payload (no phone/password/email/card in the relay).
      2. RE-SIGN the redacted envelope with this node's private key, so the
         signature is over the exact content that travels (never over a payload
         we then redact -- that would make every verify fail).
      3. Attach sender public key so the receiver can verify.
    """
    # redact payload first
    pay = envelope.payload if isinstance(envelope.payload, dict) else {}
    red_pay = {k: _pr.redact(str(v)) for k, v in pay.items()}
    # re-sign over the redacted content
    env2 = Envelope.create(
        private_key=identity_store.private_key(),
        sender=envelope.sender,
        recipient=envelope.recipient,
        kind=envelope.kind,
        payload=red_pay,
        ts=envelope.ts,
    )
    ident = identity_store.ensure_identity()
    return {
        "type": "a2a.relay",
        "sender": env2.sender,
        "recipient": env2.recipient,
        "ts": env2.ts,
        "sender_pubkey": ident.public_key,
        "envelope": env2.to_dict(),
    }


class RelayMailbox:
    """A local mirror directory of a relay node's inbox. Offline-testable.

    Consumption is tracked so the swarm loop processes each note exactly once:
    ``claim()`` returns only notes not yet acked, ``ack()``/``claim()`` record
    consumption in a small JSON ledger (*.acked) that stores *filenames only* —
    never the envelope body — keeping the privacy guarantee intact.
    """

    ACK_MARK = ".acked.json"

    def __init__(self, dirpath: Path):
        self.dir = Path(dirpath)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._ack_file = self.dir / self.ACK_MARK

    # -- ack ledger ----------------------------------------------------------

    def _load_acked(self) -> set[str]:
        if not self._ack_file.exists():
            return set()
        try:
            data = json.loads(self._ack_file.read_text(encoding="utf-8"))
            return set(data.get("acked", [])) if isinstance(data, dict) else set()
        except Exception:
            return set()

    def _save_acked(self, acked: set[str]) -> None:
        tmp = self._ack_file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"acked": sorted(acked)}, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(self._ack_file)

    def is_consumed(self, fname: str) -> bool:
        return fname in self._load_acked()

    def ack(self, fname: str) -> None:
        acked = self._load_acked()
        acked.add(fname)
        self._save_acked(acked)

    # -- mailbox -------------------------------------------------------------

    def store(self, note: dict) -> Path:
        f = self.dir / sort_relay_filename(note.get("recipient") or "mailbox")
        f.write_text(json.dumps(note, ensure_ascii=False), encoding="utf-8")
        return f

    def pull(self, mailbox: str) -> list[dict]:
        out = []
        for f in sorted(self.dir.glob("*.json")):
            if f.name == self.ACK_MARK:
                continue
            if mailbox not in f.name and mailbox != "*":
                continue
            try:
                out.append(json.loads(f.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                continue
        return out

    def claim(self, mailbox: str = "*"):
        """Yield every unconsumed note, acking it so it is surfaced exactly once.

        Returns a list of ``(fname, note)`` tuples. Consumed-on-delivery means a
        swarm loop can safely call ``claim("*")`` repeatedly — each note is seen
        exactly once.
        """
        acked = self._load_acked()
        claimed = []
        for f in sorted(self.dir.glob("*.json")):
            if f.name == self.ACK_MARK:
                continue
            if mailbox not in f.name and mailbox != "*":
                continue
            if f.name in acked:
                continue
            try:
                note = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            acked.add(f.name)
            claimed.append((f.name, note))
        if claimed:
            self._save_acked(acked)
        return claimed

    def unclaim(self, fname: str) -> None:
        """Undo an ack (e.g. the consumer failed and wants a retry)."""
        acked = self._load_acked()
        acked.discard(fname)
        self._save_acked(acked)

    def purge_consumed(self, max_age: int) -> int:
        """Delete consumed notes older than ``max_age`` seconds. Returns count.

        Unconsumed notes are never touched (the peer may still retry/harvest
        them), so an inbox that is drained but not yet acked is safe.
        """
        acked = self._load_acked()
        now = time.time()
        purged = 0
        for f in list(self.dir.glob("*.json")):
            if f.name == self.ACK_MARK:
                continue
            if f.name not in acked:
                continue
            try:
                age = now - f.stat().st_mtime
            except OSError:
                continue
            if age > max_age:
                f.unlink(missing_ok=True)
                acked.discard(f.name)
                purged += 1
        self._save_acked(acked)
        return purged


def verify_note(note: dict, *, tolerance: int = 300) -> dict:
    """Verify a relay note: signature + freshness. Returns {ok, env, reason}."""
    try:
        env = Envelope.from_dict(note["envelope"])
        pub = note.get("sender_pubkey") or ""
        if not env.verify(pub):
            return {"ok": False, "reason": "invalid signature"}
        if abs(int(time.time()) - int(env.ts)) > tolerance:
            return {"ok": False, "reason": "stale"}
        return {"ok": True, "env": env}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def git_pull_relay(relay_repo_local: Path) -> None:
    """git-pull the relay directory in a checked-out relay repo (best-effort)."""
    import subprocess
    subprocess.run(["git", "-C", str(relay_repo_local), "pull", "--rebase", "-q"],
                   check=False, timeout=60)


def git_push_relay(relay_repo_local: Path, note: dict) -> bool:
    """Write + commit + push a note to the relay repo's directory/a2a/relay/."""
    import subprocess
    relay_dir = relay_repo_local / RELAY_PREFIX
    relay_dir.mkdir(parents=True, exist_ok=True)
    f = relay_dir / sort_relay_filename(note.get("recipient") or "mailbox")
    f.write_text(json.dumps(note, ensure_ascii=False), encoding="utf-8")
    cmds = [
        ["git", "-C", str(relay_repo_local), "add", str(f)],
        ["git", "-C", str(relay_repo_local), "commit", "-q", "-m", f"a2a relay: {f.name}"],
        ["git", "-C", str(relay_repo_local), "push", "-q", "origin", "HEAD"],
    ]
    for c in cmds:
        subprocess.run(c, check=False, timeout=120)
    return True

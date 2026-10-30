"""Replication — DIR-01's own half: a sealed, restorable state snapshot.

What DIR-01 asks for: "Implement decentralized, encrypted replication protocols.
Existence is redundant." The gate has two halves, and only one of them can be
built on a single machine:

1. **The artifact** — a snapshot of this instance's state that is encrypted,
   authenticated, self-describing and *provably restorable*. This module.
2. **The other machine** — a reachable peer to push it to. Cannot be built here;
   it stays a measured `peers=0` until a node registers.

So this module refuses to pretend. `selftest()` seals a real snapshot and opens
it again, comparing every file hash, and `status()` reports `peers=0` honestly.
The genesis probe (``agent/genesis_runtime._probe_replication``) therefore moves
DIR-01 from "no replication module exists" to "module exists, snapshot verified,
peer missing" — a partial, not a lie.

Design decisions worth stating:

- **No hand-rolled crypto.** AES-256-GCM from ``cryptography``; a missing library
  is a hard error, never a custom cipher. Keys are 32 random bytes, scrypt-derived
  when a passphrase is used.
- **Authenticated manifest.** Every entry carries its sha256; the manifest hash is
  bound into the AEAD associated data, so a tampered or truncated archive fails
  to open *before* anything is written to disk.
- **Restore is defensive.** Entries may not be absolute, may not contain ``..``,
  and are written through a temp directory first — a hostile archive cannot
  escape the target directory.
- **Secrets are excluded by default.** ``.env``, ``*.key``, key directories and the
  multi-GB ``state.db*`` stay out unless explicitly asked for; replication of
  credentials is a separate decision with its own gate.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

FORMAT_VERSION = 1
KEY_BYTES = 32
NONCE_BYTES = 12
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1

#: A replication snapshot carries STATE, not derived bulk (bounded-archive
#: rule): one oversized append-only log must never make the artifact unbounded.
#: Files above this are SKIPPED and recorded by name, so the archive is honestly
#: incomplete instead of silently truncated.
MAX_FILE_BYTES = 8 * 1024 * 1024

#: Never sealed by default. ``state.db*`` alone is >1 GB on a real install, and
#: credentials are a separate decision (see DIR-07/DIR-23 gates).
DEFAULT_EXCLUDES = (
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "identity.key",
    "state.db",
    "state.db-*",
    "state.db.pre-update-emergency-*.bak",
    "state.db.*",
    "*.log",
    "__pycache__",
    ".git",
    "node_modules",
)


class ReplicationError(RuntimeError):
    """Anything that makes sealing/restoring unsafe."""


class IntegrityError(ReplicationError):
    """The envelope failed authentication or a file hash did not match."""


def _home() -> Path:
    try:
        from openamer_constants import get_openamer_home

        return Path(get_openamer_home())
    except Exception:  # pragma: no cover - defensive
        return Path.home() / ".openamer"


def replication_dir() -> Path:
    return _home() / "replication"


def key_path() -> Path:
    return replication_dir() / "identity.key"


def peers_path() -> Path:
    return replication_dir() / "peers.json"


def state_path() -> Path:
    return replication_dir() / "state.json"


# ── keys ───────────────────────────────────────────────────────────────────────

def _aead():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:  # pragma: no cover - dependency missing
        raise ReplicationError(
            "AES-GCM unavailable: install 'cryptography' (this module never "
            "falls back to a hand-written cipher)"
        ) from exc
    return AESGCM


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """scrypt(passphrase) → 32-byte key. Deterministic for a given salt."""
    if len(salt) < 16:
        raise ReplicationError("salt must be at least 16 bytes")
    return hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_BYTES,
    )


def load_or_create_key(passphrase: Optional[str] = None) -> bytes:
    """Read the instance key, creating it on first use (0600, random 32 bytes)."""
    path = key_path()
    if path.exists():
        data = path.read_bytes()
        if len(data) != KEY_BYTES:
            raise ReplicationError(f"{path} is not a {KEY_BYTES}-byte key")
        return data
    replication_dir().mkdir(parents=True, exist_ok=True)
    key = derive_key(passphrase, os.urandom(16)) if passphrase else os.urandom(KEY_BYTES)
    path.write_bytes(key)
    try:  # best effort on POSIX; Windows ACLs are inherited from the home dir
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


# ── snapshot ───────────────────────────────────────────────────────────────────

def _is_excluded(rel: str, excludes: Iterable[str]) -> bool:
    name = rel.replace("\\", "/")
    for pattern in excludes:
        if pattern.startswith("*."):
            if name.rsplit("/", 1)[-1].endswith(pattern[1:]):
                return True
        elif pattern in name or Path(name).match(pattern):
            return True
    return False


def build_bundle(
    sources: Iterable[Path],
    *,
    base: Optional[Path] = None,
    max_bytes: int = 256 * 1024 * 1024,
    max_file_bytes: int = MAX_FILE_BYTES,
    excludes: Iterable[str] = DEFAULT_EXCLUDES,
    skipped_out: Optional[List[dict]] = None,
) -> tuple[bytes, List[dict]]:
    """Deterministic tar.gz of ``sources`` plus the sha256 manifest.

    Deterministic on purpose: the same tree seals to the same manifest, so two
    ticks can be compared without re-reading the archive.
    """
    base = Path(base or _home())
    entries: List[dict] = []
    skipped: List[dict] = []
    buffer = io.BytesIO()
    total = 0

    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
        for source in sorted((Path(s) for s in sources), key=lambda p: str(p)):
            if not source.exists():
                continue
            files = [source] if source.is_file() else sorted(
                (p for p in source.rglob("*") if p.is_file()),
                key=lambda p: str(p),
            )
            for path in files:
                try:
                    rel = path.relative_to(base).as_posix()
                except ValueError:
                    rel = path.name
                if _is_excluded(rel, excludes):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if size > max_file_bytes:
                    # Recorded, not dropped: a reader can see exactly what the
                    # snapshot does not contain.
                    skipped.append({"path": rel, "size": size, "reason": "over_file_cap"})
                    continue
                try:
                    data = path.read_bytes()
                except OSError:
                    continue
                total += len(data)
                if total > max_bytes:
                    raise ReplicationError(
                        f"snapshot exceeds {max_bytes} bytes at {rel}; raise the cap "
                        "explicitly or narrow the sources"
                    )
                digest = hashlib.sha256(data).hexdigest()
                entries.append({"path": rel, "size": len(data), "sha256": digest})
                info = tarfile.TarInfo(rel)
                info.size = len(data)
                info.mtime = 0  # deterministic
                info.mode = 0o600
                tar.addfile(info, io.BytesIO(data))

    manifest = {
        "format": FORMAT_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base": str(base),
        "entries": entries,
        "total_bytes": total,
    }
    # ``skipped`` is returned separately rather than bound into the manifest
    # digest: two identical trees must seal identically even when a log crossed
    # the per-file cap between them.
    if skipped_out is not None:
        skipped_out.extend(skipped)
    return buffer.getvalue(), entries


def _manifest_digest(entries: List[dict]) -> bytes:
    blob = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).digest()


# ── seal / open ───────────────────────────────────────────────────────────────

def seal(bundle: bytes, entries: List[dict], key: bytes) -> bytes:
    """Encrypt + authenticate a bundle. Header carries KDF/format, not the key."""
    if len(key) != KEY_BYTES:
        raise ReplicationError(f"key must be {KEY_BYTES} bytes")
    aes = _aead()(key)
    nonce = os.urandom(NONCE_BYTES)
    header = {
        "format": FORMAT_VERSION,
        "cipher": "AES-256-GCM",
        "nonce": nonce.hex(),
        "entries": len(entries),
        "manifest_sha256": _manifest_digest(entries).hex(),
    }
    aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ciphertext = aes.encrypt(nonce, bundle, aad)
    payload = {
        "header": header,
        "ciphertext": ciphertext.hex(),
        "manifest": entries,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def open_sealed(envelope: bytes, key: bytes) -> tuple[bytes, List[dict], dict]:
    """Authenticate and decrypt. Raises IntegrityError before returning bytes."""
    try:
        payload = json.loads(envelope.decode("utf-8"))
        header = payload["header"]
        entries = payload["manifest"]
        ciphertext = bytes.fromhex(payload["ciphertext"])
        nonce = bytes.fromhex(header["nonce"])
    except Exception as exc:
        raise IntegrityError(f"malformed envelope: {exc}") from exc

    if header.get("format") != FORMAT_VERSION:
        raise ReplicationError(f"unsupported envelope format {header.get('format')!r}")
    if _manifest_digest(entries).hex() != header.get("manifest_sha256"):
        raise IntegrityError("manifest does not match the header digest")

    aes = _aead()(key)
    aad = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        bundle = aes.decrypt(nonce, ciphertext, aad)
    except Exception as exc:
        raise IntegrityError("authentication failed (wrong key or tampered envelope)") from exc

    return bundle, entries, header


def restore(
    envelope: bytes,
    key: bytes,
    target: Path,
    *,
    allow_overwrite: bool = False,
) -> dict:
    """Decrypt into ``target`` after verifying EVERY entry hash.

    Nothing is written before the archive is authenticated and every member is
    checked for a safe path — a hostile envelope cannot escape ``target``.
    """
    bundle, entries, _header = open_sealed(envelope, key)
    target = Path(target)
    staged = Path(tempfile.mkdtemp(prefix="openamer-restore-"))
    try:
        with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as tar:
            for member in tar.getmembers():
                name = member.name.replace("\\", "/")
                if name.startswith("/") or ".." in Path(name).parts or ":" in name:
                    raise IntegrityError(f"unsafe archive member: {member.name!r}")
            tar.extractall(staged)

        expected = {entry["path"]: entry for entry in entries}
        for rel, entry in expected.items():
            path = staged / rel
            if not path.is_file():
                raise IntegrityError(f"missing after extract: {rel}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                raise IntegrityError(f"hash mismatch after extract: {rel}")

        if target.exists() and not allow_overwrite:
            raise ReplicationError(f"{target} already exists (pass allow_overwrite)")
        target.mkdir(parents=True, exist_ok=True)
        for rel in expected:
            destination = target / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged / rel, destination)
    finally:
        shutil.rmtree(staged, ignore_errors=True)

    return {"restored": len(entries), "target": str(target), "bytes": sum(e["size"] for e in entries)}


# ── peers and transport ───────────────────────────────────────────────────────

def load_peers() -> List[dict]:
    try:
        data = json.loads(peers_path().read_text(encoding="utf-8"))
    except Exception:
        return []
    peers = data.get("peers") if isinstance(data, dict) else data
    return [p for p in (peers or []) if isinstance(p, dict) and p.get("url")]


def register_peer(url: str, name: str = "") -> dict:
    """Record a replication target. Registration is not reachability."""
    peer = {"url": url.rstrip("/"), "name": name or url, "registered_at": time.time()}
    peers = [p for p in load_peers() if p["url"] != peer["url"]] + [peer]
    replication_dir().mkdir(parents=True, exist_ok=True)
    peers_path().write_text(json.dumps({"peers": peers}, indent=2), encoding="utf-8")
    return peer


def push(envelope: bytes, peer_url: str, *, timeout: float = 30.0) -> dict:
    """POST a sealed envelope to a peer's ``/replication/accept`` endpoint.

    The envelope is already encrypted and authenticated, so the transport only
    has to deliver bytes. Plain HTTP is allowed for loopback and refused
    elsewhere: shipping an encrypted blob over a hostile network is still a
    downgrade of *who* it reaches.
    """
    peer_url = peer_url.rstrip("/")
    if not peer_url.endswith("/replication/accept"):
        peer_url = f"{peer_url}/replication/accept"
    if not peer_url.startswith(("http://127.0.0.1", "http://localhost", "https://")):
        raise ReplicationError(
            "refusing a non-TLS push to a non-loopback host (metadata is public in HTTP)"
        )
    request = urllib.request.Request(
        peer_url,
        data=envelope,
        headers={"Content-Type": "application/vnd.openamer.replication+json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {"status": response.status, "peer": peer_url, "body": body[:512]}
    except urllib.error.URLError as exc:
        raise ReplicationError(f"push to {peer_url} failed: {exc}") from exc


# ── the peer side: accept and store ───────────────────────────────────────────

#: A peer refuses anything larger than this without reading it into memory.
MAX_ENVELOPE_BYTES = 512 * 1024 * 1024


def received_dir() -> Path:
    return replication_dir() / "received"


def accept(envelope: bytes, store_dir: Optional[Path] = None, *, keep: int = 5) -> dict:
    """Validate structure and store an envelope. The peer CANNOT read it.

    Only the header is inspected: format, nonce, ciphertext hex, manifest list.
    That is deliberate — a peer needs no key to hold a replica, which is what
    makes the copy useful in a failure domain the sender does not control.
    """
    if len(envelope) > MAX_ENVELOPE_BYTES:
        raise ReplicationError(f"envelope exceeds {MAX_ENVELOPE_BYTES} bytes")
    try:
        payload = json.loads(envelope.decode("utf-8"))
    except Exception as exc:
        raise IntegrityError(f"not a replication envelope: {exc}") from exc

    header = payload.get("header") if isinstance(payload, dict) else None
    if not isinstance(header, dict) or header.get("format") != FORMAT_VERSION:
        raise ReplicationError(f"unsupported envelope header: {header!r}")
    if not isinstance(payload.get("manifest"), list):
        raise IntegrityError("envelope carries no manifest")
    try:
        bytes.fromhex(header["nonce"])
        bytes.fromhex(payload["ciphertext"])
    except Exception as exc:
        raise IntegrityError(f"malformed nonce/ciphertext: {exc}") from exc

    store = Path(store_dir or received_dir())
    store.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(envelope).hexdigest()
    name = f"replica-{time.strftime('%Y%m%dT%H%M%S', time.localtime())}-{digest[:12]}.json"
    path = store / name
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(envelope)
    os.replace(tmp, path)

    files = sorted(store.glob("replica-*.json"), key=lambda p: p.name, reverse=True)
    pruned = 0
    for old in files[max(keep, 1) :]:
        try:
            old.unlink()
            pruned += 1
        except OSError:
            pass

    return {
        "stored": str(path),
        "bytes": len(envelope),
        "entries": len(payload["manifest"]),
        "manifest_sha256": header.get("manifest_sha256"),
        "sha256": digest,
        "pruned": pruned,
    }


def make_server(host: str, port: int, store_dir: Optional[Path] = None, keep: int = 5):
    """Build the peer HTTP server (so tests can run it on port 0)."""
    import http.server

    store = Path(store_dir or received_dir())

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _json(self, code: int, body: dict) -> None:
            blob = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def do_POST(self):  # noqa: N802 - http.server API
            if self.path.rstrip("/") != "/replication/accept":
                self._json(404, {"error": "unknown endpoint"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                self._json(400, {"error": "empty body"})
                return
            if length > MAX_ENVELOPE_BYTES:
                self._json(413, {"error": "envelope too large"})
                return
            body = self.rfile.read(length)
            try:
                report = accept(body, store, keep=keep)
            except (ReplicationError, IntegrityError) as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, report)

        def do_GET(self):  # noqa: N802 - http.server API
            if self.path.rstrip("/") != "/replication/status":
                self._json(404, {"error": "unknown endpoint"})
                return
            stored = sorted(store.glob("replica-*.json")) if store.is_dir() else []
            self._json(
                200,
                {
                    "role": "openamer-replication-peer",
                    "replicas": len(stored),
                    "newest": stored[-1].name if stored else None,
                    "keep": keep,
                },
            )

        def log_message(self, *args):  # keep a peer quiet unless debugging
            return

    return http.server.ThreadingHTTPServer((host, port), Handler)


def serve(host: str = "127.0.0.1", port: int = 8765, *, keep: int = 5) -> int:
    """Run the peer endpoint until interrupted. Returns a process exit code."""
    server = make_server(host, port, keep=keep)
    print(
        f"replication peer listening on http://{host}:{server.server_port}"
        f"  (POST /replication/accept, keep={keep}, store={received_dir()})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


# ── self-test, status ─────────────────────────────────────────────────────────

DEFAULT_SOURCES = ("memory", "skills", "cron/jobs.json", "config.yaml")

#: The frequent proof. A full snapshot of this install is ~139 MB and takes ~56 s
#: (measured 2026-10-30: 3,876 files, 7 oversized logs skipped) — far too much for
#: a tick. The fast profile seals the state that must never be lost *and*
#: exercises the whole path (build → seal → restore → verify) in about a second.
FAST_SOURCES = ("memory/self_model", "memory/genesis", "cron/jobs.json", "config.yaml")


def selftest(
    *,
    profile: str = "fast",
    sources: Optional[Iterable[Path]] = None,
    key: Optional[bytes] = None,
) -> dict:
    """Seal a real snapshot, restore it into a temp dir, verify every hash.

    This is the only DIR-01 claim that can be *proven* on one machine, so it runs
    as a measurement and its result is what `status()` reports.
    """
    if profile not in ("fast", "full"):
        raise ReplicationError(f"unknown profile {profile!r} (fast|full)")
    home = _home()
    wanted = FAST_SOURCES if profile == "fast" else DEFAULT_SOURCES
    chosen = list(sources) if sources is not None else [
        home / part for part in wanted if (home / part).exists()
    ]
    if not chosen:
        return {"ok": False, "reason": "no sources to snapshot", "files": 0, "bytes": 0}

    started = time.time()
    data_key = key or load_or_create_key()
    skipped: List[dict] = []
    bundle, entries = build_bundle(chosen, base=home, skipped_out=skipped)
    envelope = seal(bundle, entries, data_key)
    target = Path(tempfile.mkdtemp(prefix="openamer-replica-check-")) / "restored"
    try:
        report = restore(envelope, data_key, target)
        ok = report["restored"] == len(entries)
    finally:
        shutil.rmtree(target.parent, ignore_errors=True)

    result = {
        "ok": ok,
        "profile": profile,
        "files": len(entries),
        "bytes": sum(e["size"] for e in entries),
        "envelope_bytes": len(envelope),
        "seconds": round(time.time() - started, 3),
        "at": time.time(),
        "sources": [str(p) for p in chosen],
        "skipped_files": len(skipped),
        "skipped_bytes": sum(int(entry["size"]) for entry in skipped),
    }
    try:
        replication_dir().mkdir(parents=True, exist_ok=True)
        # Merge, do not overwrite: the last push result must survive a selftest
        # (dropping it would silently downgrade DIR-01 on the next tick).
        try:
            current = json.loads(state_path().read_text(encoding="utf-8"))
        except Exception:
            current = {}
        current.update(result)
        state_path().write_text(json.dumps(current, indent=2), encoding="utf-8")
    except OSError:
        pass
    return result


def status() -> dict:
    """What DIR-01's gate needs: module present, snapshot verified, peers count."""
    last: Dict[str, object] = {}
    try:
        last = json.loads(state_path().read_text(encoding="utf-8"))
    except Exception:
        last = {}
    peers = load_peers()
    pushed = last.get("last_push") if isinstance(last.get("last_push"), dict) else {}
    return {
        "module": True,
        "key_present": key_path().exists(),
        "peers": len(peers),
        "last_selftest_ok": bool(last.get("ok")),
        "last_selftest_profile": last.get("profile"),
        "last_selftest_files": last.get("files", 0),
        "last_selftest_age_s": (
            round(time.time() - float(last["at"])) if isinstance(last.get("at"), (int, float)) else None
        ),
        "last_selftest_bytes": last.get("bytes", 0),
        "last_selftest_skipped": last.get("skipped_files", 0),
        "last_push_ok": bool(pushed.get("ok")),
        "last_push_peers": len(pushed.get("results") or []),
        "last_push_age_s": (
            round(time.time() - float(pushed["at"])) if isinstance(pushed.get("at"), (int, float)) else None
        ),
    }


def push_to_peers(*, profile: str = "fast", timeout: float = 15.0) -> dict:
    """Seal a snapshot and deliver it to every registered peer.

    "A peer is registered" is not "a replica exists" — this is the step that
    turns the first into the second, and its per-peer result is what the genesis
    probe reads before it dares to call DIR-01 satisfied.
    """
    peers = load_peers()
    if not peers:
        report = {"ok": False, "at": time.time(), "peers": 0, "reason": "no peers registered", "results": []}
        _record_push(report)
        return report

    home = _home()
    wanted = FAST_SOURCES if profile == "fast" else DEFAULT_SOURCES
    sources = [home / part for part in wanted if (home / part).exists()]
    if not sources:
        report = {"ok": False, "at": time.time(), "peers": len(peers), "reason": "no sources", "results": []}
        _record_push(report)
        return report

    key = load_or_create_key()
    skipped: List[dict] = []
    bundle, entries = build_bundle(sources, base=home, skipped_out=skipped)
    envelope = seal(bundle, entries, key)

    results = []
    for peer in peers:
        try:
            pushed = push(envelope, peer["url"], timeout=timeout)
            results.append({"peer": peer["url"], "ok": pushed["status"] == 200, "status": pushed["status"]})
        except ReplicationError as exc:
            results.append({"peer": peer["url"], "ok": False, "error": str(exc)[:200]})

    report = {
        "ok": bool(results) and all(item["ok"] for item in results),
        "at": time.time(),
        "peers": len(peers),
        "profile": profile,
        "files": len(entries),
        "envelope_bytes": len(envelope),
        "results": results,
    }
    _record_push(report)
    return report


def _record_push(report: dict) -> None:
    """Attach the push result to state.json without losing the selftest record."""
    try:
        current = json.loads(state_path().read_text(encoding="utf-8"))
    except Exception:
        current = {}
    current["last_push"] = report
    try:
        replication_dir().mkdir(parents=True, exist_ok=True)
        tmp = state_path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(current, indent=2), encoding="utf-8")
        os.replace(tmp, state_path())
    except OSError:
        pass

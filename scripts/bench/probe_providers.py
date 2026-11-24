#!/usr/bin/env python3
"""Probe every configured LLM provider for real availability.

A configured provider is a claim. This script turns claims into measurements:
  dns        -> does the hostname even resolve?
  reachable  -> does /models or a tiny chat completion answer?
  verdict    -> LIVE | UNAUTHORIZED | NO_KEY | DEAD_DNS | UNREACHABLE | SKIPPED_LOCAL

No secrets are printed. Local endpoints are probed without auth.

Usage:
    python scripts/bench/probe_providers.py
    python scripts/bench/probe_providers.py --chat      # also send a 8-token chat probe
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / "AppData" / "Local" / "openamer-laptop"))
OUT_DIR = HOME / "reports" / "provider-health"

LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


def load_config() -> dict:
    with open(HOME / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve_key(spec: dict) -> tuple[str | None, str]:
    """Return (api_key, source). Never logs the key itself."""
    if spec.get("api_key"):
        return spec["api_key"], "literal"
    env_name = spec.get("key_env") or ""
    if env_name:
        val = os.environ.get(env_name)
        if val:
            return val, f"env:{env_name}"
        return None, f"env-missing:{env_name}"
    return None, "none"


def dns_ok(host: str) -> bool:
    if not host:
        return False
    try:
        socket.getaddrinfo(host, None)
        return True
    except Exception:
        return False


CANARY_HOSTS = ("api.openai.com", "api.anthropic.com", "github.com")


def resolver_canary() -> dict:
    """Is this machine's resolver healthy, or is DNS broken for everything?

    Why this exists: on 2026-11-24T06:16 a probe ran during a resolver outage and
    wrote a report claiming 96 of 100 providers were ``DEAD_DNS``. Twelve hours
    later 56 of those 93 distinct hosts resolved fine from the same machine.

    A *global* DNS failure reported as 96 *individual* provider deaths is a false
    finding, and it is worse than no report because it will be believed -- every
    "local-first vs cloud" decision downstream inherits it. Probing three
    unrelated, near-certainly-alive hostnames separates the two cases: if the
    canaries fail, the instrument is broken, not the providers.
    """
    resolved = [h for h in CANARY_HOSTS if dns_ok(h)]
    return {
        "ok": len(resolved) == len(CANARY_HOSTS),
        "probed": list(CANARY_HOSTS),
        "resolved": resolved,
    }


def http_probe(url: str, key: str | None, timeout: float, chat: bool, model: str) -> dict:
    """Return {status, http, latency_s, detail}."""
    t0 = time.time()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    if chat:
        payload = json.dumps({
            "model": model or "test",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 8,
            "temperature": 0,
        }).encode()
        target = url.rstrip("/") + "/chat/completions"
        req = urllib.request.Request(target, data=payload, headers=headers, method="POST")
    else:
        target = url.rstrip("/") + "/models"
        req = urllib.request.Request(target, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(2000).decode("utf-8", "replace")
            return {
                "http": resp.status,
                "latency_s": round(time.time() - t0, 3),
                "detail": body[:160],
            }
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(400).decode("utf-8", "replace")
        except Exception:
            pass
        return {
            "http": exc.code,
            "latency_s": round(time.time() - t0, 3),
            "detail": f"{exc.reason} {body}"[:200],
        }
    except Exception as exc:
        return {
            "http": None,
            "latency_s": round(time.time() - t0, 3),
            "detail": f"{type(exc).__name__}: {exc}"[:200],
        }


def verdict_for(
    spec: dict,
    key_src: str,
    dns: bool,
    probe: dict,
    keyless: bool = False,
    resolver_ok: bool = True,
) -> str:
    """Classify one provider. The order of the checks is the whole point.

    Measured failure this guards against (2026-11-24): 96 of 100 providers were
    reported ``DEAD_DNS``. 56 of those 93 distinct hosts resolved on a re-check,
    and almost all of the rest had no API key configured -- so the report told the
    operator "your providers do not exist" when the truth was "you have no keys"
    plus a resolver outage. NO_KEY and host-existence are separate facts and are
    now reported separately; the row still carries ``dns`` so nothing is lost.
    """
    host = urlparse(str(spec.get("base_url") or "")).hostname or ""
    if host in LOCAL_HOSTS:
        if probe.get("http") == 200:
            return "LIVE_LOCAL"
        return "LOCAL_DOWN"
    # No key and not advertised as keyless: unusable regardless of DNS. Saying
    # DEAD_DNS here invents a DNS failure that did not happen.
    if not keyless and (key_src == "none" or key_src.startswith("env-missing")):
        return "NO_KEY"
    if not dns:
        # Only blame the provider when the instrument itself is healthy.
        return "DEAD_DNS" if resolver_ok else "RESOLVER_DOWN"
    http = probe.get("http")
    if http == 200:
        return "LIVE"
    if http in (401, 403):
        return "UNAUTHORIZED"
    if http == 404:
        return "REACHABLE_NO_ROUTE"
    if http is None:
        return "UNREACHABLE"
    if key_src.startswith("env-missing"):
        return "NO_KEY"
    return f"HTTP_{http}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", action="store_true", help="send a real 8-token chat probe")
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--only-live", action="store_true", help="print only LIVE verdicts")
    args = ap.parse_args()

    cfg = load_config()
    providers = [p for p in (cfg.get("custom_providers") or []) if isinstance(p, dict)]

    # Which providers does the fallback chain actually use?
    # Chain entries carry a "custom:" prefix that the provider list does not, so
    # the names must be normalised before comparing -- otherwise every chain
    # entry looks unmeasured and the watchdog can never fire.
    chain = []
    for rung in cfg.get("fallback_providers") or []:
        if isinstance(rung, dict):
            prov = str(rung.get("provider", ""))
            chain.append((prov.replace("custom:", ""), rung.get("model", "")))

    rows = []
    # model to use for the chat probe: prefer the model this provider actually
    # serves in the chain. An empty model string makes Ollama and the NPU server
    # answer 404/error, which would look like a dead provider.
    chain_models: dict = {}
    for prov, model in chain:
        chain_models.setdefault(prov, model)
    # Measure the instrument before measuring the subjects.
    resolver = resolver_canary()
    if not resolver["ok"]:
        print(
            "WARNING: resolver canary failed for "
            + ", ".join(h for h in resolver["probed"] if h not in resolver["resolved"])
            + " -- unreachable hosts will be reported as RESOLVER_DOWN, not DEAD_DNS.\n"
        )
    print(f"probing {len(providers)} configured providers (chat={args.chat}) ...\n")
    for spec in providers:
        name = spec.get("name", "?")
        base = str(spec.get("base_url") or "")
        host = urlparse(base).hostname or ""
        key, key_src = resolve_key(spec)
        is_local = host in LOCAL_HOSTS
        d = dns_ok(host) if host else False
        # A key-less REMOTE provider is only worth a call if it claims to be
        # keyless. A LOCAL endpoint never needs a key -- skipping local hosts
        # because key_src == "none" was a bug in the first version of this
        # script and made four running local servers look dead.
        keyless = "keyless" in name.lower() or "free" in name.lower()
        should_probe = bool(base) and (is_local or d)
        if should_probe and (is_local or key or keyless):
            # Local servers frequently implement /chat/completions but not
            # /models -- probing /models made a working Mini-OpenAmer server on
            # :8081 look dead (HTTP 404). Chat-probe local endpoints.
            # Local inference is CPU/NPU bound: under concurrent load a 4B model
            # needs far more than the remote timeout. Measured 2026-11-23: with
            # only 1 GB RAM free a healthy NPU server needed >12 s to answer and
            # was wrongly reported LOCAL_DOWN. Give local endpoints their own
            # budget so load is reported as slow, not as dead.
            local_timeout = max(args.timeout, 90.0)
            probe = http_probe(base, key, local_timeout if is_local else args.timeout,
                               args.chat or is_local, chain_models.get(name, ""))
        else:
            probe = {"http": None, "latency_s": None, "detail": "not probed (no key / no dns)"}
        v = verdict_for(spec, key_src, d, probe, keyless, resolver["ok"])
        rows.append({
            "provider": name,
            "base_url": base,
            "host": host,
            "dns": d,
            "key_source": key_src,
            "http": probe.get("http"),
            "latency_s": probe.get("latency_s"),
            "verdict": v,
            "detail": probe.get("detail"),
            "in_fallback_chain": any(p == name for p, _ in chain),
        })
        if args.only_live and not v.startswith("LIVE"):
            continue
        lat = f"{probe.get('latency_s'):>6.2f}s" if probe.get("latency_s") else "     -  "
        flag = "*" if any(p == name for p, _ in chain) else " "
        print(f"{flag} {v:<20} {lat} {name[:38]:<40} {probe.get('detail','')[:60]}")

    counts: dict = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    live = [r for r in rows if r["verdict"].startswith("LIVE")]
    remote = [r for r in rows if r.get("host") not in LOCAL_HOSTS]
    result = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "chat_probe": args.chat,
        # Instrument health comes first: a reader must be able to tell whether a
        # DEAD_DNS row means "provider gone" or "my resolver was down".
        "resolver_ok": resolver["ok"],
        "resolver_canary": resolver,
        "configured_providers": len(providers),
        "fallback_chain_entries": len(chain),
        "verdict_counts": counts,
        "hosts_total": len(remote),
        "hosts_dns_resolvable": sum(1 for r in remote if r.get("dns")),
        "providers_without_key": sum(
            1 for r in rows if str(r.get("key_source", "")).startswith("env-missing")
            or r.get("key_source") == "none"
        ),
        "live_providers": [r["provider"] for r in live],
        "rows": rows,
    }
    # Freshness is part of the measurement: a stale file must announce itself.
    result["report_age_hours"] = 0.0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT_DIR / f"provider-health-{stamp}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("\n--- verdicts ---")
    for k in sorted(counts):
        print(f"  {k:<22} {counts[k]}")
    print(f"\nlive: {len(live)} / {len(providers)} configured")
    print(f"result: {OUT_DIR / 'latest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

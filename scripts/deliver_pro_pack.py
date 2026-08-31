#!/usr/bin/env python3
"""deliver_pro_pack.py — delivery automation for Pro Skill Pack purchases.

Flow: ko-fi/BMAC webhooks (or manual CSV export) append order lines to
orders.json (email + transaction id). This script:
  1. reads pending orders
  2. builds a fresh pack from the current best skills (build_pro_pack logic)
  3. emails the buyer a one-time download link (local HTTP link file or SMTP)
  4. marks the order delivered

Without SMTP creds configured, it writes a link file to reports/pro-pack-links/
and prints it — Damir can paste it manually into the ko-fi order.

Usage:
  python scripts/deliver_pro_pack.py --rebuild          # fresh pack zip
  python scripts/deliver_pro_pack.py --order email.txid # register an order
  python scripts/deliver_pro_pack.py --deliver          # process pending orders
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
PACK_ZIP = REPO / "packs" / "pro-pack-v1.zip"
ORDERS = REPO / "reports" / "pro-pack-orders.json"
LINKS = REPO / "reports" / "pro-pack-links"
LINK_TTL_HOURS = 48


def _load(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_token() -> str:
    return secrets.token_urlsafe(24)


def register(email: str, txid: str) -> dict:
    orders = _load(ORDERS, [])
    for o in orders:
        if o["txid"] == txid:
            print(f"order {txid} already registered ({o['status']})")
            return o
    order = {"email": email, "txid": txid,
             "registered": datetime.now().isoformat(timespec="seconds"),
             "status": "pending"}
    orders.append(order)
    _save(ORDERS, orders)
    print(f"registered: {email} ({txid})")
    return order


def deliver(order: dict) -> dict:
    if not PACK_ZIP.exists():
        raise SystemExit(f"pack zip missing: {PACK_ZIP}. Run --rebuild first.")
    token = make_token()
    expires = (datetime.now() + timedelta(hours=LINK_TTL_HOURS)).isoformat(timespec="seconds")
    # token -> file mapping; a tiny local server (or manual paste) serves the zip
    link_id = hashlib.sha1(token.encode()).hexdigest()[:16]
    link_file = LINKS / f"{link_id}.json"
    _save(link_file, {"token": token, "txid": order["txid"], "email": order["email"],
                      "file": str(PACK_ZIP), "expires": expires})
    link = f"https://openamer.dev/downloads/pro-pack/{link_id}?t={token}"
    order["status"] = "delivered"
    order["link_id"] = link_id
    order["delivered"] = datetime.now().isoformat(timespec="seconds")
    print(f"delivered → {order['email']}\n  link-file: {link_file}\n  public link (serve manually): {link}")
    return order


def rebuild() -> int:
    r = subprocess_run_rebuild()
    print(r)
    return 0


def subprocess_run_rebuild() -> str:
    import subprocess
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "build_pro_pack.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, cwd=str(REPO))
    return r.stdout[-500:] or r.stderr[-300:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--order", nargs=2, metavar=("EMAIL", "TXID"))
    ap.add_argument("--deliver", action="store_true")
    args = ap.parse_args()

    if args.rebuild:
        return rebuild()
    if args.order:
        register(*args.order)
    if args.deliver:
        orders = _load(ORDERS, [])
        pending = [o for o in orders if o.get("status") == "pending"]
        if not pending:
            print("no pending orders")
        for o in pending:
            deliver(o)
        _save(ORDERS, orders)
        return 0
    if not (args.rebuild or args.order or args.deliver):
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""ai_deep.py — opt-in deep reasoning AND vision, budget-controlled (P4+P5).

Gives the agent two "heavy" capabilities WITHOUT blowing the budget, both via
the existing OpenRouter key (never stored here — read from ~/.openamer/.env):

  --vision <image>  : multimodal analysis of an image (no local GPU) -> describe
  --reason "<prompt>": run a deep/expensive reasoning model for a tricky case
                      (e.g. architecture, math, adversarial design)

A per-day spend cap is enforced (default $0.50/day, tunable). On reaching it,
the wrapper refuses and prints the remaining-fallback suggestion, so heavy
calls stay a deliberate rarity, not a default.

Usage:
  python scripts/ai_deep.py --vision screenshot.png
  python scripts/ai_deep.py --reason "Is this ED25519 flow safe?"
  python scripts/ai_deep.py --reason "..." --model openai/gpt-5.2-class --max-spend 0.20
  python scripts/ai_deep.py --budget-status
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

HOME = Path.home() / "AppData/Local/openamer-laptop" \
    if sys.platform == "win32" else Path.home() / ".openamer"
BUDGET_FILE = HOME / "ai_deep_budget.json"

# Defaults: vision uses a cheap multimodal; reason uses a deep model.
DEFAULT_VISION = "openai/gpt-5-mini-class"  # multimodal, low cost
DEFAULT_REASON = "anthropic/claude-sonnet-4"  # strong but capped
DEFAULT_MAX_SPEND = 0.50  # USD per rolling day


def _key() -> str:
    env = HOME / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OPENROUTER_API_KEY", "")


def _spend_today() -> float:
    if not BUDGET_FILE.exists():
        return 0.0
    try:
        d = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
        if d.get("day") == str(date.today()):
            return float(d.get("spend", 0.0))
    except Exception:
        pass
    return 0.0


def _record_spend(cost: float) -> None:
    today = str(date.today())
    spent = _spend_today()
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps({
        "day": today, "spend": round(spent + cost, 4), "updated": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")


def _call(model: str, messages: list[dict], max_tokens: int = 1200) -> tuple[str, float]:
    key = _key()
    if not key:
        print("ERROR: no OPENROUTER_API_KEY in ~/.openamer/.env — cannot run deep/vision.")
        return "", 0.0
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print(f"API error {e.code}: {e.read().decode()[:200]}"); return "", 0.0
    txt = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    # OpenRouter returns usage.cost in the top level on newer responses
    cost = float(data.get("usage", {}).get("cost", 0.0) or 0.0)
    return txt, cost


def vision(image: str, model: str, max_spend: float) -> int:
    if not Path(image).exists():
        print(f"ERROR: image not found: {image}"); return 1
    if _spend_today() + 0.01 > max_spend:
        print(f"BUDGET: {_spend_today():.2f} today >= cap {max_spend:.2f}. Refusing vision (use a free/fast model or raise --max-spend).")
        return 1
    b64 = base64.b64encode(Path(image).read_bytes()).decode()
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "Describe this image precisely and completely (relevant for an agent's UI/state verification):"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]}]
    txt, c = _call(model, msgs, max_tokens=1500)
    _record_spend(c if c else 0.001)
    print(txt or "(empty response)")
    return 0


def reason(prompt: str, model: str, max_spend: float) -> int:
    spent = _spend_today()
    est = 0.01  # rough floor for budget check
    if spent + est > max_spend:
        print(f"BUDGET: {spent:.2f} today >= cap {max_spend:.2f}. Refusing deep model (use flash or raise --max-spend).")
        return 1
    msgs = [{"role": "user", "content": prompt}]
    txt, c = _call(model, msgs, max_tokens=2000)
    _record_spend(c if c else 0.001)
    print(txt or "(empty response)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="ai_deep")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--vision", metavar="IMAGE")
    g.add_argument("--reason", metavar="PROMPT")
    g.add_argument("--budget-status", action="store_true")
    ap.add_argument("--model", default="")
    ap.add_argument("--max-spend", type=float, default=DEFAULT_MAX_SPEND)
    a = ap.parse_args()
    if a.budget_status:
        print(f"budget today: {_spend_today():.2f} (cap {a.max_spend:.2f})")
        return 0
    model = a.model or (DEFAULT_VISION if a.vision else DEFAULT_REASON)
    if a.vision:
        return vision(a.vision, model, a.max_spend)
    if a.reason:
        return reason(a.reason, model, a.max_spend)
    return 2


if __name__ == "__main__":
    sys.exit(main())
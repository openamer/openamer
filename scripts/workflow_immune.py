#!/usr/bin/env python3
"""
OpenAmer Workflow Immune System (WIS)
=====================================
The invention: UI-level workflows WITHOUT API integrations - with self-healing.

Concept:
  1. REGISTER   - Register a workflow: name + steps (URL + CSS/XPath selectors).
                  WIS takes a baseline DOM fingerprint of every step.
  2. CHECK      - Nightly via cron: run all workflows against the real website.
                  Per step: does the selector still exist? DOM similarity ok?
  3. HEAL       - On drift: search the page for the target element
                  (selector tokens, text, role, class vocabulary) -> learn a new
                  selector -> patch the workflow automatically -> heal report.

v2.5: End-to-end actions. Steps can type text, click, and assert text/URL.
      When an action fails mid-flow, WIS heals the selector and RETRIES the
      action in the same run.

No APIs, no third-party keys, no SaaS. Runs locally via Chrome CDP :9222.
This is what Zapier/RPA can never have: UI-level automation with an immune system.

Usage:
  workflow_immune.py register <name> <url> <selector> [<selector> ...]
  workflow_immune.py register <name> <url> --json '<steps-json-array>'
  workflow_immune.py check [name] [--no-heal]
  workflow_immune.py list

Step JSON fields:
  selector                CSS selector (required)
  action                  check | type | click | assert_text | assert_url (default: check)
  text                    text for type / assert_text
  contains                substring for assert_url
  role                    optional ARIA role hint for healing

Exit codes: 0 = all healthy/healed, 1 = usage error, 2 = unresolved drift.
"""
import base64
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\workflow-immune")
WORKFLOWS = STATE_DIR / "workflows.json"
REPORTS = STATE_DIR / "reports"
CDP = "http://localhost:9222"

_id = [0]


def _next_id():
    _id[0] += 1
    return _id[0]


def list_pages():
    return json.loads(urllib.request.urlopen(f"{CDP}/json/list", timeout=5).read())


def connect(target_url_hint=None):
    """Open a FRESH WebSocket to a page target (renderer swaps kill old sockets)."""
    pages = [t for t in list_pages() if t.get("type") == "page"]
    t = None
    if target_url_hint:
        for p in pages:
            if target_url_hint in p.get("url", ""):
                t = p
                break
    if not t:
        t = pages[0] if pages else None
    if not t:
        raise RuntimeError("no page target on :9222")
    import websocket
    return websocket.create_connection(t["webSocketDebuggerUrl"], suppress_origin=True, timeout=12)


def ev(ws, expr, timeout_s=20):
    """Runtime.evaluate with timeout. Caller must reconnect after navigation."""
    mid = _next_id()
    ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            if msg.get("result", {}).get("exceptionDetails"):
                return {"__exc__": str(msg["result"]["exceptionDetails"])[:200]}
            return msg.get("result", {}).get("result", {}).get("value")
    return {"__timeout__": True}


def navigate(url, wait=4):
    """Navigate and return a FRESH connection (renderer process swaps)."""
    try:
        ws = connect()
        ws.send(json.dumps({"id": _next_id(), "method": "Page.navigate", "params": {"url": url}}))
        time.sleep(0.5)
        ws.close()
    except Exception:
        pass
    time.sleep(wait)
    return connect()


def screenshot(ws, name):
    """Save a PNG of the current page; returns path or None."""
    try:
        mid = _next_id()
        ws.send(json.dumps({"id": mid, "method": "Page.captureScreenshot",
                            "params": {"format": "png"}}))
        deadline = time.time() + 15
        while time.time() < deadline:
            msg = json.loads(ws.recv())
            if msg.get("id") == mid:
                p = REPORTS / f"{name}.png"
                p.write_bytes(base64.b64decode(msg["result"]["data"]))
                return str(p)
    except Exception as e:
        print(f"  WARNING: screenshot failed ({str(e)[:60]})")
    return None


# ---------------- Fingerprint & Match ----------------

FINGERPRINT_JS = """
((sel) => {
    const el = document.querySelector(sel);
    if (!el) return {found: false};
    const r = el.getBoundingClientRect();
    let sig = el.tagName.toLowerCase();
    if (el.id) sig += '#' + el.id;
    if (el.className && typeof el.className === 'string')
        sig += '.' + el.className.trim().split(/\\\\s+/).slice(0,3).join('.');
    const parent = el.parentElement;
    return {
        found: true,
        tag: el.tagName.toLowerCase(),
        id: el.id || null,
        cls: typeof el.className === 'string' ? el.className : '',
        text: (el.innerText || el.textContent || '').trim().slice(0, 80),
        rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
        visible: r.width > 0 && r.height > 0,
        dom_path: (() => { let p=[], e=el; while(e && p.length<5){let s=e.tagName.toLowerCase(); if(e.id){s+='#'+e.id; p.unshift(s); break;} s += e.className&&typeof e.className==='string'&&e.className.trim()?'.'+e.className.trim().split(/\\\\s+/)[0]:''; p.unshift(s); e=e.parentElement;} return p.join('>'); })(),
        parent_sig: parent ? (parent.tagName.toLowerCase() + (parent.id?('#'+parent.id):'')) : null,
        child_count: el.children.length,
    };
})(%s)
"""

HEAL_SEARCH_JS = """
((spec) => {
    // DARWIN MODE: each strategy runs ISOLATED and reports which one produced
    // the winning candidate. spec.strategy is one of:
    //   TOKENS | TEXT | ROLE | CLASSES
    const byText = [];
    const push = (el) => { if (el && byText.length < 5 && !byText.includes(el)) byText.push(el); };
    const strat = spec.strategy || 'TOKENS';

    if (strat === 'TOKENS') {
        // Tokens from the DEAD selector (redesigns often keep meaningful ids/names)
        for (const tok of (spec.selector_tokens || [])) {
            document.querySelectorAll(
                `[id*="${tok}" i],[name*="${tok}" i],[placeholder*="${tok}" i],[aria-label*="${tok}" i]`
            ).forEach(push);
            document.querySelectorAll(`[class*="${tok}" i]`).forEach(el => {
                if ((el.tagName||'').toLowerCase() !== 'input') push(el);
            });
            if (byText.length >= 3) break;
        }
    } else if (strat === 'TEXT') {
        // Exact text (only when real text is known - empty string matches everything!)
        const wanted = spec.text_match || '';
        if (wanted && wanted.length > 2) {
            document.querySelectorAll('*').forEach(el => {
                const t = (el.innerText || '').trim();
                if (!t || t.length > 200) return;
                if (t === wanted || t.includes(wanted)) push(el);
            });
        }
    } else if (strat === 'ROLE') {
        if (spec.role) document.querySelectorAll(`[role="${spec.role}"]`).forEach(push);
    } else if (strat === 'CLASSES') {
        if (spec.cls_words && spec.cls_words.length) {
            outer:
            for (const w of spec.cls_words) {
                for (const el of document.querySelectorAll('*')) {
                    const c = (typeof el.className === 'string') ? el.className : '';
                    if (c && c.includes(w)) { push(el); if (byText.length >= 5) break outer; }
                }
            }
        }
    }
    // Best candidate -> build new selector
    // VALIDATION: tag must match baseline + must be visible (no meta/head/hidden!)
    const wantedTag = (spec.tag || '').toLowerCase();
    for (const el of byText) {
        const elTag = (el.tagName || '').toLowerCase();
        if (wantedTag && elTag !== wantedTag) continue;
        if (['meta','head','script','style','link','title'].includes(elTag)) continue;
        const rr = el.getBoundingClientRect ? el.getBoundingClientRect() : {width:1,height:1};
        if (!(rr.width > 0 && rr.height > 0)) continue;
        if (el.id) return {selector: '#'+CSS.escape(el.id), how: 'text->id'};
        let sel = el.tagName.toLowerCase();
        if (typeof el.className === 'string' && el.className.trim()) {
            sel += '.' + el.className.trim().split(/\\\\s+/).slice(0,2).map(c=>CSS.escape(c)).join('.');
        }
        // Uniqueness check
        try { if (document.querySelectorAll(sel).length === 1) return {selector: sel, how: 'rebuilt'}; } catch(e){}
        // nth-of-type path up to a unique selector
        let node = el, path = [];
        while (node && node !== document.body && path.length < 6) {
            let seg = node.tagName.toLowerCase();
            if (node.id) { path.unshift('#'+CSS.escape(node.id)); break; }
            const parent = node.parentElement;
            if (parent) {
                const same = Array.from(parent.children).filter(c=>c.tagName===node.tagName);
                if (same.length > 1) seg += `:nth-of-type(${same.indexOf(node)+1})`;
            }
            path.unshift(seg);
            node = parent;
        }
        const full = path.join(' > ');
        try {
            if (full && document.querySelectorAll(full).length === 1)
                return {selector: full, how: 'path'};
        } catch(e){}
        if (sel) return {selector: sel, how: 'best-effort'};
    }
    return null;
})(%s)
"""


def fingerprint(ws, selector):
    """DOM fingerprint of a selector: found? text? position? visibility?"""
    full_js = FINGERPRINT_JS.replace("%s", json.dumps(selector))
    return ev(ws, full_js)


def heal_search(ws, spec):
    full_js = HEAL_SEARCH_JS.replace("%s", json.dumps(spec))
    return ev(ws, full_js)


# ---------------- Actions (v2.5: end-to-end) ----------------

def run_action(ws, step):
    """Execute a step's action. Returns (ok: bool, detail: dict)."""
    action = step.get("action", "check")
    sel = step.get("selector")

    if action == "type":
        text = step.get("text", "")
        js = ("(function(){const el=document.querySelector(" + json.dumps(sel) + ");"
              "if(!el)return{ok:false};el.scrollIntoView({block:'center'});"
              "el.focus();el.value='';el.dispatchEvent(new Event('input',{bubbles:true}));"
              "return{ok:true}})()")
        r = ev(ws, js)
        if not (isinstance(r, dict) and r.get("ok")):
            return False, {"error": "element not focusable"}
        mid = _next_id()
        ws.send(json.dumps({"id": mid, "method": "Input.insertText",
                            "params": {"text": text}}))
        time.sleep(0.4)
        try:
            ws.recv()
        except Exception:
            pass
        v = ev(ws, "(function(){const el=document.querySelector(" + json.dumps(sel) + ");return el?el.value:null})()")
        ok = isinstance(v, str) and text in v
        return ok, {"value": (v or "")[:40]}

    if action == "click":
        js = ("(function(){const el=document.querySelector(" + json.dumps(sel) + ");"
              "if(!el)return{ok:false};el.scrollIntoView({block:'center'});el.click();"
              "return{ok:true}})()")
        r = ev(ws, js)
        return (isinstance(r, dict) and r.get("ok")), r

    if action == "assert_text":
        want = step.get("text", "")
        body = ev(ws, "document.body.innerText.slice(0, 30000)")
        found = isinstance(body, str) and want in body
        return found, {"expected": want[:50], "found": found}

    if action == "assert_url":
        want = step.get("contains", "")
        u = ev(ws, "window.location.href")
        found = isinstance(u, str) and want in u
        return found, {"url": (u or "")[:80], "expected": want[:50]}

    # Default: presence check
    fp = fingerprint(ws, sel) if sel else None
    ok = bool(fp and fp.get("found"))
    return ok, fp or {}


def heal_selector(ws, wf, i, step, base):
    """Darwin-mode heal: try strategies in epsilon-greedy order (win-rate weighted,
    25% exploration), track every win/loss in strategies.json.
    Returns (new_selector, fix_info) or (None, None)."""
    sel = step["selector"]
    raw_toks = [t.lower() for t in re.split(r"[^a-zA-Z0-9]+", sel)
                if len(t) > 3 and not t.isdigit()]
    spec = {
        "text_match": (base or {}).get("text", ""),
        "role": step.get("role"),
        "tag": (base or {}).get("tag"),
        "cls_words": [w for w in ((base or {}).get("cls", "").split()) if len(w) > 3][:4],
        "selector_tokens": raw_toks[:4],
    }
    order = strategy_order()
    for strat in order:
        spec["strategy"] = strat
        fix = heal_search(ws, spec)
        if not (fix and fix.get("selector")):
            record_strategy(strat, win=False)
            continue
        nf = fingerprint(ws, fix["selector"])
        if not (nf and nf.get("found")):
            record_strategy(strat, win=False)
            continue
        record_strategy(strat, win=True)
        old_sel = sel
        wf["steps"][i]["selector"] = fix["selector"]
        wf["steps"][i][f"healed_from_{datetime.now(timezone.utc).date()}"] = old_sel
        wf["baseline"][str(i)] = nf
        wf["heals"] = wf.get("heals", 0) + 1
        fix = dict(fix)
        fix["strategy"] = strat
        return fix["selector"], {"old": old_sel, "new": fix["selector"],
                                 "how": fix.get("how"), "strategy": strat}
    return None, None


# ---------------- Darwin evolution stats ----------------

STRATEGIES_FILE = STATE_DIR / "strategies.json"
ALL_STRATEGIES = ["TOKENS", "TEXT", "ROLE", "CLASSES"]
EXPLORATION_RATE = 0.25  # epsilon: try underdogs first this often


def load_strategies():
    if STRATEGIES_FILE.exists():
        return json.loads(STRATEGIES_FILE.read_text(encoding="utf-8"))
    return {s: {"wins": 0, "tries": 0} for s in ALL_STRATEGIES}


def record_strategy(name, win):
    stats = load_strategies()
    if name not in stats:
        stats[name] = {"wins": 0, "tries": 0}
    stats[name]["tries"] += 1
    if win:
        stats[name]["wins"] += 1
    STRATEGIES_FILE.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")


def strategy_order():
    """Epsilon-greedy ordering: with p=EXPLORATION_RATE put the least-tried
    strategy first (exploration), otherwise sort by win-rate desc."""
    import random
    stats = load_strategies()
    if random.random() < EXPLORATION_RATE:
        least = min(ALL_STRATEGIES, key=lambda s: stats.get(s, {}).get("tries", 0))
        rest = [s for s in ALL_STRATEGIES if s != least]
        random.shuffle(rest)
        return [least] + rest

    def score(s):
        st = stats.get(s, {"wins": 0, "tries": 0})
        # Laplace-smoothed win rate: (wins+1)/(tries+2) - untried strategies get a chance
        return (st["wins"] + 1) / (st["tries"] + 2)

    return sorted(ALL_STRATEGIES, key=score, reverse=True)


def cmd_darwin():
    """Leaderboard: which healing strategy evolves best?"""
    stats = load_strategies()
    print("DARWIN LEADERBOARD - healing strategy evolution")
    print("=" * 52)
    print(f"{'Strategy':<10} {'Wins':>6} {'Tries':>7} {'Win-rate':>10}  Score")
    rows = []
    for s in ALL_STRATEGIES:
        st = stats.get(s, {"wins": 0, "tries": 0})
        wr = (st["wins"] / st["tries"] * 100) if st["tries"] else 0.0
        score = (st["wins"] + 1) / (st["tries"] + 2)
        rows.append((score, s, st, wr))
    rows.sort(reverse=True)
    for score, s, st, wr in rows:
        bar = "#" * int(score * 20)
        print(f"{s:<10} {st['wins']:>6} {st['tries']:>7} {wr:>9.1f}%  {bar} {score:.3f}")
    print("=" * 52)
    print(f"exploration rate: {EXPLORATION_RATE:.0%} (underdogs get tried first)")
    print("strategies evolve automatically with every nightly heal.")
    return 0


# ---------------- Persistence ----------------

def load_workflows():
    if WORKFLOWS.exists():
        return json.loads(WORKFLOWS.read_text(encoding="utf-8"))
    return {"workflows": {}}


def save_workflows(data):
    REPORTS.mkdir(parents=True, exist_ok=True)
    WORKFLOWS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------- Core operations ----------------

def cmd_register(name, url, steps):
    data = load_workflows()
    ws = navigate(url, wait=5)
    fingerprints = {}
    for i, step in enumerate(steps):
        sel = step["selector"]
        fp = fingerprint(ws, sel)
        if not fp or not fp.get("found"):
            print(f"  x Step {i+1}: '{sel}' NOT found - registration failed")
            ws.close()
            return 1
        fingerprints[str(i)] = fp
        print(f"  + Step {i+1}: {fp['tag']}{'#'+fp['id'] if fp.get('id') else ''} "
              f"visible={fp['visible']} text='{fp['text'][:40]}'")
    ws.close()
    data["workflows"][name] = {
        "url": url,
        "steps": steps,
        "baseline": fingerprints,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "heals": 0,
        "last_status": "registered",
    }
    save_workflows(data)
    print(f"[OK] Workflow '{name}' registered ({len(steps)} steps, baseline saved)")
    return 0


def cmd_check(name=None, heal=True):
    data = load_workflows()
    names = [name] if name else list(data["workflows"].keys())
    if not names:
        print("No workflows registered. First: register <name> <url> <selector> [...]")
        return 1
    overall_rc = 0
    report_lines = []
    for wname in names:
        wf = data["workflows"][wname]
        url = wf["url"]
        print(f"\n[CHECK] '{wname}' -> {url}")
        ws = navigate(url, wait=5)
        drifted = []
        healed = []
        for i, step in enumerate(wf["steps"]):
            key = str(i)
            base = wf["baseline"].get(key)
            sel = step["selector"]
            action = step.get("action", "check")

            ok, detail = run_action(ws, step)
            status = "OK" if ok else f"FAIL ({action})"
            healed_entry = None
            drifted_entry = None

            if not ok and heal:
                # GUARD: only heal when the selector is really dead. If the element
                # still exists, the ACTION failed at app level (JS/React/password
                # manager) - healing would be spurious and could poison the baseline.
                fp_now = fingerprint(ws, sel) if sel else None
                if fp_now and fp_now.get("found"):
                    status = f"FAIL ({action}) - selector alive, no heal attempted"
                    drifted_entry = {"step": i + 1, "selector": sel,
                                     "problem": f"{action} failed (selector alive - app-level)",
                                     "detail": detail}
                else:
                    # Mid-flow healing: selector dead -> heal -> RETRY
                    stamp_sick = f"{wname}_step{i+1}_sick_{datetime.now(timezone.utc).strftime('%H%M%S')}"
                    screenshot(ws, stamp_sick)
                    new_sel, fix = heal_selector(ws, wf, i, step, base)
                    if new_sel:
                        healed_entry = {"step": i + 1, "old": fix["old"], "new": fix["new"],
                                        "how": fix["how"]}
                        step["selector"] = new_sel
                        ok2, detail2 = run_action(ws, step)
                        if ok2:
                            status = f"HEALED+RETRY OK ({fix['how']}): '{fix['old']}' -> '{fix['new']}'"
                        else:
                            status = f"HEALED but action still fails ({fix['how']})"
                            drifted_entry = {"step": i + 1, "selector": new_sel,
                                             "problem": f"retry {action} failed", "detail": detail2}
                    else:
                        drifted_entry = {"step": i + 1, "selector": sel,
                                         "problem": "no replacement found", "detail": detail}
            elif not ok:
                drifted_entry = {"step": i + 1, "selector": sel,
                                 "problem": f"{action} failed", "detail": detail}
            elif action == "check":
                # Soft check: did the text change?
                bt = (base or {}).get("text", "")
                nt = (detail or {}).get("text", "")
                if bt and nt and bt != nt:
                    status = f"TEXT-DRIFT ('{bt[:30]}' -> '{nt[:30]}')"
                    drifted_entry = {"step": i + 1, "type": "text",
                                     "old": bt[:60], "new": nt[:60]}
            if healed_entry:
                healed.append(healed_entry)
            if drifted_entry:
                drifted.append(drifted_entry)
            mark = "[OK]" if status == "OK" else "[HEAL]" if "HEALED" in status else "[DRIFT]"
            print(f"  {mark} Step {i+1} [{action}]: {status}")
            # Brief wait after click/type so navigation/render can follow
            if action in ("click", "type"):
                time.sleep(2)
        ws.close()
        wf["last_status"] = "healthy" if not drifted else ("healed" if healed and not drifted else "drift")
        wf["last_check"] = datetime.now(timezone.utc).isoformat()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rep = REPORTS / f"{wname}_{stamp}.json"
        rep.write_text(json.dumps({
            "workflow": wname, "url": url, "time": wf["last_check"],
            "healthy": not drifted, "healed": healed, "drifted": drifted,
            "screenshots_sick": [h.get("screenshot") for h in healed if h.get("screenshot")],
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Report: {rep.name}")
        report_lines.append({"workflow": wname, "healthy": not drifted, "healed": healed, "drifted": drifted})
        if drifted:
            overall_rc = 2
        save_workflows(data)
    print("\n" + "=" * 50)
    healthy_n = sum(1 for r in report_lines if r["healthy"])
    print(f"IMMUNE REPORT: {healthy_n}/{len(report_lines)} healthy | "
          f"heals: {sum(len(r['healed']) for r in report_lines)} | "
          f"open drifts: {sum(len(r['drifted']) for r in report_lines)}")
    return overall_rc


def cmd_list():
    data = load_workflows()
    if not data["workflows"]:
        print("No workflows registered.")
        return 0
    for name, wf in data["workflows"].items():
        print(f"- {name}: {wf['url']} | {len(wf['steps'])} steps | "
              f"status: {wf.get('last_status')} | heals: {wf.get('heals', 0)} | "
              f"last check: {(wf.get('last_check') or 'never')[:19]}")
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--help":
        print(__doc__)
        return 0
    cmd = args[0]
    if cmd == "register":
        # Variant A: register <name> <url> <sel> [<sel>...]   (presence checks only)
        # Variant B: register <name> <url> --json '<json-array>'  (full actions)
        if len(args) < 4:
            print("register requires: <name> <url> <selector> [...] OR <name> <url> --json '[...]'")
            return 1
        if args[3] == "--json":
            try:
                steps = json.loads(args[4])
                assert isinstance(steps, list) and steps
            except Exception as e:
                print(f"Invalid JSON steps: {e}")
                return 1
        else:
            steps = [{"selector": s} for s in args[3:]]
        return cmd_register(args[1], args[2], steps)
    if cmd == "check":
        heal = "--no-heal" not in args
        rest = [a for a in args[1:] if not a.startswith("--")]
        return cmd_check(rest[0] if rest else None, heal=heal)
    if cmd == "list":
        return cmd_list()
    if cmd == "darwin":
        return cmd_darwin()
    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

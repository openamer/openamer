#!/usr/bin/env python3
"""
OpenAmer Workflow-Immunsystem (Workflow Immune System, WIS)
===========================================================
Die Erfindung: UI-Workflows ohne API-Integrationen - mit Selbstheilung.

Konzept:
  1. REGISTER   - Workflow registrieren: Name + Schritte (URL + CSS/XPath-Selektoren)
                  WIS macht einen Baseline-Snapshot (DOM-Fingerprint pro Schritt).
  2. CHECK      - Nachts via Cron: alle Workflows gegen die echte Website laufen
                  lassen. Pro Schritt: Selektor noch da? DOM-Aehnlichkeit ok?
  3. HEAL       - Bei Abweichung: Seite nach dem Ziel-Element durchsuchen
                  (Text, Rolle, aehnliche Struktur) -> neuen Selektor lernen
                  -> Skill/Workflow automatisch patchen -> Heal-Report mit Diff.

Keine APIs, keine Keys der Ziel-Seiten, kein SaaS. Läuft lokal via Chrome :9222.
Das ist das, was Zapier/RPA prinzipbedingt nie haben: UI-Level mit Immunabwehr.
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
        raise RuntimeError("kein Page-Target an :9222")
    import websocket
    return websocket.create_connection(t["webSocketDebuggerUrl"], suppress_origin=True, timeout=12)


def ev(ws, expr, timeout_s=20):
    """Runtime.evaluate mit Timeout; frische Verbindung nötig nach Navigation."""
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
    """PNG der aktuellen Seite speichern; liefert Pfad oder None."""
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
        print(f"  ⚠️ Screenshot fehlgeschlagen ({str(e)[:60]})")
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
        sig += '.' + el.className.trim().split(/\\s+/).slice(0,3).join('.');
    const parent = el.parentElement;
    return {
        found: true,
        tag: el.tagName.toLowerCase(),
        id: el.id || null,
        cls: typeof el.className === 'string' ? el.className : '',
        text: (el.innerText || el.textContent || '').trim().slice(0, 80),
        rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
        visible: r.width > 0 && r.height > 0,
        dom_path: (() => { let p=[], e=el; while(e && p.length<5){let s=e.tagName.toLowerCase(); if(e.id){s+='#'+e.id; p.unshift(s); break;} s += e.className&&typeof e.className==='string'&&e.className.trim()?'.'+e.className.trim().split(/\\s+/)[0]:''; p.unshift(s); e=e.parentElement;} return p.join('>'); })(),
        parent_sig: parent ? (parent.tagName.toLowerCase() + (parent.id?('#'+parent.id):'')) : null,
        child_count: el.children.length,
    };
})(%s)
"""

HEAL_SEARCH_JS = """
((spec) => {
    const byText = [];
    const push = (el) => { if (el && byText.length < 5 && !byText.includes(el)) byText.push(el); };

    // 0. Tokens aus dem ALTEN Selektor (staerkstes Signal: Redesigns behalten oft
    //    bedeutungsvolle Ids/Namen/Placeholder wie 'login_field' oder 'search')
    for (const tok of (spec.selector_tokens || [])) {
        document.querySelectorAll(
            `[id*="${tok}" i],[name*="${tok}" i],[placeholder*="${tok}" i],[aria-label*="${tok}" i]`
        ).forEach(push);
        // Klassen-Token nur bei nicht-input Elementen
        document.querySelectorAll(`[class*="${tok}" i]`).forEach(el => {
            if ((el.tagName||'').toLowerCase() !== 'input') push(el);
        });
        if (byText.length >= 3) break;
    }

    // 1. Exakter Text (nur wenn wirklich Text bekannt ist)
    const wanted = spec.text_match || '';
    if (wanted && wanted.length > 2) {
        document.querySelectorAll('*').forEach(el => {
            const t = (el.innerText || '').trim();
            if (!t || t.length > 200) return;
            if (t === wanted || t.includes(wanted)) push(el);
        });
    }
    // 2. Rolle/Aria
    if (byText.length === 0 && spec.role) {
        document.querySelectorAll(`[role="${spec.role}"]`).forEach(push);
    }
    // 3. Tag+Klassen-Wortschatz
    if (byText.length === 0 && spec.cls_words && spec.cls_words.length) {
        outer:
        for (const w of spec.cls_words) {
            for (const el of document.querySelectorAll('*')) {
                const c = (typeof el.className === 'string') ? el.className : '';
                if (c && c.includes(w)) { push(el); if (byText.length >= 5) break outer; }
            }
        }
    }
    // Bester Kandidat -> neuen Selektor bauen
    // VALIDIERUNG: Tag muss zum Baseline passen + sichtbar sein (kein meta/head/hidden!)
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
            sel += '.' + el.className.trim().split(/\\s+/).slice(0,2).map(c=>CSS.escape(c)).join('.');
        }
        // Eindeutigkeit pruefen
        try { if (document.querySelectorAll(sel).length === 1) return {selector: sel, how: 'rebuilt'}; } catch(e){}
        // nth-of-type Pfad hoch bis eindeutig
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
    """DOM-Fingerprint eines Selektors: gefunden? Text? Position? Sichtbarkeit?"""
    full_js = FINGERPRINT_JS.replace("%s", json.dumps(selector))
    return ev(ws, full_js)


def heal_search(ws, spec):
    full_js = HEAL_SEARCH_JS.replace("%s", json.dumps(spec))
    return ev(ws, full_js)


# ---------------- Persistenz ----------------

def load_workflows():
    if WORKFLOWS.exists():
        return json.loads(WORKFLOWS.read_text(encoding="utf-8"))
    return {"workflows": {}}


def save_workflows(data):
    REPORTS.mkdir(parents=True, exist_ok=True)
    WORKFLOWS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------- Kern-Operationen ----------------

def cmd_register(name, url, steps):
    data = load_workflows()
    ws = navigate(url, wait=5)
    fingerprints = {}
    for i, step in enumerate(steps):
        sel = step["selector"]
        fp = fingerprint(ws, sel)
        if not fp or not fp.get("found"):
            print(f"  ✗ Schritt {i+1}: '{sel}' NICHT gefunden - Registrierung fehlgeschlagen")
            ws.close()
            return 1
        fingerprints[str(i)] = fp
        print(f"  ✓ Schritt {i+1}: {fp['tag']}{'#'+fp['id'] if fp.get('id') else ''} "
              f"sichtbar={fp['visible']} text='{fp['text'][:40]}'")
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
    print(f"✅ Workflow '{name}' registriert ({len(steps)} Schritte, Baseline gespeichert)")
    return 0


def cmd_check(name=None, heal=True):
    data = load_workflows()
    names = [name] if name else list(data["workflows"].keys())
    if not names:
        print("Keine Workflows registriert. Erst: register <name> <url> <selector> [...]")
        return 1
    overall_rc = 0
    report_lines = []
    for wname in names:
        wf = data["workflows"][wname]
        url = wf["url"]
        print(f"\n🔍 Check '{wname}' -> {url}")
        ws = navigate(url, wait=5)
        drifted = []
        healed = []
        for i, step in enumerate(wf["steps"]):
            key = str(i)
            base = wf["baseline"].get(key)
            sel = step["selector"]
            fp = fingerprint(ws, sel)
            status = "OK"
            if not fp or not fp.get("found"):
                status = "MISSING"
                drift_info = {"step": i + 1, "selector": sel, "problem": "Selektor nicht gefunden"}
                if heal:
                    # Tokens aus dem TOTEN Selektor selbst ('input#login_field_X' -> ['login_field'])
                    raw_toks = [t.lower() for t in re.split(r"[^a-zA-Z0-9]+", sel)
                                if len(t) > 3 and not t.isdigit()]
                    spec = {
                        "text_match": (base or {}).get("text", ""),
                        "role": step.get("role"),
                        "tag": (base or {}).get("tag"),
                        "cls_words": [w for w in ((base or {}).get("cls", "").split()) if len(w) > 3][:4],
                        "selector_tokens": raw_toks[:4],
                    }
                    stamp_sick = f"{wname}_step{i+1}_sick_{datetime.now(timezone.utc).strftime('%H%M%S')}"
                    shot_sick = screenshot(ws, stamp_sick)
                    fix = heal_search(ws, spec)
                    if fix and fix.get("selector"):
                        nf = fingerprint(ws, fix["selector"])
                        if nf and nf.get("found"):
                            old_sel = sel
                            wf["steps"][i]["selector"] = fix["selector"]
                            wf["steps"][i][f"healed_from_{datetime.now(timezone.utc).date()}"] = old_sel
                            wf["baseline"][key] = nf
                            wf["heals"] = wf.get("heals", 0) + 1
                            healed.append({**drift_info, "new_selector": fix["selector"], "how": fix.get("how"),
                                           "new_text": (nf.get("text") or "")[:60],
                                           "screenshot": shot_sick})
                            status = f"HEALED ({fix.get('how')}): '{old_sel}' -> '{fix['selector']}'"
                        else:
                            drifted.append(drift_info)
                            status = "DRIFT (Heal fehlgeschlagen)"
                    else:
                        drifted.append(drift_info)
                        status = "DRIFT (kein Ersatz gefunden)"
                else:
                    drifted.append(drift_info)
            else:
                # Weiche Pruefung: Text geaendert?
                bt = (base or {}).get("text", "")
                nt = fp.get("text", "")
                if bt and nt and bt != nt:
                    status = f"TEXT-DRIFT ('{bt[:30]}' -> '{nt[:30]}')"
                    drifted.append({"step": i + 1, "type": "text",
                                    "old": bt[:60], "new": nt[:60]})
            print(f"  {'✅' if status=='OK' else '🩺' if status.startswith('HEALED') else '⚠️'} "
                  f"Schritt {i+1}: {status}")
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
        print(f"  📄 Report: {rep.name}")
        report_lines.append({"workflow": wname, "healthy": not drifted, "healed": healed, "drifted": drifted})
        if drifted:
            overall_rc = 2
        save_workflows(data)
    print("\n" + "=" * 50)
    healthy_n = sum(1 for r in report_lines if r["healthy"])
    print(f"IMMUNSYSTEM-BERICHT: {healthy_n}/{len(report_lines)} gesund | "
          f"Heilungen: {sum(len(r['healed']) for r in report_lines)} | "
          f"Offene Drifts: {sum(len(r['drifted']) for r in report_lines)}")
    return overall_rc


def cmd_list():
    data = load_workflows()
    if not data["workflows"]:
        print("Keine Workflows registriert.")
        return 0
    for name, wf in data["workflows"].items():
        print(f"- {name}: {wf['url']} | {len(wf['steps'])} Schritte | "
              f"Status: {wf.get('last_status')} | Heilungen: {wf.get('heals', 0)} | "
              f"Letzter Check: {(wf.get('last_check') or 'nie')[:19]}")
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--help":
        print(__doc__)
        print("Usage:")
        print("  workflow_immune.py register <name> <url> <selector> [<selector> ...]")
        print("  workflow_immune.py check [name] [--no-heal]")
        print("  workflow_immune.py list")
        return 0
    cmd = args[0]
    if cmd == "register":
        if len(args) < 4:
            print("register braucht: <name> <url> <selector> [...]")
            return 1
        steps = [{"selector": s} for s in args[3:]]
        return cmd_register(args[1], args[2], steps)
    if cmd == "check":
        heal = "--no-heal" not in args
        name = None
        rest = [a for a in args[1:] if not a.startswith("--")]
        if rest:
            name = rest[0]
        return cmd_check(name, heal=heal)
    if cmd == "list":
        return cmd_list()
    print(f"Unbekannter Befehl: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

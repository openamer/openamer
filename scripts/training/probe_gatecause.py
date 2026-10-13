"""Which gate fires on the current junk rejections? Confirm they are the known
SERP/chrome shapes (normal rotation noise), not a NEW chrome leak.
"""
import importlib.util, sys, json, os
from pathlib import Path

# Portable: OPENAMER_HOME (set by the desktop/cron env), else the standard
# per-user install dir. Never a hardcoded machine path — see
# test_no_hardcoded_paths.py, which guards exactly this.
T = os.path.join(
    os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")),
    "scripts", "training")

spec = importlib.util.spec_from_file_location("il", T + "/internet_learner.py")
m = importlib.util.module_from_spec(spec)
sys.path.insert(0, T)
spec.loader.exec_module(m)
bspec = importlib.util.spec_from_file_location("bs", T + "/buffer_store.py")
bstore = importlib.util.module_from_spec(bspec)
sys.modules["bs"] = bstore
bspec.loader.exec_module(bstore)

rows = [json.loads(l) for l in open(T + "/buffer_junk.jsonl", encoding="utf-8") if l.strip()]
recent = [r for r in rows[-40:] if r["reason"] == "junk"]
print(f"recent junk rows: {len(recent)}\n")

for r in recent:
    a = r["a"]
    print("U:", r["u"][:78])
    print("  serp  :", m._is_serp_snippet(a) if hasattr(m, "_is_serp_snippet") else "?")
    print("  nav   :", m._is_nav_list(a) if hasattr(m, "_is_nav_list") else "?")
    print("  junkRE:", bool(m._JUNK_RE.search(a)) if hasattr(m, "_JUNK_RE") else "?")
    print("  writer:", bstore.is_junk(a))
    print("  glue  :", bstore.is_glued_motif(a))
    segs = a.count(" — ") + a.count("; ")
    print(f"  seps  : em/semicolon={segs} len={len(a)}")
    print("  A:", a[:150].replace("\n", " "))
    print()

print("=== buffer size ===")
n = sum(1 for l in open(T + "/online_buffer.jsonl", encoding="utf-8") if l.strip())
print("online_buffer rows:", n)

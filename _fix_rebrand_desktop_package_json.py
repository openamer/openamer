"""Rebrand apps/desktop/package.json from Hermes to OpenAmer."""
import json
from pathlib import Path

p = Path(r"D:\OpenAmer\apps\desktop\package.json")
data = json.loads(p.read_text(encoding="utf-8"))

data["name"] = "openamer"
data["productName"] = "OpenAmer"
data["description"] = "Native desktop shell for OpenAmer Agent."

def rebrand_str(s):
    if not isinstance(s, str):
        return s
    return s.replace("Hermes", "OpenAmer").replace("hermes", "openamer")

# Rebrand build section fields
build = data.get("build", {})
for key in ["appId", "productName", "executableName", "artifactName", "legalTrademarks", "synopsis"]:
    if key in build:
        build[key] = rebrand_str(build[key])

# Protocols
for proto in build.get("protocols", []):
    proto["name"] = proto["name"].replace("Hermes", "OpenAmer")
    proto["schemes"] = [s.replace("hermes", "openamer") for s in proto["schemes"]]

# mac extendInfo
mac = build.get("mac", {})
extend = mac.get("extendInfo", {})
for k, v in extend.items():
    extend[k] = rebrand_str(v)

# nsis
nsis = build.get("nsis", {})
for key in ["shortcutName", "uninstallDisplayName"]:
    if key in nsis:
        nsis[key] = rebrand_str(nsis[key])

# dmg title
if "dmg" in build:
    build["dmg"]["title"] = rebrand_str(build["dmg"].get("title", ""))

# linux synopsis
if "linux" in build:
    build["linux"]["synopsis"] = rebrand_str(build["linux"].get("synopsis", ""))

# scripts env vars: HERMES_DESKTOP_* -> OPENAMER_DESKTOP_*
scripts = data.get("scripts", {})
new_scripts = {}
for k, v in scripts.items():
    new_v = v.replace("HERMES_DESKTOP_", "OPENAMER_DESKTOP_").replace("hermes", "openamer").replace("Hermes", "OpenAmer")
    new_scripts[k] = new_v
    if k != k.replace("hermes", "openamer"):
        new_scripts[k.replace("hermes", "openamer")] = new_v
        del new_scripts[k]  # Actually we need to handle this more carefully below
data["scripts"] = new_scripts

p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("Rebranded package.json")

#!/usr/bin/env python3
"""
OpenAmer Stealth Browser Plugin — Anti-Detection für agent-browser.
Macht automatisierte Browseranfragen für Websites unsichtbar.
Installiert Preload-Scripte + Chrome Flags + Nutzerprofil.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_DIR = Path(os.environ.get("OPENAMER_REPO",
    r"C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent"))
OPENAMER_HOME = Path(os.environ.get("OPENAMER_HOME",
    r"C:\Users\damir\AppData\Local\openamer-laptop"))
STEALTH_DIR = OPENAMER_HOME / "stealth"
PRELOAD_SCRIPT = STEALTH_DIR / "preload.js"
PROFILE_DIR = STEALTH_DIR / "chrome-profile"
LOG_FILE = STEALTH_DIR / "stealth.log"

def setup():
    """Installiere alle Stealth-Komponenten."""
    STEALTH_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Preload Script schreiben (wird in JEDE Seite injiziert)
    preload = r"""// OpenAmer Stealth Shield — Injected into every page
// Überschreibt alle Headless-Detection-Vektoren
    
// 1. navigator.webdriver — das wichtigste!
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true,
});

// 2. chrome.runtime — fehlt in Headless
if (!window.chrome) window.chrome = {};
if (!window.chrome.runtime) {
    Object.defineProperty(window.chrome, 'runtime', {
        get: () => ({
            id: 'openamer-stealth',
            onMessage: { addListener: () => {} },
            onConnect: { addListener: () => {} },
            sendMessage: () => {},
        }),
        configurable: true,
    });
}

// 3. Plugins — fehlen in Headless-Chrome
const FAKE_PLUGINS = [
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
    { name: 'Native Client', filename: 'internal-nacl-plugin' },
];
if (navigator.plugins.length === 0) {
    const plugins = {
        0: FAKE_PLUGINS[0], 1: FAKE_PLUGINS[1], 2: FAKE_PLUGINS[2],
        length: 3,
        item: i => FAKE_PLUGINS[i] || null,
        namedItem: n => FAKE_PLUGINS.find(p => p.name === n) || null,
        [Symbol.iterator]: function*() { yield* FAKE_PLUGINS; },
    };
    Object.defineProperty(navigator, 'plugins', { get: () => plugins, configurable: true });
}

// 4. MIME Types
if (navigator.mimeTypes.length === 0) {
    const mimeTypes = {
        0: { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
        length: 1,
        item: i => (i === 0 ? mimeTypes[0] : null),
        namedItem: n => (n === 'application/pdf' ? mimeTypes[0] : null),
        [Symbol.iterator]: function*() { yield* [mimeTypes[0]]; },
    };
    Object.defineProperty(navigator, 'mimeTypes', { get: () => mimeTypes, configurable: true });
}

// 5. WebGL — Headless-Chrome zeigt SwiftShader/Google
try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl');
    if (gl) {
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        if (debugInfo) {
            const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
            const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            if (vendor.includes('Google') || renderer.includes('SwiftShader') || 
                vendor.includes('Mesa') || renderer.includes('ANGLE')) {
                const origGetParam = gl.getParameter.bind(gl);
                gl.getParameter = function(p) {
                    if (p === debugInfo.UNMASKED_VENDOR_WEBGL) return 'Intel Inc.';
                    if (p === debugInfo.UNMASKED_RENDERER_WEBGL) return 'Intel(R) Iris(R) Xe Graphics';
                    return origGetParam(p);
                };
            }
        }
    }
} catch(e) {}

// 6. Languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['de-DE', 'de', 'en-US', 'en'],
    configurable: true,
});

// 7. Hardware
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8, configurable: true,
});
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8, configurable: true,
});

// 8. Screen
try {
    Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
    Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
} catch(e) {}

// 9. Permissions — realistische Defaults
try {
    const origQuery = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (desc) => {
        if (['notifications', 'clipboard-read', 'clipboard-write', 'midi',
             'background-sync', 'persistent-storage'].includes(desc.name)) {
            return Promise.resolve({ state: 'prompt', onchange: null });
        }
        return origQuery(desc);
    };
} catch(e) {}

// 10. User-Agent Data — Headless oft falsch
try {
    if (navigator.userAgentData) {
        Object.defineProperty(navigator, 'userAgentData', {
            get: () => ({
                brands: [
                    { brand: 'Chromium', version: '152' },
                    { brand: 'Google Chrome', version: '152' },
                    { brand: 'Not=A?Brand', version: '99' },
                ],
                mobile: false,
                platform: 'Windows',
                getHighEntropyValues: () => Promise.resolve({
                    platform: 'Windows',
                    platformVersion: '15.0.0',
                    architecture: 'x86',
                    model: '',
                    uaFull: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
                }),
            }),
            configurable: true,
        });
    }
} catch(e) {}

console.log('🔒 OpenAmer Stealth Shield aktiv');
"""
    PRELOAD_SCRIPT.write_text(preload, encoding="utf-8")
    print(f"✅ Preload-Script: {PRELOAD_SCRIPT} ({len(preload)} bytes)")
    
    # 2. Chrome-Flags setzen
    chrome_flags = (
        "--disable-blink-features=AutomationControlled "
        "--disable-features=IsolateOrigins,site-per-process "
        "--no-first-run --no-default-browser-check "
        "--window-size=1920,1080 --lang=de-DE "
        f"--user-data-dir={PROFILE_DIR} "
        "--disable-component-update "
        "--disable-background-networking "
        "--disable-sync "
        "--metrics-recording-only "
        "--disable-default-apps "
        "--mute-audio "
        "--no-pings"
    )
    
    # In .env setzen
    env_file = OPENAMER_HOME / ".env"
    env_content = env_file.read_text(encoding="utf-8", errors="replace") if env_file.exists() else ""
    
    # AGENT_BROWSER_ARGS ersetzen oder hinzufügen
    if "AGENT_BROWSER_ARGS" in env_content:
        lines = env_content.split("\n")
        new_lines = []
        for line in lines:
            if line.startswith("AGENT_BROWSER_ARGS="):
                new_lines.append(f"AGENT_BROWSER_ARGS={chrome_flags}")
            else:
                new_lines.append(line)
        env_content = "\n".join(new_lines)
    else:
        env_content += f"\n# OpenAmer Stealth Browser — Anti-Detection\nAGENT_BROWSER_ARGS={chrome_flags}\n"
    
    env_file.write_text(env_content, encoding="utf-8")
    print(f"✅ Chrome-Flags in .env gesetzt")
    
    # 3. Config setzen
    subprocess.run(
        ["openamer", "config", "set", "browser.engine", "chrome"],
        capture_output=True, timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    subprocess.run(
        ["openamer", "config", "set", "browser.inactivity_timeout", "300"],
        capture_output=True, timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    print("✅ Browser-Config aktualisiert (engine=chrome, timeout=300s)")
    
    # 4. Test: Bot Detection Check
    print("\n🔍 Teste Bot-Erkennung...")
    try:
        result = subprocess.run(
            ["agent-browser", "open", "https://webbrowsertools.com/bot-detection/", "--json"],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            print("✅ Browser gestartet")
            # Screenshot für visuelle Bestätigung
            subprocess.run(
                ["agent-browser", "screenshot", STEALTH_DIR / "stealth-test.png", "--json"],
                capture_output=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if (STEALTH_DIR / "stealth-test.png").exists():
                print(f"✅ Screenshot: {STEALTH_DIR / 'stealth-test.png'}")
        else:
            # Test auf sannysoft
            subprocess.run(
                ["agent-browser", "open", "https://bot.sannysoft.com/", "--json"],
                capture_output=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            subprocess.run(
                ["agent-browser", "screenshot", STEALTH_DIR / "stealth-test-sanny.png", "--json"],
                capture_output=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            print(f"✅ Test-Screenshot: {STEALTH_DIR / 'stealth-test-sanny.png'}")
    except Exception as e:
        print(f"⚠ Test: {e}")
    
    print("\n✅ Stealth Setup abgeschlossen!")
    print("ℹ️  Starte OpenAmer neu für volle Wirkung")
    return 0

def check():
    """Prüfe ob Stealth aktiv ist."""
    # Prüfe env
    env_file = OPENAMER_HOME / ".env"
    if env_file.exists():
        content = env_file.read_text()
        if "AGENT_BROWSER_ARGS" in content and "AutomationControlled" in content:
            print("✅ AGENT_BROWSER_ARGS mit Stealth-Flags gesetzt")
        else:
            print("❌ AGENT_BROWSER_ARGS nicht gefunden")
    
    if PRELOAD_SCRIPT.exists():
        print(f"✅ Preload-Script: {PRELOAD_SCRIPT}")
    else:
        print("❌ Kein Preload-Script")
    
    if PROFILE_DIR.exists():
        print(f"✅ Chrome-Profil: {PROFILE_DIR}")
    else:
        print("⚠ Kein Chrome-Profil")
    
    # Prüfe Config
    result = subprocess.run(
        ["openamer", "config", "get", "browser.engine"],
        capture_output=True, text=True, timeout=10,
    )
    print(f"🔧 Browser-Engine: {result.stdout.strip() or 'auto'}")
    
    return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if cmd == "setup":
        sys.exit(setup())
    elif cmd == "check":
        sys.exit(check())
    else:
        print(f"Usage: {sys.argv[0]} [setup|check]")
        sys.exit(1)
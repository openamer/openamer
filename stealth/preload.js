// OpenAmer Stealth Shield v2 — Wird via agent-browser --init-script in JEDE Seite injiziert
// Überschreibt alle Headless-Detection-Vektoren auf Prototype-Ebene

(function() {
    'use strict';
    
    // 1. navigator.webdriver — DAS WICHTIGSTE!
    // Headless: true | Real: undefined
    try {
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });
    } catch(e) {}

    // 2. navigator.userAgent — HeadlessChrome entfernen
    // Headless: "... HeadlessChrome/152.0..." | Real: "... Chrome/152.0..."
    try {
        Object.defineProperty(Navigator.prototype, 'userAgent', {
            get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
            configurable: true,
        });
    } catch(e) {}

    // 3. navigator.plugins — fehlt in Headless
    // Headless: length=0 | Real: length>=3 (PDF, PDF Viewer, Native Client)
    try {
        if (Navigator.prototype.plugins && navigator.plugins.length === 0) {
            const pdfPlugin = { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' };
            const pdfViewer = { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' };
            const naclPlugin = { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' };
            const plugins = [pdfPlugin, pdfViewer, naclPlugin];
            const pluginArray = {
                0: pdfPlugin, 1: pdfViewer, 2: naclPlugin,
                length: 3,
                item: (i) => plugins[i] || null,
                namedItem: (n) => plugins.find(p => p.name === n) || null,
                refresh: () => {},
                [Symbol.iterator]: function*() { yield* plugins; },
            };
            Object.defineProperty(Navigator.prototype, 'plugins', {
                get: () => pluginArray,
                configurable: true,
            });
        }
    } catch(e) {}

    // 4. navigator.mimeTypes — fehlt in Headless
    try {
        if (Navigator.prototype.mimeTypes && navigator.mimeTypes.length === 0) {
            const pdfMime = { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' };
            const mimeArray = {
                0: pdfMime, length: 1,
                item: (i) => i === 0 ? pdfMime : null,
                namedItem: (n) => n === 'application/pdf' ? pdfMime : null,
                [Symbol.iterator]: function*() { yield pdfMime; },
            };
            Object.defineProperty(Navigator.prototype, 'mimeTypes', {
                get: () => mimeArray,
                configurable: true,
            });
        }
    } catch(e) {}

    // 5. chrome.runtime — fehlt in Headless-Chrome
    // Headless: undefined | Real: { id: '...', onMessage: {...}, ... }
    try {
        if (typeof window.chrome === 'undefined') {
            window.chrome = {};
        }
        if (!window.chrome.runtime) {
            window.chrome.runtime = {
                id: 'openamer-stealth',
                onMessage: { addListener: function() {}, removeListener: function() {} },
                onConnect: { addListener: function() {}, removeListener: function() {} },
                onInstalled: { addListener: function() {}, removeListener: function() {} },
                sendMessage: function() {},
                connect: function() {},
            };
        }
    } catch(e) {}

    // 6. navigator.languages
    try {
        Object.defineProperty(Navigator.prototype, 'languages', {
            get: () => ['de-DE', 'de', 'en-US', 'en'],
            configurable: true,
        });
    } catch(e) {}

    // 7. navigator.hardwareConcurrency — Headless oft 4 statt 8+
    try {
        Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {
            get: () => 12,
            configurable: true,
        });
    } catch(e) {}

    // 8. navigator.deviceMemory
    try {
        Object.defineProperty(Navigator.prototype, 'deviceMemory', {
            get: () => 8,
            configurable: true,
        });
    } catch(e) {}

    // 9. navigator.permissions
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

    // 10. navigator.webdriver — NOCHMAL auf dem Prototype (doppelt hält besser)
    try {
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });
    } catch(e) {}

    console.log('🔒 OpenAmer Stealth Shield v2 aktiv');
})();
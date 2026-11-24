// OpenAmer Stealth Browser Server v2
// Startet einen Playwright-Browser mit Stealth-Shield und gibt WS-Endpunkt frei
import { chromium } from 'playwright';
import { writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const STEALTH_DIR = join(__dirname, '..', 'stealth');
const LOCK = join(STEALTH_DIR, 'browser.lock');
const PRELOAD = join(STEALTH_DIR, 'preload.js');

if (!existsSync(STEALTH_DIR)) mkdirSync(STEALTH_DIR, { recursive: true });

const PORT = 9222;

async function main() {
    // WARN: KEIN --user-data-dir hier! launch() akzeptiert das nicht.
    // Für Datenverzeichnis: launchPersistentContext() verwenden.
    const browser = await chromium.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-web-security',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            `--remote-debugging-port=${PORT}`,
        ],
    });

    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
        locale: 'de-DE',
        timezoneId: 'Europe/Berlin',
        permissions: ['geolocation'],
        geolocation: { latitude: 52.52, longitude: 13.405 },
    });

    const page = await context.newPage();
    await page.addInitScript({ path: PRELOAD });

    // CDP-Endpunkt ermitteln
    const cdpUrl = `http://127.0.0.1:${PORT}/json/version`;
    const resp = await fetch(cdpUrl);
    const data = await resp.json();
    const wsEndpoint = data.webSocketDebuggerUrl;

    // browser.process() kann TypeError werfen → try/catch
    let browserPid = null;
    try { browserPid = browser.process()?.pid || null; } catch(e) {}

    const lockData = JSON.stringify({
        pid: process.pid,
        wsEndpoint: wsEndpoint,
        browserPid: browserPid,
        started: new Date().toISOString(),
    });
    writeFileSync(LOCK, lockData, 'utf-8');

    console.log('✅ Stealth Browser gestartet');
    console.log('🔗', wsEndpoint);
    console.log('📋 agent-browser connect', wsEndpoint);

    process.on('SIGINT', async () => { await browser.close(); process.exit(0); });
    process.on('SIGTERM', async () => { await browser.close(); process.exit(0); });

    // Heartbeat alle 5min
    setInterval(async () => {
        try {
            const pages = context.pages();
            if (pages.length === 0) await context.newPage();
        } catch (e) {
            console.error('❌ Browser heartbeat failed:', e.message);
            process.exit(1);
        }
    }, 300000);
}

main().catch(err => {
    console.error('❌ Stealth Server fehlgeschlagen:', err.message, err.stack);
    process.exit(1);
});
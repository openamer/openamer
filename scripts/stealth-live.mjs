#!/usr/bin/env node
/**
 * OpenAmer Stealth — LIVE DEMO
 * 
 * Startet Chrome sichtbar über Playwright und navigiert zu Websites.
 * DU SIEHST ALLES LIVE AUF DEINEM BILDSCHIRM.
 * 
 * Usage: node stealth-live.mjs
 */

import playwright from 'playwright';

const PRELOAD_PATH = 'C:\\Users\\damir\\AppData\\Local\\openamer-laptop\\stealth\\preload.js';
import { readFileSync, existsSync } from 'fs';

async function main() {
  console.log('🖥️  OpenAmer Stealth — LIVE DEMO');
  console.log('   Browser öffnet sich GLEICH! 👀');
  console.log('');

  let preload = '';
  if (existsSync(PRELOAD_PATH)) {
    preload = readFileSync(PRELOAD_PATH, 'utf-8');
  }

  const browser = await playwright.chromium.launch({
    headless: false,
    args: [
      '--no-sandbox',
      '--window-size=1280,800',
    ],
  });

  console.log('✅ Browser-Fenster ist OFFEN!');
  console.log('   Schau auf deinen Desktop...');
  console.log('');

  // GitHub öffnen
  const page = await browser.newPage();
  if (preload) await page.addInitScript(preload);
  
  console.log('🌐 Öffne GitHub...');
  await page.goto('https://github.com/openamer/openamer', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));
  
  console.log('✅ GitHub geladen!');
  console.log('   → Nächste Seite in 3 Sekunden...');
  await new Promise(r => setTimeout(r, 3000));
  
  console.log('🌐 Öffne Product Hunt...');
  await page.goto('https://www.producthunt.com', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));
  
  console.log('✅ Product Hunt geladen!');
  console.log('');
  console.log('🔴 Browser läuft — du siehst alles live!');
  console.log('   Drücke Ctrl+C hier zum Beenden');

  // Am Leben halten
  process.on('SIGINT', async () => {
    console.log('\n🛑 Schließe...');
    await browser.close();
    process.exit(0);
  });
  await new Promise(() => {});
}

main().catch(err => {
  console.error('❌ Fehler:', err.message);
  process.exit(1);
});
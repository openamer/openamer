#!/usr/bin/env node
/**
 * OpenAmer Stealth Browser — VISIBLE MODE
 * 
 * Startet Chrome sichtbar (headless: false) + Vollstealth.
 * Connect via: agent-browser connect <wsEndpoint>
 * 
 * Usage: node stealth-show.mjs
 */

import playwright from 'playwright';

const PRELOAD_PATH = 'C:\\Users\\damir\\AppData\\Local\\openamer-laptop\\stealth\\preload.js';
const LOCK_PATH = 'C:\\Users\\damir\\AppData\\Local\\openamer-laptop\\stealth\\browser.lock';
import { readFileSync, existsSync, writeFileSync, unlinkSync } from 'fs';

async function main() {
  console.log('🖥️  OpenAmer Stealth Browser — SICHTBARER MODUS');
  
  let preload = '';
  if (existsSync(PRELOAD_PATH)) {
    preload = readFileSync(PRELOAD_PATH, 'utf-8');
    console.log(`✅ Preload (${preload.length}b)`);
  }

  const server = await playwright.chromium.launchServer({
    headless: false,          // ← SICHTBAR!
    args: [
      '--no-sandbox',
      '--window-size=1400,900',
      '--window-position=100,50',
      '--disable-blink-features=AutomationControlled',
    ],
  });

  const wsEndpoint = server.wsEndpoint();
  const pid = server.process().pid;

  writeFileSync(LOCK_PATH, JSON.stringify({pid, wsEndpoint, time: new Date().toISOString(), visible: true}));
  
  console.log(`\n✅ Browser sichtbar gestartet (PID ${pid})`);
  console.log(`🔗 ${wsEndpoint}`);
  console.log(`\n📋 Verbinde agent-browser:`);
  console.log(`   agent-browser connect ${wsEndpoint}`);
  console.log(`\n🔴 Browser-Fenster ist OFFEN — du siehst alles live!`);
  console.log(`   Drücke Ctrl+C hier zum Beenden`);

  process.on('SIGINT', () => {
    console.log('\n🛑 Schließe Browser...');
    try { unlinkSync(LOCK_PATH); } catch(e) {}
    server.close().catch(() => process.exit(0));
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    try { unlinkSync(LOCK_PATH); } catch(e) {}
    server.close().catch(() => process.exit(0));
    process.exit(0);
  });

  await new Promise(() => {});
}

main().catch(err => {
  console.error('❌', err.message);
  process.exit(1);
});
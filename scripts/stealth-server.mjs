#!/usr/bin/env node
/**
 * OpenAmer Stealth Browser Server — Playwright launchServer mit addInitScript
 * 
 * Startet einen Chrome-Server mit Vollstealth. Verbinde mit agent-browser connect.
 * 
 * Usage: node stealth-server.mjs
 */

import playwright from 'playwright';

const PRELOAD_PATH = 'C:\\Users\\damir\\AppData\\Local\\openamer-laptop\\stealth\\preload.js';
const LOCK_PATH = 'C:\\Users\\damir\\AppData\\Local\\openamer-laptop\\stealth\\browser.lock';
import { readFileSync, existsSync, writeFileSync, unlinkSync } from 'fs';

async function main() {
  console.log('🚀 OpenAmer Stealth Server');
  
  let preload = '';
  if (existsSync(PRELOAD_PATH)) {
    preload = readFileSync(PRELOAD_PATH, 'utf-8');
    console.log(`✅ Preload (${preload.length}b)`);
  }

  const server = await playwright.chromium.launchServer({
    headless: true,
    args: ['--no-sandbox', '--window-size=1920,1080'],
  });

  const wsEndpoint = server.wsEndpoint();
  const pid = server.process().pid;

  writeFileSync(LOCK_PATH, JSON.stringify({pid, wsEndpoint, time: new Date().toISOString()}));
  
  console.log(`✅ Server PID ${pid}`);
  console.log(`🔗 ${wsEndpoint}`);
  console.log(`\n📋 agent-browser connect ${wsEndpoint}`);

  // On each new context, inject stealth
  if (preload && server.adopt) {
    try {
      const browser = await server.browser();
      browser.on('contextcreated', async (ctx) => {
        try { await ctx.addInitScript(preload); } catch(e) {}
      });
    } catch(e) {
      // non-critical - init on first context manually
    }
  }

  process.on('SIGINT', () => { unlinkSync(LOCK_PATH); server.close(); process.exit(0); });
  process.on('SIGTERM', () => { unlinkSync(LOCK_PATH); server.close(); process.exit(0); });
  await new Promise(() => {});
}

main().catch(err => {
  console.error('❌', err.message);
  process.exit(1);
});
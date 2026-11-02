#!/usr/bin/env node
/**
 * generate-icons.mjs — derive every desktop icon from ONE canonical master.
 *
 * Source of truth: docs/assets/openamer-logo.svg (the OpenAmer DNA mark).
 * The wordmark baked into that SVG is dropped: at 16–32 px (taskbar, favicon,
 * installer) lettering turns to mush, so app icons carry the helix alone.
 *
 * Outputs (all committed, so a normal build needs no browser):
 *   assets/icon.png            512×512 master used by Electron + electron-builder
 *   assets/icon.ico            16/24/32/48/64/128/256 — Windows exe + taskbar
 *   assets/icon.icns           real Apple icon container (was a mislabeled PNG)
 *   public/apple-touch-icon.png 180×180 renderer/apple fallback icon
 *
 * Rendering happens in Chromium and resizing in a canvas, so there is no native
 * image dependency. Run: node scripts/generate-icons.mjs
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { chromium } from '@playwright/test'

const DESKTOP_ROOT = path.resolve(import.meta.dirname, '..')
const MASTER_SVG = path.join(DESKTOP_ROOT, '..', '..', 'docs', 'assets', 'openamer-logo.svg')

const ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
const ICNS_CHUNKS = [
  ['icp4', 16],
  ['icp5', 32],
  ['ic07', 128],
  ['ic08', 256],
  ['ic09', 512],
  ['ic10', 1024]
]

function buildIco(pngs) {
  const header = Buffer.alloc(6)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(pngs.length, 4)

  let offset = header.length + pngs.length * 16
  const entries = []

  for (const { size, png } of pngs) {
    const entry = Buffer.alloc(16)
    entry.writeUInt8(size >= 256 ? 0 : size, 0)
    entry.writeUInt8(size >= 256 ? 0 : size, 1)
    entry.writeUInt8(0, 2)
    entry.writeUInt8(0, 3)
    entry.writeUInt16LE(1, 4)
    entry.writeUInt16LE(32, 6)
    entry.writeUInt32LE(png.length, 8)
    entry.writeUInt32LE(offset, 12)
    entries.push(entry)
    offset += png.length
  }

  return Buffer.concat([header, ...entries, ...pngs.map(p => p.png)])
}

function buildIcns(pngsBySize) {
  const chunks = ICNS_CHUNKS.map(([type, size]) => {
    const png = pngsBySize.get(size)

    if (!png) {
      throw new Error(`missing ${size}px render for ${type}`)
    }

    const head = Buffer.alloc(8)
    head.write(type, 0, 'ascii')
    head.writeUInt32BE(png.length + 8, 4)

    return Buffer.concat([head, png])
  })

  const head = Buffer.alloc(8)
  head.write('icns', 0, 'ascii')
  head.writeUInt32BE(8 + chunks.reduce((n, c) => n + c.length, 0), 4)

  return Buffer.concat([head, ...chunks])
}

function renderSizes(svg) {
  // Drop the wordmark; keep the gradient tile + helix.
  return svg.replace(/<text[\s\S]*?<\/text>/g, '')
}

/** Prefer the Playwright-managed Chromium; fall back to an installed Chrome so
 * icon regeneration works on a machine that never ran `playwright install`. */
async function launchChromium() {
  if (process.env.OPENAMER_CHROME_PATH) {
    return chromium.launch({ executablePath: process.env.OPENAMER_CHROME_PATH })
  }

  try {
    return await chromium.launch()
  } catch {
    return chromium.launch({ channel: 'chrome' })
  }
}

async function main() {
  const svg = renderSizes(readFileSync(MASTER_SVG, 'utf8'))
  const dataUrl = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`
  const wanted = [...new Set([...ICO_SIZES, ...ICNS_CHUNKS.map(([, s]) => s), 512, 180])]

  const browser = await launchChromium()
  const page = await browser.newPage({ viewport: { height: 1024, width: 1024 } })
  await page.setContent('<!doctype html><meta charset="utf-8"><body style="margin:0;background:transparent"></body>')

  const rendered = await page.evaluate(
    async ({ src, sizes }) => {
      const image = new Image()
      image.src = src
      await image.decode()
      const out = {}

      for (const size of sizes) {
        const canvas = document.createElement('canvas')
        canvas.width = size
        canvas.height = size
        const context = canvas.getContext('2d')
        context.imageSmoothingQuality = 'high'
        context.drawImage(image, 0, 0, size, size)
        // Strip the data-URL prefix; the writer needs raw PNG bytes.
        out[size] = canvas.toDataURL('image/png').split(',')[1]
      }

      return out
    },
    { sizes: wanted, src: dataUrl }
  )

  await browser.close()

  const pngs = new Map(Object.entries(rendered).map(([size, base64]) => [Number(size), Buffer.from(base64, 'base64')]))

  writeFileSync(path.join(DESKTOP_ROOT, 'assets', 'icon.png'), pngs.get(512))
  writeFileSync(
    path.join(DESKTOP_ROOT, 'assets', 'icon.ico'),
    buildIco(ICO_SIZES.map(size => ({ png: pngs.get(size), size })))
  )
  writeFileSync(path.join(DESKTOP_ROOT, 'assets', 'icon.icns'), buildIcns(pngs))
  mkdirSync(path.join(DESKTOP_ROOT, 'public'), { recursive: true })
  writeFileSync(path.join(DESKTOP_ROOT, 'public', 'apple-touch-icon.png'), pngs.get(180))

  console.log('wrote assets/icon.png, assets/icon.ico, assets/icon.icns, public/apple-touch-icon.png')
}

await main()

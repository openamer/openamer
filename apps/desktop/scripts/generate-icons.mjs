#!/usr/bin/env node
/* global document, Image -- the page.evaluate callback runs in the browser */
/**
 * generate-icons.mjs — derive every desktop icon from ONE canonical master.
 *
 * Source of truth: docs/assets/openamer-logo.svg (O enclosing A).
 * The same text-free geometric monogram ships on every product surface.
 * Also regenerates setup, website, web, VS Code, and launch brand assets.
 *
 * Outputs (all committed, so a normal build needs no browser):
 *   assets/icon.png            512×512 master used by Electron + electron-builder
 *   assets/icon.ico            16/24/32/48/64/128/256 as classic 32bpp BMP entries
 *   assets/icon.icns           real Apple icon container (was a mislabeled PNG)
 *   public/apple-touch-icon.png 180×180 renderer/apple fallback icon
 *
 * WHY BMP ENTRIES IN THE ICO: a PNG-compressed ICO renders fine through
 * DrawIconEx, but the shell path that paints taskbar buttons did not draw it on
 * this install and fell back to a blank document tile. Classic BMP entries are
 * the compatible form, so the ICO is built from raw canvas pixels instead of
 * re-using the PNGs.
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

/** BITMAPINFOHEADER + bottom-up 32bpp BGRA + zeroed AND mask. */
function bmpPayload(rgba, size) {
  const header = Buffer.alloc(40)
  header.writeUInt32LE(40, 0) // biSize
  header.writeInt32LE(size, 4) // biWidth
  header.writeInt32LE(size * 2, 8) // biHeight (XOR image + AND mask)
  header.writeUInt16LE(1, 12) // biPlanes
  header.writeUInt16LE(32, 14) // biBitCount
  header.writeUInt32LE(0, 16) // BI_RGB
  header.writeUInt32LE(size * size * 4, 20)

  const pixels = Buffer.alloc(size * size * 4)

  for (let y = 0; y < size; y += 1) {
    const srcRow = size - 1 - y // bottom-up

    for (let x = 0; x < size; x += 1) {
      const src = (srcRow * size + x) * 4
      const dst = (y * size + x) * 4
      pixels[dst] = rgba[src + 2] // B
      pixels[dst + 1] = rgba[src + 1] // G
      pixels[dst + 2] = rgba[src] // R
      pixels[dst + 3] = rgba[src + 3] // A
    }
  }

  const maskRowBytes = Math.ceil(size / 32) * 4

  return Buffer.concat([header, pixels, Buffer.alloc(maskRowBytes * size)])
}

function buildIco(bitmaps) {
  const header = Buffer.alloc(6)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(bitmaps.length, 4)

  let offset = header.length + bitmaps.length * 16
  const directory = bitmaps.map(({ payload, size }) => {
    const entry = Buffer.alloc(16)
    entry.writeUInt8(size >= 256 ? 0 : size, 0)
    entry.writeUInt8(size >= 256 ? 0 : size, 1)
    entry.writeUInt8(0, 2)
    entry.writeUInt8(0, 3)
    entry.writeUInt16LE(1, 4)
    entry.writeUInt16LE(32, 6)
    entry.writeUInt32LE(payload.length, 8)
    entry.writeUInt32LE(offset, 12)
    offset += payload.length

    return entry
  })

  return Buffer.concat([header, ...directory, ...bitmaps.map(b => b.payload)])
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
  head.writeUInt32BE(8 + chunks.reduce((total, chunk) => total + chunk.length, 0), 4)

  return Buffer.concat([head, ...chunks])
}

// The master contains geometry only: no font or external-resource dependency.

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
  const svg = readFileSync(MASTER_SVG, 'utf8')
  const dataUrl = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`
  const wanted = [...new Set([...ICO_SIZES, ...ICNS_CHUNKS.map(([, size]) => size), 512, 180])]

  const browser = await launchChromium()
  const page = await browser.newPage({ viewport: { height: 1024, width: 1024 } })
  await page.setContent('<!doctype html><meta charset="utf-8"><body style="margin:0;background:transparent"></body>')

  const rendered = await page.evaluate(
    async ({ sizes, src }) => {
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
        out[size] = {
          png: canvas.toDataURL('image/png').split(',')[1],
          rgba: Array.from(context.getImageData(0, 0, size, size).data)
        }
      }

      return out
    },
    { sizes: wanted, src: dataUrl }
  )

  const pngs = new Map(Object.entries(rendered).map(([size, { png }]) => [Number(size), Buffer.from(png, 'base64')]))
  const bitmaps = ICO_SIZES.map(size => ({
    payload: bmpPayload(rendered[size].rgba, size),
    size
  }))

  writeFileSync(path.join(DESKTOP_ROOT, 'assets', 'icon.png'), pngs.get(512))
  writeFileSync(path.join(DESKTOP_ROOT, 'assets', 'icon.ico'), buildIco(bitmaps))
  writeFileSync(path.join(DESKTOP_ROOT, 'assets', 'icon.icns'), buildIcns(pngs))
  mkdirSync(path.join(DESKTOP_ROOT, 'public'), { recursive: true })
  writeFileSync(path.join(DESKTOP_ROOT, 'public', 'apple-touch-icon.png'), pngs.get(180))

  const root = path.resolve(DESKTOP_ROOT, '../..')
  const write = (name, bytes) => {
    const target = path.join(root, name)
    mkdirSync(path.dirname(target), { recursive: true })
    writeFileSync(target, bytes)
  }
  for (const name of ['docs/assets/openamer-logo.png', 'apps/desktop/public/openamer.png', 'apps/bootstrap-installer/public/openamer-logo.png', 'website/static/img/openamer-logo.png', 'website/static/img/logo.png', 'LAUNCH/assets/openamer-logo-512.png']) write(name, pngs.get(512))
  for (const name of ['apps/desktop/public/favicon.ico', 'apps/bootstrap-installer/src-tauri/icons/icon.ico', 'website/static/img/favicon.ico', 'web/public/favicon.ico']) write(name, buildIco(bitmaps))
  write('apps/bootstrap-installer/src-tauri/icons/icon.icns', buildIcns(pngs))
  for (const [name, size] of Object.entries({
    'apps/bootstrap-installer/src-tauri/icons/32x32.png': 32,
    'apps/bootstrap-installer/src-tauri/icons/128x128.png': 128,
    'apps/bootstrap-installer/src-tauri/icons/128x128@2x.png': 256,
    'website/static/img/favicon.png': 32,
    'website/static/img/favicon-16x16.png': 16,
    'website/static/img/favicon-32x32.png': 32,
    'website/static/img/apple-touch-icon.png': 180,
    'apps/vscode/icon.png': 128,
    'LAUNCH/assets/openamer-icon-180.png': 180
  })) write(name, pngs.get(size))
  write('website/static/img/favicon.svg', svg)
  const samples = [16, 24, 32, 48, 64, 128].map(size => `<div class="sample"><img width="${size}" height="${size}" src="data:image/png;base64,${rendered[size].png}"><span>${size} px</span></div>`).join('')
  await page.setViewportSize({ width: 1600, height: 1000 })
  await page.setContent(`<!doctype html><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;background:#080f1d;color:#eefaff;font-family:Arial,sans-serif;padding:72px}
    .eyebrow{font-size:14px;letter-spacing:5px;color:#62e8ee}h1{font-size:76px;letter-spacing:-4px;margin:20px 0}p{font-size:20px;color:#8fa8ba;line-height:1.6}
    .hero{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #203445;padding-bottom:60px}.hero img{width:400px;height:400px}
    .row{display:flex;gap:36px;margin-top:38px;align-items:center}.sample{height:174px;min-width:130px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px;background:#101f31;border-radius:18px}.sample span{font-size:13px;color:#90b0c2}
    .footer{margin-top:32px;color:#6d879b;font-size:14px;letter-spacing:2px}
    </style><div class="hero"><div><div class="eyebrow">OPENAMER / VISUAL IDENTITY</div><h1>One unmistakable<br>signature.</h1><p>A bold O. An ascending A. One geometric signal.<br>Cyan energy, teal depth, midnight clarity.</p></div><img src="${dataUrl}"></div><div class="row">${samples}</div><div class="footer">O ENCLOSING A &nbsp; / &nbsp; SHARED SVG MASTER &nbsp; / &nbsp; 16–1024 PX &nbsp; / &nbsp; PNG · ICO · ICNS</div>`)
  await page.locator('img').evaluateAll(images => Promise.all(images.map(image => image.decode())))
  await page.screenshot({ path: path.join(root, 'docs/assets/openamer-identity-preview.png') })
  await browser.close()
  console.log('Generated shared O/A brand assets and docs/assets/openamer-identity-preview.png')
}

await main()

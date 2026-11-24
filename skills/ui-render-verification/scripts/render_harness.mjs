#!/usr/bin/env node
// Render harness: real component -> real markup -> SHIPPED css -> measured boxes.
//
// Usage (run from the app dir, e.g. apps/desktop):
//   node render_harness.mjs \
//     --component src/components/ui/brand-loader.tsx \
//     --export BrandLoader \
//     --props '{"decorative":true}' \
//     --slot brand-loader \
//     --css release/win-unpacked/resources/app.asar.unpacked/dist/assets \
//     --em 1.15 --min-px 8 --max-px 32 \
//     [--frames 0,300,1500] [--out tmp/harness]
//
// Exit 0 = every measured slot satisfies the bounds; exit 1 = a violation.
// Exit 2 = the harness itself could not run (missing arg / file) — never report
// that as a UI verdict.
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import * as esbuild from 'esbuild'
import { chromium } from 'playwright'

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`)

  return i === -1 ? fallback : process.argv[i + 1]
}

function die(message) {
  console.error(`harness: ${message}`)
  process.exit(2)
}

const component = arg('component') ?? die('--component <tsx> is required')
const exportName = arg('export', 'default')
const props = JSON.parse(arg('props', '{}'))
const slot = arg('slot') ?? die('--slot <data-slot value> is required')
const cssInput = arg('css') ?? die('--css <built css file or its directory> is required')
const emFactor = Number(arg('em', '0'))
const minPx = Number(arg('min-px', '0'))
const maxPx = Number(arg('max-px', '100000'))
const frames = (arg('frames') ?? '').split(',').filter(Boolean).map(Number)
const outDir = resolve(arg('out', 'tmp/render-harness'))
const root = process.cwd()

const entry = resolve(root, component)

if (!statSync(entry, { throwIfNoEntry: false })) die(`component not found: ${entry}`)

const cssPath = statSync(cssInput).isDirectory()
  ? resolve(cssInput, readdirSync(cssInput).find(f => /^index-.*\.css$/.test(f)) ?? die('no index-*.css there'))
  : resolve(cssInput)

mkdirSync(outDir, { recursive: true })

const bundlePath = resolve(outDir, 'component.bundle.mjs')

await esbuild.build({
  alias: { '@': resolve(root, 'src') },
  bundle: true,
  entryPoints: [entry],
  external: ['react', 'react-dom', 'react/jsx-runtime'],
  format: 'esm',
  jsx: 'automatic',
  logLevel: 'warning',
  outfile: bundlePath,
  platform: 'node',
  tsconfig: resolve(root, 'tsconfig.json')
})

const mod = (await import(pathToFileURL(bundlePath).href))[exportName]

if (typeof mod !== 'function') die(`export '${exportName}' is not a component`)

const [{ createElement }, { renderToStaticMarkup }] = await Promise.all([
  import('react'),
  import('react-dom/server')
])

const markup = renderToStaticMarkup(createElement(mod, props))
const css = readFileSync(cssPath, 'utf8')

const html = `<!doctype html><html class="dark"><head><meta charset="utf-8">
<style>${css}</style>
<style>
  body { background:#141a21; margin:0; padding:24px; font:14px/1.5 system-ui }
  .cell { display:grid; place-items:center; width:420px; height:180px; border:1px solid #253244 }
  .frozen .oa-loader-ring-sweep, .frozen .oa-loader-a-legs, .frozen .oa-loader-a-bar {
    animation-delay: var(--freeze, 0ms) !important;
    animation-play-state: paused !important;
  }
</style></head><body>
<div class="cell" id="cell">${markup}</div>
<script>
  const t = new URLSearchParams(location.search).get('t')
  if (t !== null) {
    document.body.classList.add('frozen')
    document.documentElement.style.setProperty('--freeze', '-' + t + 'ms')
  }
</script>
</body></html>`

const htmlPath = resolve(outDir, 'harness.html')

writeFileSync(htmlPath, html)

const browser = await chromium.launch()
const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { height: 260, width: 480 } })

await page.goto(`file://${htmlPath.replace(/\\/g, '/')}`)
await page.waitForTimeout(200)

const measured = await page.evaluate(sel => {
  return [...document.querySelectorAll(`[data-slot="${sel}"]`)].map(el => {
    const r = el.getBoundingClientRect()
    const s = getComputedStyle(el)

    return {
      width: +r.width.toFixed(2),
      height: +r.height.toFixed(2),
      fontSize: s.fontSize,
      cellHeight: +(el.closest('.cell')?.getBoundingClientRect().height ?? 0).toFixed(0)
    }
  })
}, slot)

if (measured.length === 0) {
  await browser.close()
  die(`no element with data-slot="${slot}" in the rendered markup`)
}

console.log(`css: ${cssPath}`)
console.table(measured)

let failed = false

for (const m of measured) {
  if (emFactor > 0) {
    const expected = +(parseFloat(m.fontSize) * emFactor).toFixed(2)

    console.log(`em check: ${m.height}px vs ${expected}px (${emFactor} × ${m.fontSize})`)

    if (Math.abs(m.height - expected) > 1.5) failed = true
  }

  if (m.height < minPx || m.height > maxPx) {
    console.log(`bounds check: ${m.height}px outside [${minPx}, ${maxPx}]`)
    failed = true
  }

  if (m.cellHeight > 0 && Math.abs(m.height - m.cellHeight) < 1) {
    console.log(`layout check: the element fills its cell (${m.cellHeight}px) — it has no size`)
    failed = true
  }
}

for (const t of frames) {
  await page.goto(`file://${htmlPath.replace(/\\/g, '/')}?t=${t}`)
  await page.waitForTimeout(120)
  const shot = resolve(outDir, `frame-${String(t).padStart(4, '0')}.png`)

  await page.screenshot({ path: shot })
  console.log('frame', shot)
}

await browser.close()
console.log(failed ? 'FAIL: a measured box violates the expected contract' : 'PASS')
process.exit(failed ? 1 : 0)

// Real-browser end-to-end proof for the preview-act engine.
//
// The vitest suite exercises the engine against jsdom. This spec drives the
// SAME engine source in a real Chromium against a real locally-served fixture
// page, so the claim the adoption card asks for ("real local fixture served in
// the preview, element action/readback and screenshot verified") is backed by
// a real browser run rather than a DOM shim.
//
// The engine is self-contained by construction: `previewActEngineSource()`
// stringifies the function and injects it into the page, which is exactly how
// the renderer reaches the guest page through `webview.executeJavaScript`.
// This spec injects it the same way — via `page.evaluate` — so the code that
// runs here is byte-identical to the code that ships.

import { mkdirSync, readFileSync } from 'node:fs'
import { createServer, type Server } from 'node:http'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { previewActEngineSource } from '../src/lib/preview-act/act-in-page'

const HERE = dirname(fileURLToPath(import.meta.url))
const FIXTURE = resolve(HERE, 'preview-act-fixture.html')

// esbuild rewrites named function expressions to a `__name` helper. The engine
// source is injected into a bare page context where that helper does not
// exist, so provide it — the shipped source then runs verbatim.
const PAGE_HELPER = 'globalThis.__name = globalThis.__name || ((fn) => fn);'

type EngineResult = {
  ok: boolean
  status?: string
  message?: string
  elements?: { ref: string; role: string; label: string; value?: string }[]
  readback?: { text: string; label?: string; ref?: string }
}

/** A minimal static server for the fixture — a real http origin, not a data URL. */
function serveFixture(): Promise<{ server: Server; origin: string }> {
  const html = readFileSync(FIXTURE, 'utf8')

  const server = createServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
    res.end(html)
  })

  return new Promise((done) => {
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      done({ server, origin: `http://127.0.0.1:${port}` })
    })
  })
}

test('the preview-act engine drives a real served page and returns a real readback', async ({
  page
}) => {
  const { server, origin } = await serveFixture()

  try {
    await page.goto(`${origin}/preview-act-fixture.html`)

    const run = async (action: Record<string, unknown>): Promise<EngineResult> => {
      const src = previewActEngineSource(action as never)

      return (await page.evaluate(
        (a: { src: string; helper: string }) =>
          (0, eval)(a.helper + a.src) as unknown as Promise<EngineResult>,
        { src, helper: PAGE_HELPER }
      )) as EngineResult
    }

    // --- inventory -------------------------------------------------------
    const inventory = await run({ action: 'elements' })
    console.log('INVENTORY ' + JSON.stringify(inventory.elements, null, 2))
    expect(inventory.ok).toBe(true)
    expect(inventory.elements?.length ?? 0).toBeGreaterThan(0)

    const refs = inventory.elements ?? []
    const button = refs.find((el) => el.role === 'button')
    const field = refs.find((el) => el.role === 'textbox')
    expect(button).toBeDefined()
    expect(field).toBeDefined()

    // --- act on a real element and read the result back ------------------
    const acted = await run({ action: 'click', ref: button?.ref ?? '' })
    console.log('CLICK ' + JSON.stringify(acted, null, 2))
    expect(acted.ok).toBe(true)

    // The click must have actually reached the page: the fixture's status
    // line changes on click, and the engine reads the visible text back.
    const readback = await run({ action: 'read' })
    console.log('READBACK ' + JSON.stringify(readback, null, 2))
    expect(readback.ok).toBe(true)
    expect(readback.readback?.text ?? '').toContain('clicked')

    // --- type into a real field and read the value back -------------------
    const typed = await run({ action: 'type', ref: field?.ref ?? '', text: 'agent@example.com' })
    console.log('TYPE ' + JSON.stringify(typed, null, 2))
    expect(typed.ok).toBe(true)

    const valueRead = await run({ action: 'read', ref: field?.ref ?? '' })
    console.log('READ_FIELD ' + JSON.stringify(valueRead, null, 2))
    expect(valueRead.readback?.text ?? '').toContain('agent@example.com')

    // --- a ref that does not exist must fail closed ----------------------
    const bogus = await run({ action: 'click', ref: 'no-such-ref' })
    console.log('BOGUS ' + JSON.stringify(bogus, null, 2))
    expect(bogus.ok).toBe(false)
    expect(bogus.status).toBe('unknown-ref')

    // --- screenshot proof ------------------------------------------------
    // The artifact must show the page AFTER the click — that is the point of
    // the screenshot. Read the DOM back to bind the image to a known state.
    const statusText = await page.textContent('#status')
    console.log('STATUS_TEXT ' + String(statusText))
    expect(String(statusText)).toContain('clicked')

    // Write into Playwright's own output directory: it is gitignored and is
    // uploaded as the `playwright-test-results-<sha>` CI artifact. Writing to a
    // fresh untracked directory (e.g. apps/pr-assets) would deposit files into
    // every clone that runs the suite.
    const outDir = resolve(HERE, '../test-results')
    mkdirSync(outDir, { recursive: true })
    const shot = resolve(outDir, 'preview-act-fixture.png')
    await page.screenshot({ path: shot, fullPage: true })
    console.log('SCREENSHOT ' + shot)
  } finally {
    await new Promise<void>((done) => server.close(() => done()))
  }
})

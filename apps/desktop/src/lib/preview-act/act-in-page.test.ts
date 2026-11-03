import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  PREVIEW_ACT_GLOBAL,
  previewActEngine,
  type PreviewActEngineResult,
  previewActEngineSource
} from './act-in-page'

function resetPage(): void {
  delete (window as unknown as Record<string, unknown>)[PREVIEW_ACT_GLOBAL]
  document.body.innerHTML = ''
}

function ok(result: PreviewActEngineResult): Extract<PreviewActEngineResult, { ok: true }> {
  if (!result.ok) {
    throw new Error(`expected success, got ${result.status}: ${result.message}`)
  }

  return result
}

describe('preview act engine', () => {
  beforeEach(() => {
    resetPage()
    // jsdom does not lay out text, so getClientRects() is always empty. The
    // engine treats an empty rect list as "not visible" — correct for a real
    // browser, wrong for jsdom — so give elements a rect here.
    vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(function (this: Element) {
      return [{ height: 10, width: 10 }] as unknown as DOMRectList
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    resetPage()
  })

  it('inventories clickable and typable elements as legible refs', async () => {
    document.body.innerHTML = `
      <main>
        <h1>Fixture</h1>
        <button>Sign in</button>
        <a href="/docs">Read the docs</a>
        <input placeholder="Email" />
        <button disabled>Disabled</button>
        <div hidden><button>Hidden</button></div>
      </main>`

    const result = ok(await previewActEngine({ action: 'elements' }))

    expect(result.elements.map(el => el.ref)).toEqual(['btn-sign-in', 'link-read-the-docs', 'field-email'])
    expect(result.elements.map(el => el.role)).toEqual(['button', 'link', 'textbox'])
    expect(result.elements[2]?.label).toBe('Email')
  })

  it('disambiguates repeated labels instead of reusing one ref', async () => {
    document.body.innerHTML = '<button>Save</button><button>Save</button>'

    const result = ok(await previewActEngine({ action: 'elements' }))

    expect(result.elements.map(el => el.ref)).toEqual(['btn-save', 'btn-save-1'])
  })

  it('clicks the element a ref names, not whatever moved into its place', async () => {
    const onClick = vi.fn()

    document.body.innerHTML = '<button>Pay</button><button>Cancel</button>'
    document.querySelector('button')!.addEventListener('click', onClick)

    ok(await previewActEngine({ action: 'elements' }))
    const result = ok(await previewActEngine({ action: 'click', ref: 'btn-pay' }))

    expect(onClick).toHaveBeenCalledTimes(1)
    expect(result.elements.length).toBe(2)
  })

  it('types into a field and reports the new value back', async () => {
    document.body.innerHTML = '<input placeholder="Email" />'

    ok(await previewActEngine({ action: 'elements' }))
    ok(await previewActEngine({ action: 'type', ref: 'field-email', text: 'damir@example.test' }))

    expect((document.querySelector('input') as HTMLInputElement).value).toBe('damir@example.test')

    const read = ok(await previewActEngine({ action: 'read', ref: 'field-email' }))

    expect(read.readback).toEqual({ label: 'Email', ref: 'field-email', text: 'damir@example.test' })
  })

  it('submits the form when asked to', async () => {
    const onSubmit = vi.fn((event: Event) => event.preventDefault())

    document.body.innerHTML = '<form><input placeholder="Email" /><button>Go</button></form>'
    document.querySelector('form')!.addEventListener('submit', onSubmit)

    ok(await previewActEngine({ action: 'elements' }))
    ok(await previewActEngine({ action: 'type', ref: 'field-email', text: 'x@y.z', submit: true }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('reads the visible page text when no ref is named', async () => {
    document.body.innerHTML = '<p>Order confirmed</p>'

    const result = ok(await previewActEngine({ action: 'read' }))

    expect(result.readback?.text).toContain('Order confirmed')
  })

  it('rejects a ref whose element was replaced, instead of acting on the new one', async () => {
    const onNewClick = vi.fn()

    document.body.innerHTML = '<button>Delete</button>'
    ok(await previewActEngine({ action: 'elements' }))

    // A framework re-render swaps the subtree: same position, different node.
    document.body.innerHTML = '<button>Delete</button>'
    document.querySelector('button')!.addEventListener('click', onNewClick)

    const result = await previewActEngine({ action: 'click', ref: 'btn-delete' })

    expect(result.ok).toBe(false)
    expect(result.status).toBe('stale-ref')
    expect(onNewClick).not.toHaveBeenCalled()
  })

  it('rejects a ref it never handed out', async () => {
    document.body.innerHTML = '<button>Sign in</button>'

    const result = await previewActEngine({ action: 'click', ref: 'btn-made-up' })

    expect(result.ok).toBe(false)
    expect(result.status).toBe('unknown-ref')

    if (result.ok) {
      throw new Error('expected the engine to refuse an unknown ref')
    }

    expect(result.message).toContain('call elements again')
  })

  it('answers unsupported for an action it does not implement', async () => {
    document.body.innerHTML = '<button>Sign in</button>'

    const result = await previewActEngine({ action: 'evaluate' as never })

    expect(result).toMatchObject({ ok: false, status: 'unsupported' })
  })

  it('is self-contained: the injected source runs without module scope', async () => {
    document.body.innerHTML = '<button>Sign in</button><input placeholder="Email" />'

    // Exactly what the renderer sends through executeJavaScript. `new Function`
    // has no access to this module's bindings, so anything the engine closes over
    // would blow up here instead of silently working only in tests.
    const run = new Function(`return ${previewActEngineSource({ action: 'elements' })}`)
    const result = (await run()) as PreviewActEngineResult

    expect(result.ok).toBe(true)
    expect(ok(result).elements.map(el => el.ref)).toEqual(['btn-sign-in', 'field-email'])
  })

  it('mints a fresh book after the page reloads it', async () => {
    document.body.innerHTML = '<button>Sign in</button>'
    ok(await previewActEngine({ action: 'elements' }))

    // A navigation destroys the injected global; the next call starts over.
    delete (window as unknown as Record<string, unknown>)[PREVIEW_ACT_GLOBAL]

    const stale = await previewActEngine({ action: 'click', ref: 'btn-sign-in' })

    expect(stale).toMatchObject({ ok: false, status: 'unknown-ref' })
  })
})

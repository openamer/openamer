/**
 * The engine that runs INSIDE the preview pane's guest page.
 *
 * The page is out-of-process, so the renderer reaches it with
 * `webview.executeJavaScript`. That makes this function *self-contained by
 * construction*: `previewActEngineSource()` stringifies it and evaluates it in
 * the page, where none of our imports, closures or module constants exist. Every
 * helper therefore lives inside the function body. Tests call the same function
 * directly against a real DOM (jsdom), so the code that ships is the code that is
 * tested — there is no parallel "string template" copy to drift.
 *
 * What it does, in the smallest useful shape:
 *
 *   elements — inventory clickable/typable elements as legible refs
 *              ('btn-sign-in') with role, label and value.
 *   click    — resolve the ref to a node and click it.
 *   type     — resolve the ref, replace the field's value, fire input/change,
 *              optionally submit the form.
 *   read     — the page's visible text, or one element's value/text.
 *
 * Two invariants the renderer relies on, enforced here rather than assumed:
 *
 *  1. A ref belongs to the DOCUMENT it was minted in. Refs live on a window
 *     global, which a navigation destroys; and the book carries a document token
 *     so a rebuild inside the same document still retires the old refs. Acting on
 *     a ref that is gone answers `stale-ref` — never a best-effort guess at
 *     "whatever is there now". The caller is told to re-inventory.
 *  2. Nothing is evaluated on the caller's behalf. There is no selector input and
 *     no script hook: the caller names a ref, and the engine owns the code.
 *
 * Ported in spirit from NousResearch/hermes-agent `lib/preview-act/*` (MIT, pinned
 * at bfa652fae87fd7c5c01161188f97a8ed68b5a762). The delta protocol, the pointer /
 * overlay / strobe layers and `sendInputEvent` are NOT ported — this is the
 * bounded slice (see NOTICE).
 */

export const PREVIEW_ACT_GLOBAL = '__openamerPreviewAct'

/**
 * The key the page engine parks its ref book on. Passed into the injected source
 * rather than closed over, because the engine is stringified into the guest page
 * where this module does not exist.
 */
const DEFAULT_GLOBAL_KEY = PREVIEW_ACT_GLOBAL

export type PreviewActVerb = 'elements' | 'click' | 'type' | 'read'

export interface PreviewActRequestPayload {
  action: PreviewActVerb
  max?: number
  ref?: string
  submit?: boolean
  text?: string
}

export interface PreviewActElement {
  label: string
  ref: string
  role: string
  value?: string
}

export type PreviewActEngineResult =
  | {
      action: PreviewActVerb
      elements: PreviewActElement[]
      ok: true
      readback?: { label?: string; ref?: string; text: string }
      status: 'ok'
      title: string
      truncated: boolean
      url: string
    }
  | { message: string; ok: false; ref?: string; status: 'denied' | 'stale-ref' | 'unknown-ref' | 'unsupported' }

export async function previewActEngine(
  payload: PreviewActRequestPayload,
  globalKey: string = DEFAULT_GLOBAL_KEY
): Promise<PreviewActEngineResult> {
  const DEFAULT_MAX = 60
  const HARD_MAX = 200
  const LABEL_MAX = 80
  const READ_MAX = 4000
  const SETTLE_MS = 80

  const CANDIDATE_SELECTOR = [
    'a[href]',
    'button',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    '[contenteditable="true"]',
    '[role="button"]',
    '[role="link"]',
    '[role="checkbox"]',
    '[role="tab"]',
    '[role="menuitem"]',
    '[role="switch"]',
    '[role="radio"]'
  ].join(',')

  interface Entry {
    label: string
    ref: string
    role: string
    target: Element
  }

  interface Book {
    doc: string
    entries: Map<string, Entry>
    seq: number
  }

  const doc = document
  const view = doc.defaultView as (Window & Record<string, unknown>) | null

  if (!view) {
    return { message: 'The preview page is not ready yet.', ok: false, status: 'unsupported' }
  }

  const scope = view as unknown as Record<string, unknown>
  let book = scope[globalKey] as Book | undefined

  if (!book || !book.doc) {
    book = {
      doc: Math.random().toString(36).slice(2) + Date.now().toString(36),
      entries: new Map<string, Entry>(),
      seq: 0
    }
    scope[globalKey] = book
  }

  const roleOf = (el: Element): string => {
    const explicit = el.getAttribute('role')

    if (explicit) {
      return explicit
    }

    const tag = el.tagName.toLowerCase()

    if (tag === 'a') {
      return 'link'
    }

    if (tag === 'button') {
      return 'button'
    }

    if (tag === 'select') {
      return 'combobox'
    }

    if (tag === 'textarea') {
      return 'textbox'
    }

    if (tag === 'input') {
      const type = (el.getAttribute('type') || 'text').toLowerCase()

      if (type === 'checkbox' || type === 'radio') {
        return type
      }

      if (type === 'submit' || type === 'button' || type === 'reset') {
        return 'button'
      }

      return 'textbox'
    }

    return 'textbox'
  }

  const valueOf = (el: Element): string | undefined => {
    const tag = el.tagName.toLowerCase()

    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      const value = (el as HTMLInputElement).value

      return value ? value.slice(0, LABEL_MAX) : undefined
    }

    return undefined
  }

  const labelOf = (el: Element): string => {
    const raw =
      el.getAttribute('aria-label') ||
      el.getAttribute('placeholder') ||
      el.getAttribute('title') ||
      el.getAttribute('alt') ||
      valueOf(el) ||
      el.textContent ||
      ''

    return raw.replace(/\s+/g, ' ').trim().slice(0, LABEL_MAX)
  }

  const slugOf = (role: string, label: string): string => {
    const prefix =
      role === 'button'
        ? 'btn'
        : role === 'link'
          ? 'link'
          : role === 'textbox'
            ? 'field'
            : role === 'checkbox'
              ? 'check'
              : role === 'combobox'
                ? 'select'
                : role === 'option' || role === 'menuitem'
                  ? 'option'
                  : role === 'tab'
                    ? 'tab'
                    : 'el'

    const tail = label
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40)
      .replace(/-+$/g, '')

    return tail ? `${prefix}-${tail}` : prefix
  }

  const isVisible = (el: Element): boolean => {
    const html = el as HTMLElement

    if (html.hidden || (el as HTMLInputElement).disabled || el.closest?.('[hidden]')) {
      return false
    }

    const rects = el.getClientRects?.()

    if (rects && rects.length === 0) {
      return false
    }

    const style = view.getComputedStyle?.(el)

    return !(style && (style.visibility === 'hidden' || style.display === 'none'))
  }

  /** `innerText` is what the user reads, but it does not exist everywhere. */
  const textOf = (el: HTMLElement | null | undefined): string => String(el?.innerText ?? el?.textContent ?? '')

  const inventory = (max: number): { elements: PreviewActElement[]; truncated: boolean } => {
    book!.entries.clear()

    const found: PreviewActElement[] = []

    for (const el of Array.from(doc.querySelectorAll(CANDIDATE_SELECTOR))) {
      if (!isVisible(el)) {
        continue
      }

      const role = roleOf(el)
      const label = labelOf(el)
      const base = slugOf(role, label)
      let ref = base

      while (book!.entries.has(ref)) {
        book!.seq += 1
        ref = `${base}-${book!.seq}`
      }

      book!.entries.set(ref, { label, ref, role, target: el })

      const value = valueOf(el)

      found.push({ ...(value ? { value } : {}), label, ref, role })
    }

    return { elements: found.slice(0, max), truncated: found.length > max }
  }

  const resolve = (ref: string): { entry?: Entry; failure?: PreviewActEngineResult } => {
    const entry = book!.entries.get(ref)

    if (!entry) {
      return {
        failure: {
          message: `Ref '${ref}' is not part of the current page inventory — call elements again.`,
          ok: false,
          ref,
          status: 'unknown-ref'
        }
      }
    }

    // A node detached since the inventory (a re-render replaced the subtree) is
    // exactly the case a stale ref must catch, so it never silently retargets.
    if (!entry.target.isConnected) {
      book!.entries.delete(ref)

      return {
        failure: {
          message: `Ref '${ref}' belonged to a previous view of the page — call elements again.`,
          ok: false,
          ref,
          status: 'stale-ref'
        }
      }
    }

    return { entry }
  }

  const max = Math.min(Math.max(payload.max ?? DEFAULT_MAX, 1), HARD_MAX)
  const base = { title: doc.title || '', url: doc.location?.href || '' }
  const action = payload.action

  if (action === 'elements') {
    const { elements, truncated } = inventory(max)

    return { ...base, action, elements, ok: true, status: 'ok', truncated }
  }

  if (action === 'read') {
    const wanted = (payload.ref || '').trim()

    if (!wanted) {
      const bodyText = textOf(doc.body).slice(0, READ_MAX)

      return {
        ...base,
        action,
        elements: [],
        ok: true,
        readback: { text: bodyText },
        status: 'ok',
        truncated: textOf(doc.body).length > READ_MAX
      }
    }

    const { entry, failure } = resolve(wanted)

    if (failure || !entry) {
      return failure!
    }

    const text = (textOf(entry.target as HTMLElement) || valueOf(entry.target) || '').slice(0, READ_MAX)

    return {
      ...base,
      action,
      elements: [],
      ok: true,
      readback: { label: entry.label, ref: wanted, text },
      status: 'ok',
      truncated: text.length > READ_MAX
    }
  }

  if (action !== 'click' && action !== 'type') {
    return { message: `Unsupported action '${String(action)}'.`, ok: false, status: 'unsupported' }
  }

  const { entry, failure } = resolve((payload.ref || '').trim())

  if (failure || !entry) {
    return failure!
  }

  const target = entry.target as HTMLElement

  if (action === 'click') {
    target.focus?.()
    target.click()
  } else {
    const text = payload.text ?? ''

    target.focus?.()

    if (target.isContentEditable) {
      target.textContent = text
    } else {
      // React (and every other controlled input) tracks the value through its
      // own setter: assigning `el.value` updates the DOM but not the framework's
      // state, so the next render restores the old text. Calling the prototype's
      // native setter keeps that tracker honest.
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(target), 'value')?.set

      if (setter) {
        setter.call(target, text)
      } else {
        ;(target as unknown as { value: string }).value = text
      }
    }

    target.dispatchEvent(new Event('input', { bubbles: true }))
    target.dispatchEvent(new Event('change', { bubbles: true }))

    if (payload.submit) {
      const form = (target as HTMLInputElement).form

      if (form?.requestSubmit) {
        form.requestSubmit()
      } else if (form) {
        form.submit()
      }
    }
  }

  // Let the framework commit before re-inventorying, so the answer describes the
  // page as it is *after* the action.
  await new Promise(resolveWait => setTimeout(resolveWait, SETTLE_MS))

  const { elements, truncated } = inventory(max)

  return { ...base, action, elements, ok: true, status: 'ok', truncated }
}

/** The page-side source string the renderer injects through executeJavaScript. */
export function previewActEngineSource(payload: PreviewActRequestPayload): string {
  return `(${previewActEngine.toString()})(${JSON.stringify(payload)}, ${JSON.stringify(DEFAULT_GLOBAL_KEY)})`
}

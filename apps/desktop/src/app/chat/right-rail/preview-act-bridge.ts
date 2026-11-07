/**
 * The renderer half of `drive_preview`: answer the gateway's `preview.act.request`
 * for the preview page this window is showing, or refuse.
 *
 * Two things are decided here, and both are refusals by default:
 *
 *  - **Ownership.** The request must name a session, that session must be the one
 *    this window has in front of the user, and the pane must actually be mounted
 *    for it. A background conversation's turn can therefore never drive the page
 *    the user is looking at — it gets `denied`, and the tool reports that instead
 *    of acting on someone else's tab. The gateway enforces the mirror half: an
 *    answer stamped with a different session id is rejected server-side.
 *  - **Refs.** Resolving refs happens in the page engine
 *    (`lib/preview-act/act-in-page.ts`), which retires them on navigation and
 *    answers `stale-ref` rather than clicking whatever replaced the old element.
 *
 * Everything the answer needs comes from the caller, so the module is pure enough
 * to unit-test without a gateway or an Electron window.
 */

import {
  type PreviewActEngineResult,
  previewActEngineSource,
  type PreviewActRequestPayload,
  type PreviewActVerb
} from '@/lib/preview-act/act-in-page'

/** The mounted preview pane, as far as this bridge is concerned. */
export interface PreviewActHost {
  executeJavaScript(code: string): Promise<unknown>
  /** The session whose preview this pane is currently showing. */
  sessionId: string
}

const VERBS: readonly PreviewActVerb[] = ['elements', 'click', 'type', 'read']

/** One answer frame stays small: the model gets inventory + a text readback. */
export const PREVIEW_ACT_MAX_RESULT_CHARS = 12_000

let activeHost: PreviewActHost | null = null

/** Called by the pane on mount; the returned function unregisters it. */
export function registerPreviewActHost(host: PreviewActHost): () => void {
  activeHost = host

  return () => {
    if (activeHost === host) {
      activeHost = null
    }
  }
}

/** Test seam — production only ever sets the host through the pane. */
export function resetPreviewActHostForTests(): void {
  activeHost = null
}

export type PreviewActRefusal = 'no-active-session' | 'not-active-session' | 'no-preview'

export type PreviewActDecision =
  | { host: PreviewActHost; ok: true }
  | { message: string; ok: false; reason: PreviewActRefusal }

export interface PreviewActDecisionInput {
  activeSessionId: string | null | undefined
  eventSessionId: string | null | undefined
  host: PreviewActHost | null
}

export function decidePreviewAct(input: PreviewActDecisionInput): PreviewActDecision {
  const active = (input.activeSessionId || '').trim()
  const requested = (input.eventSessionId || '').trim()

  if (!active) {
    return {
      message: 'No conversation is in focus, so there is no preview this window may drive.',
      ok: false,
      reason: 'no-active-session'
    }
  }

  // The request names a session and it is not this window's focused one: a
  // background turn asking to drive the pane must not be served.
  if (requested && requested !== active) {
    return {
      message:
        'That request belongs to another conversation. drive_preview only drives the preview of the conversation the user is looking at.',
      ok: false,
      reason: 'not-active-session'
    }
  }

  const host = input.host

  if (!host) {
    return {
      message: 'No preview page is open in this window — open one with open_preview first.',
      ok: false,
      reason: 'no-preview'
    }
  }

  if (!host.sessionId) {
    return {
      message:
        'This window has not settled which conversation the pane belongs to yet — try again once the turn is under way.',
      ok: false,
      reason: 'no-active-session'
    }
  }

  if (host.sessionId !== active) {
    return {
      message:
        'The preview pane is showing a different conversation’s page. Switch back to it, or open this conversation’s page with open_preview first.',
      ok: false,
      reason: 'not-active-session'
    }
  }

  return { host, ok: true }
}

function clampResult(result: PreviewActEngineResult): string {
  const encoded = JSON.stringify(result)

  if (encoded.length <= PREVIEW_ACT_MAX_RESULT_CHARS) {
    return encoded
  }

  return JSON.stringify({
    message:
      'The page answered with more than this bridge will carry; narrow the request (elements max, or read one ref).',
    ok: false,
    status: 'unsupported'
  })
}

function parsePayload(raw: Record<string, unknown>): PreviewActRequestPayload | null {
  const action = typeof raw.action === 'string' ? (raw.action.trim().toLowerCase() as PreviewActVerb) : null

  if (!action || !VERBS.includes(action)) {
    return null
  }

  const payload: PreviewActRequestPayload = { action }

  if (typeof raw.ref === 'string' && raw.ref.trim()) {
    payload.ref = raw.ref.trim()
  }

  if (typeof raw.text === 'string') {
    payload.text = raw.text
  }

  if (typeof raw.submit === 'boolean') {
    payload.submit = raw.submit
  }

  if (typeof raw.max === 'number' && Number.isFinite(raw.max)) {
    payload.max = Math.trunc(raw.max)
  }

  return payload
}

export interface PreviewActAnswerInput {
  activeSessionId: string | null | undefined
  /** The session id the gateway stamped on the request frame, if any. */
  eventSessionId?: string | null
  /** The payload the gateway sent, including its `request_id`. */
  payload: Record<string, unknown>
  respond: (body: { request_id: string; result: string; session_id: string }) => void
  /** Overrides the mounted host — tests only. */
  host?: PreviewActHost | null
}

/**
 * Answer one `preview.act.request`. Always answers when a `request_id` is present
 * — including refusals — because the gateway's tool call is blocked on it and a
 * silent bridge would burn the whole timeout.
 */
export async function answerPreviewAct(input: PreviewActAnswerInput): Promise<boolean> {
  const requestId = typeof input.payload.request_id === 'string' ? input.payload.request_id : ''

  if (!requestId) {
    return false
  }

  const sessionId = (input.eventSessionId || input.activeSessionId || '').trim()

  const respond = (result: PreviewActEngineResult) => {
    input.respond({ request_id: requestId, result: clampResult(result), session_id: sessionId })
  }

  const decision = decidePreviewAct({
    activeSessionId: input.activeSessionId,
    eventSessionId: sessionId,
    host: input.host === undefined ? activeHost : input.host
  })

  if (!decision.ok) {
    respond({ message: decision.message, ok: false, status: 'denied' })

    return true
  }

  const request = parsePayload(input.payload)

  if (!request) {
    respond({ message: 'Unsupported preview action.', ok: false, status: 'unsupported' })

    return true
  }

  let raw: unknown

  try {
    raw = await decision.host.executeJavaScript(previewActEngineSource(request))
  } catch (error) {
    respond({
      message: `The preview page could not be reached: ${error instanceof Error ? error.message : String(error)}`,
      ok: false,
      status: 'unsupported'
    })

    return true
  }

  // `executeJavaScript` resolves with the engine's return value. It is normally a
  // promise the embedder unwraps, but Electron hands the raw value back when the
  // page navigated mid-call, so both shapes are accepted.
  const settled =
    raw && typeof raw === 'object' && 'status' in (raw as Record<string, unknown>)
      ? (raw as PreviewActEngineResult)
      : (() => {
          try {
            return JSON.parse(String(raw)) as PreviewActEngineResult
          } catch {
            return null
          }
        })()

  if (!settled) {
    respond({
      message: 'The page stopped answering — it is probably navigating. Call elements to see where it landed.',
      ok: false,
      status: 'stale-ref'
    })

    return true
  }

  respond(settled)

  return true
}

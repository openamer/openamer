import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  answerPreviewAct,
  decidePreviewAct,
  type PreviewActHost,
  registerPreviewActHost,
  resetPreviewActHostForTests
} from './preview-act-bridge'

const SESSION_A = 'session-a'
const SESSION_B = 'session-b'

function hostFor(sessionId: string, executed: string[] = []): PreviewActHost {
  return {
    executeJavaScript: vi.fn(async (code: string) => {
      executed.push(code)

      return {
        action: 'elements',
        elements: [{ label: 'Sign in', ref: 'btn-sign-in', role: 'button' }],
        ok: true,
        status: 'ok',
        title: 'Fixture',
        truncated: false,
        url: 'http://127.0.0.1:8765/'
      }
    }),
    sessionId
  }
}

describe('decidePreviewAct', () => {
  it('allows the focused session to drive the pane it owns', () => {
    expect(
      decidePreviewAct({ activeSessionId: SESSION_A, eventSessionId: SESSION_A, host: hostFor(SESSION_A) })
    ).toMatchObject({ ok: true })
  })

  it('refuses a request that belongs to another conversation', () => {
    const decision = decidePreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_B,
      host: hostFor(SESSION_A)
    })

    expect(decision).toMatchObject({ ok: false, reason: 'not-active-session' })
  })

  it('refuses when the pane on screen belongs to another conversation', () => {
    const decision = decidePreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_A,
      host: hostFor(SESSION_B)
    })

    expect(decision).toMatchObject({ ok: false, reason: 'not-active-session' })
  })

  it('refuses when no conversation is focused', () => {
    expect(
      decidePreviewAct({ activeSessionId: null, eventSessionId: SESSION_A, host: hostFor(SESSION_A) })
    ).toMatchObject({
      ok: false,
      reason: 'no-active-session'
    })
  })

  it('refuses when the pane is not mounted', () => {
    expect(decidePreviewAct({ activeSessionId: SESSION_A, eventSessionId: SESSION_A, host: null })).toMatchObject({
      ok: false,
      reason: 'no-preview'
    })
  })

  it('refuses when the pane has not resolved its conversation yet', () => {
    expect(
      decidePreviewAct({ activeSessionId: SESSION_A, eventSessionId: SESSION_A, host: hostFor('') })
    ).toMatchObject({
      ok: false,
      reason: 'no-active-session'
    })
  })
})

describe('answerPreviewAct', () => {
  let answers: Array<{ request_id: string; result: string; session_id: string }>

  beforeEach(() => {
    answers = []
    resetPreviewActHostForTests()
  })

  afterEach(() => {
    resetPreviewActHostForTests()
  })

  const respond = (body: { request_id: string; result: string; session_id: string }) => answers.push(body)

  it('never touches the page for a cross-session request, and still answers', async () => {
    const executed: string[] = []

    await answerPreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_B,
      host: hostFor(SESSION_A, executed),
      payload: { action: 'click', ref: 'btn-pay', request_id: 'r1' },
      respond
    })

    expect(executed).toEqual([])
    expect(answers).toHaveLength(1)
    expect(JSON.parse(answers[0]!.result)).toMatchObject({ ok: false, status: 'denied' })
    expect(answers[0]!.session_id).toBe(SESSION_B)
  })

  it('runs the engine for the owning session and answers with its readback', async () => {
    await answerPreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_A,
      host: hostFor(SESSION_A),
      payload: { action: 'elements', request_id: 'r2' },
      respond
    })

    expect(answers).toHaveLength(1)
    expect(answers[0]!.request_id).toBe('r2')
    expect(answers[0]!.session_id).toBe(SESSION_A)
    expect(JSON.parse(answers[0]!.result)).toMatchObject({ ok: true, status: 'ok' })
  })

  it('passes a stale-ref refusal through untouched', async () => {
    const host: PreviewActHost = {
      executeJavaScript: vi.fn(async () => ({
        message: "Ref 'btn-pay' belonged to a previous view of the page.",
        ok: false,
        status: 'stale-ref'
      })),
      sessionId: SESSION_A
    }

    await answerPreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_A,
      host,
      payload: { action: 'click', ref: 'btn-pay', request_id: 'r3' },
      respond
    })

    expect(JSON.parse(answers[0]!.result)).toMatchObject({ ok: false, status: 'stale-ref' })
  })

  it('answers instead of hanging when the guest page cannot be reached', async () => {
    const host: PreviewActHost = {
      executeJavaScript: vi.fn(async () => {
        throw new Error('webview is destroyed')
      }),
      sessionId: SESSION_A
    }

    await answerPreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_A,
      host,
      payload: { action: 'elements', request_id: 'r4' },
      respond
    })

    expect(JSON.parse(answers[0]!.result).message).toContain('could not be reached')
  })

  it('rejects an action it does not implement without running the page', async () => {
    const executed: string[] = []

    await answerPreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_A,
      host: hostFor(SESSION_A, executed),
      payload: { action: 'evaluate', request_id: 'r5' },
      respond
    })

    expect(executed).toEqual([])
    expect(JSON.parse(answers[0]!.result)).toMatchObject({ ok: false, status: 'unsupported' })
  })

  it('uses the registered pane when no host is injected', async () => {
    const executed: string[] = []
    registerPreviewActHost(hostFor(SESSION_A, executed))

    await answerPreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_A,
      payload: { action: 'elements', request_id: 'r6' },
      respond
    })

    expect(executed).toHaveLength(1)
    expect(answers[0]!.request_id).toBe('r6')
  })

  it('ignores a frame with no request id (nothing is blocked on it)', async () => {
    const handled = await answerPreviewAct({
      activeSessionId: SESSION_A,
      eventSessionId: SESSION_A,
      host: hostFor(SESSION_A),
      payload: { action: 'elements' },
      respond
    })

    expect(handled).toBe(false)
    expect(answers).toEqual([])
  })
})

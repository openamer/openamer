import { describe, expect, it } from 'vitest'

import {
  NEW_CHAT_ROUTE,
  primaryRouteSelectedSessionId,
  routeTargetsSession,
  sessionRoute,
  SETTINGS_ROUTE
} from './routes'

const SESS_A = 'sess-a'
const SESS_B = 'sess-b'

describe('primaryRouteSelectedSessionId', () => {
  it('prefers the routed session id over a stale/different store selection (#59305)', () => {
    // The route already committed to B while the store selection hasn't
    // caught up yet (still reads A) — the route wins.
    expect(primaryRouteSelectedSessionId(sessionRoute(SESS_B), SESS_A)).toBe(SESS_B)
  })

  it('returns null on the new-chat route even with a leftover selection from the previous chat', () => {
    expect(primaryRouteSelectedSessionId(NEW_CHAT_ROUTE, SESS_A)).toBeNull()
  })

  it('falls back to the store selection on a non-chat route (settings, overlays)', () => {
    expect(primaryRouteSelectedSessionId(SETTINGS_ROUTE, SESS_A)).toBe(SESS_A)
  })

  it('falls back to the store selection when the route matches the same session', () => {
    expect(primaryRouteSelectedSessionId(sessionRoute(SESS_A), SESS_A)).toBe(SESS_A)
  })

  it('returns null on a non-chat route with no store selection', () => {
    expect(primaryRouteSelectedSessionId(SETTINGS_ROUTE, null)).toBeNull()
  })
})


describe('routeTargetsSession', () => {
  it('matches a session route to its own id — the stale-route signal', () => {
    expect(routeTargetsSession(sessionRoute(SESS_A), SESS_A)).toBe(true)
  })

  it('does not match a route pointing at a different session', () => {
    expect(routeTargetsSession(sessionRoute(SESS_B), SESS_A)).toBe(false)
  })

  it('does not match a non-session route (new chat / pages) or a missing side', () => {
    expect(routeTargetsSession(NEW_CHAT_ROUTE, SESS_A)).toBe(false)
    expect(routeTargetsSession(SETTINGS_ROUTE, SESS_A)).toBe(false)
    expect(routeTargetsSession(null, SESS_A)).toBe(false)
    expect(routeTargetsSession(sessionRoute(SESS_A), null)).toBe(false)
  })

  it('decodes an encoded session id the same way the route reader does', () => {
    const id = 'a/b c'

    expect(routeTargetsSession(sessionRoute(id), id)).toBe(true)
  })
})

import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SETTINGS_ROUTE } from '@/app/routes'
import { getRememberedRoute, setRememberedRoute, setSessions } from '@/store/session'

import { useDesktopIntegrations } from './use-desktop-integrations'

// A session id that exists nowhere — the state a deleted session leaves behind
// in the persisted route, which is what produced the repeat 404s on cold start.
const DEAD = '20260917_094227_8c031b'
const LIVE = '20260922_153122_6ff736'

function Harness({ exhausted }: { exhausted: null | string }) {
  useDesktopIntegrations({
    chatOpen: true,
    hasPreview: false,
    // An overlay route: the hook's own persistence effect skips overlays, so the
    // persisted route under test isn't overwritten by the harness's own path.
    locationPathname: SETTINGS_ROUTE,
    navigate: vi.fn(),
    refreshSessions: vi.fn(),
    resumeExhaustedSessionId: exhausted,
    routedSessionId: null,
    runtimeIdByStoredSessionId: { current: new Map() }
  })

  return null
}

afterEach(() => {
  cleanup()
  setRememberedRoute(null)
  setSessions([])
})

describe('useDesktopIntegrations retired remembered route', () => {
  it('retires the remembered route once its session is confirmed gone', () => {
    setRememberedRoute(`/${DEAD}`)
    setSessions([])

    render(<Harness exhausted={DEAD} />)

    expect(getRememberedRoute()).toBeNull()
  })

  it('keeps the route while the session still exists (transient backend failure)', () => {
    setRememberedRoute(`/${DEAD}`)
    setSessions([{ id: DEAD } as never])

    render(<Harness exhausted={DEAD} />)

    expect(getRememberedRoute()).toBe(`/${DEAD}`)
  })

  it('keeps a remembered route that points at a different session', () => {
    setRememberedRoute(`/${LIVE}`)
    setSessions([{ id: DEAD } as never])

    render(<Harness exhausted={DEAD} />)

    expect(getRememberedRoute()).toBe(`/${LIVE}`)
  })

  it('leaves the route alone while no resume has exhausted', () => {
    setRememberedRoute(`/${DEAD}`)
    setSessions([])

    render(<Harness exhausted={null} />)

    expect(getRememberedRoute()).toBe(`/${DEAD}`)
  })
})

import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { __resetBackendSkinSync, ingestBackendSkin } from './backend-sync'
import { ThemeProvider } from './context'

// The live-authoring loop: OpenAmer writes/edits one skin file and every surface
// repaints. An in-place edit keeps the NAME — only the palette moves.
const bloomberg = (foreground: string) => ({
  name: 'bloomberg',
  colors: { background: '#000000', ui_text: foreground, ui_accent: '#ff8000' }
})

const cssVar = (name: string) => window.document.documentElement.style.getPropertyValue(name)

describe('ThemeProvider ← backend skin sync', () => {
  beforeEach(() => {
    window.localStorage.clear()
    __resetBackendSkinSync()
  })

  afterEach(cleanup)

  it('applies an activated backend skin', () => {
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>
    )

    act(() => ingestBackendSkin(bloomberg('#ff9f0a'), { apply: true }))

    expect(cssVar('--theme-foreground')).toBe('#ff9f0a')
    expect(cssVar('--theme-background-seed')).toBe('#000000')
  })

  it('repaints an in-place edit of the ACTIVE skin (same name, new palette)', () => {
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>
    )

    act(() => ingestBackendSkin(bloomberg('#ff9f0a'), { apply: true }))
    expect(cssVar('--theme-foreground')).toBe('#ff9f0a')

    // Recolor the same skin file. The same-name apply guard correctly no-ops
    // (protects manual desktop picks), so the repaint must come from the
    // registry update reaching the active theme derivation.
    act(() => ingestBackendSkin(bloomberg('#ff2d95'), { apply: true }))
    expect(cssVar('--theme-foreground')).toBe('#ff2d95')
  })

  it('does not repaint an edit to an INACTIVE skin', () => {
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>
    )

    act(() => ingestBackendSkin(bloomberg('#ff9f0a'), { apply: true }))

    // A different skin registered without apply (e.g. seeded on reconnect)
    // must not touch the painted theme.
    act(() =>
      ingestBackendSkin({ name: 'forest', colors: { background: '#001100', ui_text: '#66ff66' } }, { apply: false })
    )
    expect(cssVar('--theme-foreground')).toBe('#ff9f0a')
  })
})

// A theme may own its geometry and its surface mix. chatgpt.com's composer is a
// pill (27.6px) and its dark surface is exactly #212121 — the glass skins'
// default dilution would drag that to ~#1D1D1E, so the mix must be honoured.
describe('ThemeProvider ← theme mix + radius', () => {
  const applySkin = (skin: string, mode: 'dark' | 'light') => {
    window.localStorage.setItem('openamer-desktop-theme-v2', skin)
    window.localStorage.setItem('openamer-desktop-mode-v1', mode)
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>
    )
  }

  beforeEach(() => {
    window.localStorage.clear()
    __resetBackendSkinSync()
    document.documentElement.removeAttribute('style')
  })

  afterEach(cleanup)

  it('uses the undiluted seed + custom radius for the chatgpt skin', () => {
    applySkin('chatgpt', 'dark')

    expect(cssVar('--theme-background-seed')).toBe('#212121')
    expect(cssVar('--theme-mix-chrome')).toBe('100%')
    expect(cssVar('--theme-mix-elevated')).toBe('100%')
    expect(cssVar('--radius-scalar')).toBe('1.15')
  })

  it('restores the default radius and mixes for a skin without overrides', () => {
    applySkin('openamer', 'dark')

    expect(cssVar('--theme-mix-chrome')).toBe('74%')
    expect(cssVar('--radius-scalar')).toBe('0.85')
  })
})

import { describe, expect, it } from 'vitest'

import { BUILTIN_THEME_LIST, DEFAULT_TYPOGRAPHY, EMOJI_FALLBACK } from './presets'

// #40364: none of the UI text/mono fonts carry emoji glyphs, so every font
// stack must end with a color-emoji fallback or emoji render as tofu on
// platforms whose default font lacks them (e.g. Linux).
describe('theme typography emoji fallback (#40364)', () => {
  const stacks: Array<[string, string]> = [
    ['DEFAULT_TYPOGRAPHY.fontSans', DEFAULT_TYPOGRAPHY.fontSans],
    ['DEFAULT_TYPOGRAPHY.fontMono', DEFAULT_TYPOGRAPHY.fontMono],
    // A theme may override only fontMono (fontSans then falls back to the
    // default, which already carries the emoji stack), so skip undefined.
    ...BUILTIN_THEME_LIST.flatMap(theme =>
      (
        [
          [`${theme.name}.fontSans`, theme.typography?.fontSans],
          [`${theme.name}.fontMono`, theme.typography?.fontMono]
        ] as Array<[string, string | undefined]>
      ).filter((entry): entry is [string, string] => typeof entry[1] === 'string')
    )
  ]

  it.each(stacks)('%s includes a color-emoji font', (_label, stack) => {
    expect(stack).toMatch(/Apple Color Emoji|Segoe UI Emoji|Noto Color Emoji|(^|,\s*)emoji\b/)
  })

  it('EMOJI_FALLBACK lists the major platform emoji fonts', () => {
    expect(EMOJI_FALLBACK).toContain('Apple Color Emoji')
    expect(EMOJI_FALLBACK).toContain('Segoe UI Emoji')
    expect(EMOJI_FALLBACK).toContain('Noto Color Emoji')
  })
})

// The chatgpt skin is a measured port of chatgpt.com's own tokens; pin the
// surfaces so a later "harmonise the palettes" pass can't quietly drift them.
describe('chatgpt skin matches the measured chatgpt.com tokens', () => {
  const theme = BUILTIN_THEME_LIST.find(t => t.name === 'chatgpt')

  it('is registered', () => {
    expect(theme).toBeDefined()
  })

  it('keeps the measured light surfaces', () => {
    expect(theme?.colors.background).toBe('#FFFFFF')
    expect(theme?.colors.userBubble).toBe('#F2F2F2')
    expect(theme?.colors.sidebarBackground).toBe('#F9F9F9')
  })

  it('keeps the measured dark surfaces (#212121 / #303030 / #161616)', () => {
    expect(theme?.darkColors?.background).toBe('#212121')
    expect(theme?.darkColors?.card).toBe('#303030')
    expect(theme?.darkColors?.sidebarBackground).toBe('#161616')
  })

  it('asks for undiluted surfaces and the pill composer radius', () => {
    expect(theme?.mix).toEqual({ chrome: 100, sidebar: 100, card: 100, elevated: 100, bubble: 100 })
    expect(theme?.radiusScalar).toBe(1.15)
  })

  it('uses the OS UI stack, not a bundled webfont', () => {
    expect(theme?.typography?.fontSans).toContain('"Segoe UI"')
    expect(theme?.typography?.fontUrl).toBeUndefined()
  })
})

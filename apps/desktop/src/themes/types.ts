/**
 * Desktop app theme model.
 *
 *   colors      — Tailwind color tokens written directly to CSS vars.
 *   darkColors  — optional hand-tuned dark variant (else `colors` is reused
 *                 unchanged for dark, and a synth pass generates light).
 *   typography  — font families + optional stylesheet URL.
 *
 * Everything else (layout, sizing, radius, line-height) lives in styles.css.
 * Add new themes in `presets.ts` — no other code changes needed.
 */

export interface DesktopThemeColors {
  background: string
  foreground: string
  card: string
  cardForeground: string
  muted: string
  mutedForeground: string
  popover: string
  popoverForeground: string
  primary: string
  primaryForeground: string
  secondary: string
  secondaryForeground: string
  accent: string
  accentForeground: string
  border: string
  input: string
  /** Generic focus ring — buttons, inputs, etc. */
  ring: string
  /**
   * Brand-accent stroke — focus rings, streaming cursors, active session
   * pills, branded scrollbars, text selection. Falls back to `ring`.
   * Aliased to the DS `--midground` token.
   */
  midground?: string
  /** Auto-derived from `midground` luminance when omitted. */
  midgroundForeground?: string
  /** Composer outline / focus color. Falls back to `midground`. */
  composerRing?: string
  destructive: string
  destructiveForeground: string
  sidebarBackground?: string
  sidebarBorder?: string
  userBubble?: string
  userBubbleBorder?: string
}

/**
 * Per-theme control over how much of its own seed colour survives in the
 * derived chrome surfaces (`--theme-mix-*` in styles.css). Each value is the
 * seed's share in percent; the remainder falls back to the neutral ramp.
 *
 * The built-in glass skins want a heavily diluted seed (a tinted wash), but a
 * faithful port of an external product needs its exact measured surfaces —
 * `100` means "use the seed unchanged".
 */
export interface DesktopThemeMix {
  /** Main chrome / editor surface. */
  chrome?: number
  /** Sidebar surface. */
  sidebar?: number
  /** Card surface. */
  card?: number
  /** Elevated/popover surface. */
  elevated?: number
  /** User message bubble. */
  bubble?: number
}

export interface DesktopThemeTypography {
  fontSans: string
  fontMono: string
  /** Google/Bunny/self-hosted font stylesheet URL. */
  fontUrl?: string
}

/**
 * Integrated-terminal ANSI palette (xterm `ITheme`, minus `background`).
 *
 * Populated only when a converted VS Code theme ships a full `terminal.ansi*`
 * set; otherwise the terminal keeps its built-in VS Code default palette.
 * `background` is intentionally absent — the pane always paints the live skin
 * surface so it stays translucent.
 */
export interface DesktopTerminalPalette {
  foreground?: string
  cursor?: string
  /** Keeps its source alpha — xterm blends it over the surface. */
  selectionBackground?: string
  black?: string
  red?: string
  green?: string
  yellow?: string
  blue?: string
  magenta?: string
  cyan?: string
  white?: string
  brightBlack?: string
  brightRed?: string
  brightGreen?: string
  brightYellow?: string
  brightBlue?: string
  brightMagenta?: string
  brightCyan?: string
  brightWhite?: string
}

export interface DesktopTheme {
  name: string
  label: string
  description: string
  /** Light palette (also reused for dark when `darkColors` is omitted). */
  colors: DesktopThemeColors
  /** Hand-tuned dark palette. Skins like `openamer` ship one. */
  darkColors?: DesktopThemeColors
  /** Optional overrides for the derived-surface mix ratios. */
  mix?: DesktopThemeMix
  /**
   * Global corner-radius multiplier (styles.css `--radius-scalar`, default
   * 0.85). Raise it for a rounder, softer geometry — a pill composer needs
   * `--radius-2xl` at roughly half the composer's height.
   */
  radiusScalar?: number
  typography?: Partial<DesktopThemeTypography>
  /** Light-variant terminal ANSI palette (also the fallback for dark). */
  terminal?: DesktopTerminalPalette
  /** Dark-variant terminal ANSI palette. Falls back to `terminal`. */
  darkTerminal?: DesktopTerminalPalette
}

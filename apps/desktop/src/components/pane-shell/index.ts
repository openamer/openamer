/**
 * Cross-surface event: toggle-reveal a collapsed pane. Dispatched by the
 * keybinds (⌘B / ⌘G / titlebar toggles on narrow viewports) with the pane id
 * in `detail`; the layout tree's narrow overlays (tree/renderer.tsx) listen
 * and slide the pane over the grid.
 */
// Upstream-Derived: apps/desktop/src/components/pane-shell/index.ts @ 63a9bde77 (MIT)
export const PANE_TOGGLE_REVEAL_EVENT = 'openamer:pane-toggle-reveal'

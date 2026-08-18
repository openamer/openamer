# Changelog

All notable changes to `@openamer-research/ui` are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.17.0

### Component promotion and Radix Dialog consolidation

Promotes reusable components and hooks from `openamer-agent/web` into the shared design system, and consolidates all dialog/modal implementations on Radix UI primitives.

#### Added

- **`Dialog` compound component** — general-purpose modal built on Radix Dialog primitive. Compound API: `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`, `DialogClose`. Dismissible via backdrop click or ESC.
- **`Input`** — styled text input with focus ring, disabled state, courier font.
- **`Label`** — form label with mondwest font, uppercase tracking, peer-disabled opacity.
- **`Separator`** — horizontal/vertical divider with `role="separator"`.
- **`Card`** compound component — `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent` with themeable `--component-card-*` CSS custom properties.
- **`Toast`** — portal-based success/error notification with enter/exit animations.
- **`BottomSheet`** — mobile-first bottom sheet with drag-to-dismiss, backdrop, reduced-motion support.
- **`useToast`** — toast state management with auto-dismiss timer.
- **`useBelowBreakpoint`** — `matchMedia`-based responsive breakpoint query (SSR-safe).
- **`useConfirmDelete`** — generic confirm-delete flow state machine.
- **Forms overview story** — showcases all form controls in one view.
- Toast keyframes (`toast-in`, `toast-out`) in `globals.css`.

#### Changed

- **`ConfirmDialog` rebuilt on Radix AlertDialog** — same external API (`open`, `onCancel`, `onConfirm`, `title`, `description`, `destructive`, `loading`), but ESC handling, focus trapping, scroll lock, and portal rendering are now handled by Radix. Backdrop click does not dismiss (correct for destructive confirms).
- **`Checkbox` migrated to unified `radix-ui` package** — import changed from `@radix-ui/react-checkbox` to `radix-ui`.
- **Dependency:** `@radix-ui/react-checkbox` replaced with unified `radix-ui` package.
- Storybook stories organized into categories (Forms, Feedback, Overlays, Data Display, Layout, Effects).
- Kitchen-sink demo updated to use new `Dialog`.

#### Removed

- **`Modal` component** (`modal/index.tsx`, `modal.css`) — unused by any consumer app; replaced by `Dialog`.
- **`useModalBehavior` hook** — functionality now provided natively by Radix Dialog/AlertDialog primitives.
- Stale `modal.css` import from `globals.css`.

#### Fixed

- Portal text color: dialogs now use `text-foreground-base` for correct rendering outside the blend-mode stack.

## 0.16.0

### Usability overhaul — typography, contrast, theming

This release reworks how the brand uppercase + Mondwest styling and color hierarchy are applied, addressing legibility, contrast, and themability complaints from consumers (notably the OpenAmer Dashboard).

#### Added

- **`text-display` utility** — composable brand display style (`text-transform: uppercase` + `letter-spacing: 0.05em`). Purely typographic; pairs with any font utility.
- **Semantic text-color tokens** — `text-text-primary`, `text-text-secondary`, `text-text-tertiary`, `text-text-disabled`, `text-text-on-accent`, `text-text-display` with WCAG AA-targeted defaults in `globals.css`.

#### Changed

- **Breaking:** `LayoutWrapper` and Storybook shell no longer apply global `uppercase` or `font-mondwest`. Apply `text-display` (and `font-mondwest` where desired) on brand chrome only.
- DS components (`Button`, `Badge`, `Tabs`, `Segmented`, `FilterGroup`, `CopyButton`, `Stats`, `TierCard`, `TerminalDemo`, `Watchlist`) use `text-display` instead of hard-coded `uppercase`.
- Component legibility: micro-type bumped to `text-xs`; inactive/disabled states use semantic tokens instead of stacked opacity.

#### Tooling

- `src/` included in the published tarball.
- Inline source maps embedded in `dist/ui/*.js`.
- Storybook: **Display type** story and **Docs → Changelog** page.

## 0.15.0

### Added

- Storybook autodocs enabled for all components ([#21](https://github.com/OpenAmerResearch/design-language/pull/21)).

## 0.14.2

### Added

- `Checkbox` component built on Radix primitive ([#20](https://github.com/OpenAmerResearch/design-language/pull/20)).

### Fixed

- `defaultChecked` preserved on native input for form reset.
- Checkbox visuals in uncontrolled mode.

## 0.14.1

### Fixed

- Font variable defaults remain in `globals.css`.
- `@font-face` declarations moved out of `globals.css` into optional `fonts.css`.

### Changed

- Documented optional font stylesheet setup in README.

## 0.14.0

### Added

- `unbuild` / `mkdist` library build pipeline.
- `vite-plugin-static-copy` for asset handling in the build.

### Changed

- Bundle size reduced (~4.9 MB → ~1.9 MB).
- Storybook stories reorganized; stories excluded from Vite library entries.

## 0.13.2

### Added

- GitHub Actions workflow for trusted npm publishing on merge to `main`.

### Changed

- Removed manual release script and pnpm workspace file.

### Fixed

- Publish workflow condition syntax.

## 0.13.1

### Fixed

- Text readability improvements.

## 0.13.0

### Changed

- Overlay/canvas performance: pause render loops when hidden/offscreen; cap FPS and DPR.

## 0.12.0

### Fixed

- Eager GPU tier detection to avoid WebGL crash on first render.

## 0.11.0

### Added

- Expanded `Header` component.
- Icon exports.

### Changed

- Overlays decoupled from layout concerns.
- Introduction story updates.

## 0.10.0

### Added

- Unicode/braille spinners.

## 0.9.0

### Added

- `Switch`, `Tabs`, `Segmented`, and `ListItem` components.

## 0.8.0

### Added

- `Select` component.

## 0.7.0

### Fixed

- Button styling.
- Package rename `openamere` → `openamer`.

### Changed

- Badge support improvements.

## 0.6.0

### Fixed

- Button component fixes.

## 0.5.0

### Added

- `Poster` and `TierCard` components.

### Fixed

- Poster and build fixes.

## 0.4.0

### Added

- Migrated components: image distortion, hamburger icon, terminal demo, theme toggle, click-to-copy command blocks.

## 0.3.0

### Added

- Storybook setup.

### Fixed

- Removed Next.js dependencies from the package.

## 0.2.7

### Fixed

- Stats flip animation.

## 0.2.6

### Added

- Flip animation on `Stats`.

## 0.2.5

### Changed

- Global font size adjustments.

## 0.2.4

### Changed

- Slightly increased global font size.

### Fixed

- Hover state for inverted/outlined buttons when foreground alpha is near zero.

## 0.2.3

### Fixed

- Hover state for inverted/outlined on low foreground alpha.

## 0.2.2

### Fixed

- Global CSS selector update.

## 0.2.1

### Changed

- Simplified style setup for consumers.

## 0.2.0

### Added

- Initial tagged release of the shared design system package.

## 0.1.x

Versions `0.1.0`–`0.1.3` were published to npm before git tags were added in this repository. See [npm version history](https://www.npmjs.com/package/@openamer-research/ui?activeTab=versions) for install pins.

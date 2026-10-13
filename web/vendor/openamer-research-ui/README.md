# openamer ui

the shared design system for react ui @ openamer. components, hooks, utils, fonts, overlays, etc.

## setup

`npm i @openamer-research/ui` or `pnpm i @openamer-research/ui`

import the global styles in your app's root css file:

```css
@import 'tailwindcss';
@import '@openamer-research/ui/styles/globals.css';
```

`globals.css` includes the design-system tokens, utilities, component styles,
and default `--font-*` variable values, but does not register font files.
Import the optional font stylesheet first if your app wants CSS-managed
`@font-face` declarations:

```css
@import 'tailwindcss';
@import '@openamer-research/ui/styles/fonts.css';
@import '@openamer-research/ui/styles/globals.css';
```

Next.js apps should prefer `next/font/local` with the exported
`@openamer-research/ui/fonts/*` files and map them to the same `--font-*`
variables. Apps can also provide their own `--font-*` variables while keeping
the design-system utilities from `globals.css`.

## usage

everything exports from the top level export:

```tsx
import {
  Button,
  Grid
  // whatever else!
} from '@openamer-research/ui'
```

## local development

two ways to preview components while editing:

### storybook (per-component, primary)

```
pnpm storybook        # dev server on http://localhost:6006
pnpm build-storybook  # static build → ./storybook-static
```

stories live in `stories/*.stories.tsx`. the **Overview** story re-renders
the entire `/ds` page, so you always have a kitchen-sink view alongside the
isolated component stories. the **Lens** toolbar above the preview cycles
between the lens presets (`0`, `1`, `2`, `3`, `4`, `5`, `5i`, `6`).

### next.js showcase (kitchen-sink, secondary)

```
pnpm dev              # next dev on http://localhost:3000 → redirects to /ds
```

`app/ds/page.tsx` is the same content the Overview story renders.

## publishing

```
pnpm build     # tsc → dist/ + copies css / fonts / assets
```

releases are published automatically when PRs merge to `main`. the github
workflow bumps the package version from the merged PR labels (`major`, `minor`,
or `patch`), pushes the tag, publishes to npm via trusted publishing, and
creates a [GitHub Release](https://github.com/OpenAmerResearch/design-language/releases)
with notes from `CHANGELOG.md`.

before merging:

1. leave `package.json` at the **current published** version on `main` (CI bumps
   it after merge).
2. label the PR so the bump matches your changelog section:

| PR label | bump from `0.15.0` | changelog heading |
| --- | --- | --- |
| `patch` (default) | `0.15.1` | `## 0.15.1` |
| `minor` | `0.16.0` | `## 0.16.0` |
| `major` | `1.0.0` | `## 1.0.0` |

3. add that `## X.Y.Z` section to [`CHANGELOG.md`](./CHANGELOG.md) — release
   notes are pulled from it for npm and GitHub Releases.

the same file is rendered in Storybook under **Docs → Changelog** and shipped in
the npm tarball.

the published tarball ships `dist/`, `src/`, `README.md`, and `CHANGELOG.md`
(see `files` in `package.json`). inline source maps are embedded in `dist/` so
consumers can debug into the TypeScript source.

## deployment

`vercel.json` builds both and serves them on a single Next.js deployment:

- `/` and `/ds` — the Next.js showcase (same as `pnpm dev`)
- `/storybook` — the static Storybook build (copied to `public/storybook/`
  before `next build` so Next serves it like any other static asset)

Want Storybook-only? replace `buildCommand` with `pnpm build-storybook` and
add `"outputDirectory": "storybook-static"`. `app/ds` can stay for local
`pnpm dev` either way — the Overview story renders the same content.

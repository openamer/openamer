# Session notes: asyncapi/website #5755 (desktop dropdown bug) — 2026-09-30

## Pick rationale (candidate scan log)
- Rejected as scam/junk: `bounty-sandbox` repos, `bounty-plaza` (mirror-farms of real
  repos' issues), `relayhop` `[radar]` spam issues, `Scottcjn/rustchain*` (RTC token,
  crypto-not-cash), `Ikalus1988/MisakaNet` (answer-tasks, no codebase).
- Rejected as too big/risky: tenstorrent/tt-metal #58495 ($750 but C++ tile-kernel work
  needing hardware/simulator access — high cost, can't verify locally).
- Rejected as crowded: claude-builders-bounty #1 — Opire bounties are real cash paid on
  merge, but 6+ `/opire try` claims already; only worth it for uncontested issues.
- Chosen: asyncapi/website #5755 — 715★, active daily, clear repro GIF, small UI fix.
  Note: NOT a paid bounty — value is contribution credit/reputation; fine for pipeline.

## The bug + fix pattern (blur-vs-click race)
Symptom: dropdown item click needs multiple clicks on desktop; works on mobile.
Root cause: trigger button closes the list on `onBlur` (`setTimeout(close, 200)`).
On desktop, mousedown on an item blurs the trigger BEFORE the item's click fires,
so the list unmounts and click never lands.

Fix: on every dropdown item, add
```tsx
onMouseDown={(e) => e.preventDefault()}
```
This suppresses the blur (mousedown default action) so onClick still fires. Keep the
existing onClick that handles selection + close. Works for any "button + onBlur-close
list" custom dropdown; no need for relatedTarget bookkeeping.

## React component tests in a TS-scripts jest repo (pitfalls hit live)
- Repo jest config had `testMatch: ['**/tests/**/*.test.*']` — component tests must
  live under `tests/`, NOT a `components/__tests__/` dir (silently "No tests found").
- Babel test config (`tests/babel.test.config.cts`) only had preset-env + preset-typescript.
  JSX in a test file → `SyntaxError: Unexpected token '<'`. Fix: add
  `['@babel/preset-react', { runtime: 'automatic' }]` preset. `@babel/preset-react` was
  already present transitively; verify with `ls node_modules/@babel/preset-react`.
- `@testing-library/react` was NOT installed → `Cannot find module` at suite load.
  Fix (unverified at session end): `npm i -D @testing-library/react @testing-library/jest-dom`.
  Capture as setup-fix, not as "jest can't test React".
- Test technique for the race: `fireEvent.mouseDown(item)` → `fireEvent.blur(trigger)`
  → `fireEvent.click(item)`, then expect `onPageChange` called. That sequence fails on
  the old code and passes on the fixed one.

## Git clone quirk on this Windows host
- `--depth 1 --filter=blob:none` clone "succeeded" but left a phantom dir MSYS `ls`
  couldn't see → later clones failed with "destination path already exists" while
  `rm -rf` said no such dir. Plain `git clone --depth 1` from the parent dir worked.
  If blob-filter clone behaves haunted, fall back to plain depth-1 clone.

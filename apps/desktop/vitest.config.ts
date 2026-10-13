import type { TestProjectConfiguration } from 'vitest/config';
import { defineConfig } from 'vitest/config'

const reactUi: TestProjectConfiguration = {
  extends: './vite.config.ts',
  test: {
    name: 'ui',
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
    // The first test in each file pays jsdom env init + full module transform,
    // which can exceed vitest's 5000ms default under CI/load. 15s gives the
    // cold start headroom without masking genuinely hung tests.
    testTimeout: 30_000
  }
}

const electronNative: TestProjectConfiguration = {
  test: {
    name: 'electron',
    environment: 'node',
    include: ['electron/**/*.test.ts', 'scripts/**.test.{ts,mjs}'],
    // These tests drive real child processes — `git` in throwaway repos and
    // `wsl.exe -l -q` — whose cold start can exceed vitest's 5000ms default
    // under a full-run parallel load (observed at ~5.3s for the WSL probe,
    // 2.6s in isolation). Same headroom the ui project sets, same reason.
    testTimeout: 30_000
  }
}

export default defineConfig({
  test: {
    projects: [reactUi, electronNative],
    // The suite is 341 files across two projects. Left to its default
    // (`cores - 1` = 15 workers here) it oversubscribes a box that is also
    // running the whole OpenAmer stack — gateway, cron, cognition core — and
    // whichever test is slowest to cold-start loses its timeout to scheduling
    // starvation. That shows up as a *different* timeout failure on each full
    // run while every one passes in isolation. Cap the workers so a full run is
    // deterministic; the wall-clock cost is small next to a red suite that
    // means nothing.
    maxWorkers: 4,
    minWorkers: 1
  }
})

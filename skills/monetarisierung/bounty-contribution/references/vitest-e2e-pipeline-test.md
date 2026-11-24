# Known-good E2E pipeline test (copperhead #66) — reference skeleton

This is the distilled shape of the test that passed 2/2 on copperheadhq/copperhead
(vitest + TS). Adapt, don't copy blindly — mock shapes depend on the target repo.

## Skeleton

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import path from 'node:path';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import type { RunOptions, RunResult } from '../src/agent/loop.js'; // repo-specific
import { tempFixtureRepo } from './helpers.js';                    // repo-specific

// hoisted mock — reset in beforeEach, implementations per-test
const mockRunAgentLoop = vi.hoisted(() => vi.fn<(opts: RunOptions) => Promise<RunResult>>());

vi.mock('../src/agent/loop.js', async (importOriginal) => ({
  ...(await importOriginal<object>()), runAgentLoop: mockRunAgentLoop,
}));
// provider-requiring diagnose path: set a dummy key in beforeEach and mock the
// recovery module, else the real diagnose makes a live API call (401 abort).
vi.mock('../src/agent/recovery.js', async (importOriginal) => ({
  ...(await importOriginal<object>()), diagnoseStageFailure: mockDiagnose,
}));
// kiad-backed gates: mock each one with the REAL interface shape
vi.mock('../src/kicad/cli.js', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  runErc: async () => ({ ok: true, violations: [] }),
  runDrc: async () => ({ ok: true, violations: [], unrouted: 0 }),
  exportNetlist: async () => '(netlist (components (comp (ref "R1") (footprint "Lib:Name"))))',
}));
vi.mock('../src/kicad/legibility.js', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  checkLegibility: async () => ({
    findings: [], counts: { error: 0, advisory: 0 },
    skipped: [], disabled: [], suppressed: [], sheets: 1,
  }),
}));
vi.mock('../src/memory/drift.js', async (importOriginal) => ({
  ...(await importOriginal<object>()), checkDrift: async () => [],
}));
vi.mock('../src/kicad/footprints.js', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  missingFootprints: async () => [],
  formatMissingFootprints: () => '',
}));
```

## Fixture-write-order invariant

When a stage's completion contract reads a config file AND an artifact file,
write ALL config fields first, then the artifacts, then persist config ONCE:

```ts
cfg.schematic = 'x.kicad_sch';
cfg.board = 'x.kicad_pcb';
await write(cfg.schematic, SCH);
await write(cfg.board, PCB);
await writeFile(cfgPath, JSON.stringify(cfg), 'utf8');  // persist LAST
```

A write-persist-write-set-persist sequence leaves the loader seeing a stale
config (board=null) and the stage gate rejects with a misleading message
("no board or schematic is configured").

## Board-match artifact (for netlist-compare gates)

If a gate parses the board file for real (`boardFootprints` + `boardMatchesNetlist`),
the mock board must carry the exact netlist part: same ref, same footprint id,
and no pads whose nets contradict the netlist (no nets in the netlist = no pads
on the board is the safe shape).

## Debug technique

When a pipeline test fails without printing stage logs, instrument the failing
expectation: `expect(res.ok, 'LOGS: ' + JSON.stringify(lines)).toBe(true)` —
vitest prints the message with the captured log lines in the assertion error.
Much faster than guessing which gate rejected.
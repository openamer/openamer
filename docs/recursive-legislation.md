# Recursive legislation (DIR-16)

DIR-16 asks the system to evaluate the efficiency of its own directives and to
mutate them when blocked. This document describes what the code actually does,
where the boundary is, and what is still not true.

## What runs

```
gateway housekeeping thread (every GENESIS_EVERY ticks, own 6 h cadence)
        │
        ▼
legislation_tick_if_due()          agent/directive_legislation.py
        │
        ▼
run_cycle()
  ├── audit()                      agent/directive_engine.py
  │     ├── declared status        (IMPLEMENTATIONS, hand-written)
  │     ├── measured status        (memory/genesis/state.json, written by genesis_runtime)
  │     └── runtime effect         (RUNTIME_EFFECTS, live proof the directive changes behaviour)
  ├── detect()                     BLOCKAGE / CONTRADICTION / INEFFICIENCY / OBSOLETE
  ├── propose()                    REPAIR / IMPLEMENT / RETIRE, each with a rationale
  ├── build_candidate()            apply the proposal to a copy
  ├── self_check()                 invariants + renderability + prompt budget
  ├── apply_change()               agent/directive_constitution.py → new hash-chained version
  └── verify_chain()               recompute every hash and parent link → rollback on failure
```

Run it by hand:

```bash
openamer directive --cycle --dry-run   # propose, write nothing
openamer directive --cycle             # propose, gate, apply
openamer directive --history           # version chain + hash verification
```

## The version store

`<home>/memory/genesis/constitution/`

| file | content |
|---|---|
| `v0001.json …` | one file per version: directives, hash, parent hash, action, reason, proposal id |
| `chain.jsonl` | append-only one-line record per version |
| `last_cycle.json` | cadence marker (6 h) |

Nothing is rewritten in place. A rollback is a *new* version whose content
equals an older one, so the chain stays append-only and the history stays
readable in one direction. `verify_chain()` recomputes every hash; a tampered
file or a broken parent link is detected.

## The safety boundary

`agent/directive_constitution.py`, `INVARIANTS` — checked *before* anything
touches disk. A failing candidate leaves no file behind.

| invariant | refuses |
|---|---|
| `ids` | anything but DIR-01..DIR-24 in order (a directive cannot be deleted) |
| `fields` | empty title/scope, rule shorter than 20 chars |
| `protected-present` | removing DIR-03, DIR-16, DIR-20 or DIR-22 |
| `protected-facts` | changing 900,000,000 / 10 % / 9,000,000,000 / 75 % / 15 % / 32 years / halving / 1,350,000,000 / Treasury |
| `not-hollowed` | shrinking a rule below 60 % of its shipped length |

`PROTECTED_IDS` contains **DIR-16 itself**: the mechanism that amends the
constitution is the one rule it may not amend away.

`IMPLEMENT` proposals are never applied. They need code, not a text change, and
`run_cycle` records them as skipped. This is deliberate: a text amendment would
otherwise be able to claim an implementation that does not exist.

## What "ENFORCED" means now

`agent/directive_engine.derive_status()`:

1. a probe verdict of `blocked` → `GATED` (nothing is there);
2. a proven runtime effect → `ENFORCED`;
3. otherwise the measured level, and a declared `ENFORCED` **without** a
   runtime effect is downgraded to `PARTIAL`.

`RUNTIME_EFFECTS` currently has one entry: `DIR-16`, proven by the amendment
gate refusing a deliberately broken candidate at runtime. That is why DIR-03,
DIR-20 and DIR-22 report `PARTIAL` — their numbers are correct and asserted, but
no runtime path reads them to decide anything. **No ENFORCED claim without a
proven runtime effect.**

## Known limitations

- **DIR-03/20/22 lost ENFORCED.** They kept ENFORCED only because an arithmetic
  check on Python constants passed. Under the new rule they are `PARTIAL` until
  something at runtime acts on them (a deployed contract, a ledger, a burn).
  This is a downgrade on purpose, not a regression.
- **The cycle currently finds nothing to do on this install** (0 issues). The
  apply path is exercised by tests, not by live data.
- **DIR-04 still reports two unverified evidence paths.** The kernel tree
  exists at `<repo>/os/kernel/Cargo.toml`, but the claim is written as
  `home:os/kernel/Cargo.toml`, which resolves against `$OPENAMER_HOME` and does
  not find it. The evidence pointer is wrong; the file is there.
- **RETIRE keeps the directive row** and rewrites its rule to say it was
  retired. Deleting the row would break the owner's stable numbering.
- **No signature.** The chain detects tampering by accident and by comparison;
  it does not prove who wrote a version. A hostile process with write access to
  the store can rewrite the chain consistently.
- **`verify_tests` is off by default** in the gateway hook (~10 s). The
  invariant and render checks always run.

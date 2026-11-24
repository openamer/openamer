# Heartbeat organ wiring — orphaned organs and the probe-vs-run split

An "organ" is a subsystem script. An organ can be BUILT and RUNNABLE and still be
DEAD, because **nothing invokes it**. Found 2026-10-05: `homeostasis` /
`calibration` / `metacognition` all ran fine by hand, yet no cron scheduled them
and they appeared in no heartbeat subsystem's `scripts=[...]` → they never
ticked. `last_status: ok` on the heartbeat proved nothing about them.

## Audit in three passes

1. **Missing?** scan for organs you expect (`homeostasis`, `calibration`,
   `metacognition`, `conscience`, `attention`, `regret`, `reputation`).
   Absent = never built.
2. **Orphaned?** for each organ that *exists*, check it appears in a heartbeat
   subsystem's `scripts=[...]` **AND/OR** a cron job. In neither → dead.
3. **Wire it in** — add it to the right subsystem's `scripts=[...]` AND raise
   that subsystem's `timeout` if the organ is heavy. A subsystem that grew to 15
   scripts needs more than the default budget (observed: `meta` → `timeout=180`,
   `system` → `240`), or the tick silently cuts the organ off.

## The split that bites: a TICK must PROBE, never RUN

A heartbeat tick runs every few minutes. Putting the heavy survival job in the
tick blows the subsystem timeout — a full filesystem backup ran ~7 minutes.
Split it:

* the **CRON** does the labour (`backup --now`, publish DNA),
* the **heartbeat** runs a light `*_health.py` **probe** that only checks
  *freshness* (mtime age vs a threshold) and prints nothing when healthy.

## A no-arg script invoked bare by a cron must DO the useful thing

If a new organ's `main()` falls through to `print_help()` on no arguments, its
cron is a silent no-op — it freezes while `last_status` stays `ok`. Make the bare
invocation run the audit/tick. Test: run the script with **zero** arguments and
assert it acted (not that it printed usage).

## Wiring must not collide with another writer

`tools/asi/heartbeat.py` is edited by more than one process (cron writers commit
too). Before editing, confirm no foreign `index.lock` is held; commit narrowly;
**never delete a foreign `index.lock`**. Land heartbeat changes on a branch, not
straight onto a shared `main` that other crons also push to.

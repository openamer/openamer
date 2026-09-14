#!/usr/bin/env python3
"""Cron wrapper for the OpenRouter ranking watchdog.

Why this exists: OpenAmer's scheduler takes the job's `script` field as a bare
filename — it does NOT split arguments. The job was configured as
`openrouter_rank_watch.py --alert-only`, which the scheduler resolved as a
single putatively-named file and failed with
    Script not found: ...\\scripts\\openrouter_rank_watch.py --alert-only
(observed live 2026-09-14, every daily run). A wrapper pins the intended mode
without changing the watchdog's own CLI for interactive use.

Behaviour mirrors `openrouter_rank_watch.py --alert-only`: prints nothing when
the listing is unchanged, the change lines when it moved. Exit code is passed
through unchanged so a genuine read failure (unreadable category) still shows
as a red cron status.
"""
import pathlib
import runpy
import sys

_TARGET = pathlib.Path(__file__).with_name("openrouter_rank_watch.py")

sys.argv = [str(_TARGET), "--alert-only"]
runpy.run_path(str(_TARGET), run_name="__main__")
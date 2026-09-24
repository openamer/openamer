#!/usr/bin/env python3
"""ASI Heartbeat — Cron-Einstiegspunkt.

Wird vom Cron-Job 'asi-heartbeat-tick' alle 5 Minuten aufgerufen.
Führt tick() auf allen fälligen Subsystemen aus in-process.

Aufruf: python tools/asi/heartbeat.py --tick [--system <name>] [--force] [--status]
"""
import sys, os

# Agent-Pfad für Direktimporte
AGENT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
os.chdir(AGENT_DIR)
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from tools.asi.heartbeat import main

if __name__ == "__main__":
    main()
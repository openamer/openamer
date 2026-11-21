---
name: agent-behavioral-security
description: 'Use for agent behavioral security tasks. Candidate synthesized from trend radar; awaiting trial promotion.'
version: 0.1.0
metadata:
  openamer:
    tags: [darwin-candidate, trend-synthesized]
    related_skills: []
platforms: [linux, macos, windows]
---

# Agent Behavioral Security (Darwin Candidate)

## Overview
Behavioral anomaly detection for AI agents: runtime monitoring, deviation alerts, policy enforcement, structured UI protocol analysis.

Synthesized by `darwin_synthesize.py` on 2026-11-21 from trend-radar signals:
- AegisUI: Behavioral Anomaly Detection for Structured User Interface Protocols in AI Agent Systems
- Threat actors use agentic AI tooling to find and abuse exposed secrets - Microsoft
- ThreatFabric announces Agentic AI Risk and Know Your Agent (KYA) - ThreatFabric

## When to use
Whenever a task touches agent behavioral security: research, tool selection, or workflow design
in this area.

## Usage
1. Collect the 3 most relevant sources from the origin signals.
2. Extract concrete practices applicable to OpenAmer (commands, configs, policies).
3. Turn each practice into a verifiable step with a health check.

## Setup / Installation
No external setup required — this skill guides analysis and synthesis work
using the standard OpenAmer toolset (terminal, web, file).

## Example

```bash
# scan the trend report for this topic's latest signals
grep -i "agent" reports/trend-scout-latest.md
```

## Verification
- Candidate is only promotable after `darwin_engine --head-to-head` shows it
  beating an existing related skill OR no related skill exists and a cron
  trial runs error-free.
- Record outcomes in reports/darwin-autopatch.md for fitness scoring.

## Pitfalls
- Do not promote without real execution evidence (see Verification).
- Trend hype != practice: only extract steps that were demonstrated to work.

## Troubleshooting
- If signals are stale (>48h), re-run the trend scout before acting.

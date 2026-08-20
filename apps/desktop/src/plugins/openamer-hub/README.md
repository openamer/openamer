# OpenAmer Hub — Desktop Plugin

Adds 6 new pages to the OpenAmer Desktop sidebar with all Phase 1-25 features.

## Features

| Page | Route | Description |
|------|-------|-------------|
| 🤖 Agent Builder | `/hub/agents` | Create agents from natural language |
| 🧠 Brain Dashboard | `/hub/brain` | Learning loop statistics and growth |
| 👥 Crews & Swarm | `/hub/crews` | Multi-agent orchestration strategies |
| 📊 Trace & Observability | `/hub/trace` | Agent execution browser |
| 🏪 Marketplace | `/hub/marketplace` | Community agents discovery |
| 🎯 Superintelligence | `/hub/super` | System health dashboard (0-100) |

## How it works

The plugin registers:
- **ROUTES_AREA** contributions for each page (full-page views)
- **SIDEBAR_NAV_AREA** contributions for sidebar navigation items

Built with the existing OpenAmer Desktop plugin system — no core changes needed.
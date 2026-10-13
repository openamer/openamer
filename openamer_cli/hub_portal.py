"""
``openamer hub`` — OpenAmer Hub Portal (lokales Web-Dashboard).

Bietet ein eigenständiges HTTP-Dashboard (kein Flask, nur Python
``http.server``) mit REST-API und integrierter HTML-UI für:

  - Provider-Status (OpenRouter, OpenAI, etc.)
  - Modell-Konfiguration
  - Token-Verbrauch & Kosten
  - Skills-Übersicht
  - Memory-Status
  - Superintelligence Score

CLI usage::

    openamer hub start [--port 5000]
    openamer hub status
    openamer hub stop
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import argparse

# ---------------------------------------------------------------------------
# Versuch, OpenAmer-Module zu importieren (alle optional, damit das
# Dashboard auch bei fehlenden Abhängigkeiten starten kann)
# ---------------------------------------------------------------------------

try:
    from openamer_cli.config import load_config, get_openamer_home
except ImportError:
    load_config = lambda: None  # type: ignore[assignment]
    get_openamer_home = lambda: Path.home() / ".openamer"

try:
    from openamer_cli.superintelligence import (
        check_all_systems,
        SuperintelligenceStatus,
    )
except ImportError:
    check_all_systems = lambda: SuperintelligenceStatus()  # type: ignore[assignment]

    @dataclass
    class SuperintelligenceStatus:  # type: ignore[no-redef]
        brain_learning_loop: str = "unknown"
        a2a_swarm_connectivity: str = "unknown"
        skills_count: str = "unknown"
        skills_improvement_rate: str = "unknown"
        memory_usage: str = "unknown"
        memory_growth: str = "unknown"
        computer_use_readiness: str = "unknown"
        multi_agent_orchestration: str = "unknown"
        overall_score: int = 0

try:
    from openamer_cli.cost_dashboard import CostStore
except ImportError:
    CostStore = None  # type: ignore[assignment,misc]

try:
    from openamer_cli.skills_hub import list_skills
except ImportError:

    def list_skills() -> list[dict]:  # type: ignore[misc]
        return []


# ---------------------------------------------------------------------------
# Dashboard-Daten
# ---------------------------------------------------------------------------

_PORTAL_VERSION = "1.0.0"

_SYSTEM_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenAmer Hub</title>
<style>
  /* ── Reset & Dark Theme ── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #1c2128;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
    --radius: 8px;
    --shadow: 0 1px 3px rgba(0,0,0,.3);
  }
  html { font-size: 15px; }
  body {
    font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen,Ubuntu,Cantarell,sans-serif;
    background: var(--bg); color: var(--text); min-height: 100vh;
    display: flex; flex-direction: column;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }

  /* ── Header ── */
  header {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem;
    flex-wrap: wrap;
  }
  header h1 {
    font-size: 1.25rem; font-weight: 600;
    display: flex; align-items: center; gap: .5rem;
  }
  header h1 .logo { color: var(--accent); }
  .header-right { margin-left: auto; display: flex; align-items: center; gap: .75rem; }
  .version-badge {
    font-size: .75rem; background: var(--surface2); border: 1px solid var(--border);
    border-radius: 999px; padding: .15rem .6rem; color: var(--text-dim);
  }
  .last-update { font-size: .8rem; color: var(--text-dim); }

  /* ── Main Grid ── */
  main { flex: 1; padding: 1.25rem 1.5rem; }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1rem; max-width: 1400px; margin: 0 auto;
  }

  /* ── Cards ── */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); box-shadow: var(--shadow);
    overflow: hidden; transition: border-color .15s;
  }
  .card:hover { border-color: #3b434c; }
  .card-header {
    background: var(--surface2); padding: .65rem 1rem;
    font-weight: 600; font-size: .9rem;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: .5rem;
  }
  .card-body { padding: 1rem; }

  /* ── Status-Badge ── */
  .badge {
    display: inline-block; font-size: .75rem; font-weight: 600;
    padding: .15rem .5rem; border-radius: 999px; text-transform: uppercase;
  }
  .badge-pass  { background: #2ea04333; color: var(--green); border: 1px solid #2ea04366; }
  .badge-warn  { background: #d2992233; color: var(--yellow); border: 1px solid #d2992266; }
  .badge-fail  { background: #f8514933; color: var(--red); border: 1px solid #f8514966; }
  .badge-ok    { background: #2ea04333; color: var(--green); border: 1px solid #2ea04366; }
  .badge-error { background: #f8514933; color: var(--red); border: 1px solid #f8514966; }
  .badge-warn-label { background: #d2992233; color: var(--yellow); border: 1px solid #d2992266; }

  /* ── Score Ring ── */
  .score-ring {
    width: 72px; height: 72px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; font-weight: 700;
    flex-shrink: 0;
  }
  .score-excellent { background: conic-gradient(var(--green) 0deg 270deg, var(--surface2) 270deg 360deg); }
  .score-good      { background: conic-gradient(var(--accent) 0deg 210deg, var(--surface2) 210deg 360deg); }
  .score-fair      { background: conic-gradient(var(--yellow) 0deg 150deg, var(--surface2) 150deg 360deg); }
  .score-poor      { background: conic-gradient(var(--red) 0deg 90deg, var(--surface2) 90deg 360deg); }

  .score-row { display: flex; align-items: center; gap: 1rem; }

  /* ── Stat Rows ── */
  .stat-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: .35rem 0; border-bottom: 1px solid #21262d;
    font-size: .85rem;
  }
  .stat-row:last-child { border-bottom: none; }
  .stat-label { color: var(--text-dim); }
  .stat-value { font-weight: 500; }

  /* ── Provider Table ── */
  .provider-table { width: 100%; border-collapse: collapse; font-size: .85rem; }
  .provider-table th {
    text-align: left; padding: .4rem .5rem; color: var(--text-dim);
    font-weight: 500; border-bottom: 1px solid var(--border);
  }
  .provider-table td {
    padding: .4rem .5rem; border-bottom: 1px solid #21262d;
  }
  .provider-table tr:last-child td { border-bottom: none; }

  /* ── Skill List ── */
  .skill-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: .3rem 0; border-bottom: 1px solid #21262d;
    font-size: .85rem;
  }
  .skill-item:last-child { border-bottom: none; }
  .skill-name { font-weight: 500; }
  .skill-category { font-size: .75rem; color: var(--text-dim); }

  /* ── Usage Chart (inline bar) ── */
  .usage-bar {
    height: 6px; background: var(--surface2); border-radius: 999px;
    overflow: hidden; margin-top: .25rem;
  }
  .usage-bar-fill {
    height: 100%; border-radius: 999px; background: var(--accent);
    transition: width .5s ease;
  }

  /* ── Loading & Error States ── */
  .loading {
    text-align: center; padding: 2rem 1rem; color: var(--text-dim);
  }
  .loading .spinner {
    display: inline-block; width: 1.5rem; height: 1.5rem;
    border: 2px solid var(--border); border-top-color: var(--accent);
    border-radius: 50%; animation: spin .6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error-state { color: var(--red); text-align: center; padding: 1rem; }
  .empty-state { color: var(--text-dim); text-align: center; padding: 1rem; font-size: .85rem; }

  /* ── Responsive ── */
  @media (max-width: 768px) {
    header { flex-direction: column; align-items: flex-start; }
    .header-right { margin-left: 0; width: 100%; justify-content: space-between; }
    .grid { grid-template-columns: 1fr; }
  }

  /* ── Memory Bar ── */
  .memory-bar-container { margin-top: .5rem; }
  .memory-bar {
    height: 8px; background: var(--surface2); border-radius: 999px; overflow: hidden;
  }
  .memory-bar-fill {
    height: 100%; border-radius: 999px; transition: width .5s ease;
  }
  .memory-bar-text {
    display: flex; justify-content: space-between; font-size: .8rem;
    color: var(--text-dim); margin-top: .25rem;
  }
</style>
</head>
<body>
<header>
  <h1><span class="logo">⬡</span> OpenAmer Hub</h1>
  <span class="version-badge">v${PORTAL_VERSION}</span>
  <div class="header-right">
    <span class="last-update" id="lastUpdate">—</span>
    <span class="version-badge" id="statusIndicator">⟳ lädt…</span>
  </div>
</header>
<main>
  <div class="grid" id="dashboardGrid">
    <!-- Cards werden von JS befüllt -->
  </div>
</main>

<script>
// ── Konfiguration ──
const REFRESH_INTERVAL_MS = 5000;     // 5 Sekunden
const RETRY_DELAY_MS    = 3000;       // bei Fehler

// ── State ──
let _timeoutId = null;

// ── Hilfsfunktionen ──
function escapeHtml(text) {
  if (text == null) return '—';
  const d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}

function badge(status) {
  const s = (status || 'unknown').toLowerCase();
  if (s === 'pass' || s === 'ok' || s === 'healthy' || s === 'active') {
    return '<span class="badge badge-pass">' + escapeHtml(status) + '</span>';
  }
  if (s === 'warn' || s === 'degraded' || s === 'rate_limited') {
    return '<span class="badge badge-warn">' + escapeHtml(status) + '</span>';
  }
  if (s === 'fail' || s === 'error' || s === 'inactive' || s === 'disconnected') {
    return '<span class="badge badge-fail">' + escapeHtml(status) + '</span>';
  }
  return '<span class="badge badge-warn-label">' + escapeHtml(status) + '</span>';
}

function scoreClass(score) {
  if (score >= 80) return 'score-excellent';
  if (score >= 60) return 'score-good';
  if (score >= 40) return 'score-fair';
  return 'score-poor';
}

function scoreLabel(score) {
  if (score >= 80) return 'Exzellent';
  if (score >= 60) return 'Gut';
  if (score >= 40) return 'Mäßig';
  return 'Kritisch';
}

// ── Anzeige letztes Update ──
function updateTimestamp() {
  const now = new Date();
  document.getElementById('lastUpdate').textContent =
    now.toLocaleTimeString('de-DE', { hour12: false });
}

// ── Karten-Builder ──

function cardStatus(statusData) {
  const si = statusData || {};
  const score = si.overall_score != null ? si.overall_score : 0;
  return `
    <div class="card">
      <div class="card-header">⬡ System-Status</div>
      <div class="card-body">
        <div class="score-row">
          <div class="score-ring ${scoreClass(score)}">${score}</div>
          <div>
            <div style="font-weight:600;font-size:1.1rem;">${scoreLabel(score)}</div>
            <div style="font-size:.8rem;color:var(--text-dim);">
              Tools: ${escapeHtml(si.tools_count ?? '?')} &middot;
              Skills: ${escapeHtml(si.skills_count ?? '?')}
            </div>
          </div>
        </div>
        <div style="margin-top:.75rem;">
          <div class="stat-row"><span class="stat-label">Brain Learning</span><span>${badge(si.brain_learning_loop)}</span></div>
          <div class="stat-row"><span class="stat-label">A2A Swarm</span><span>${badge(si.a2a_swarm_connectivity)}</span></div>
          <div class="stat-row"><span class="stat-label">Memory Usage</span><span>${badge(si.memory_usage)}</span></div>
          <div class="stat-row"><span class="stat-label">Computer Use</span><span>${badge(si.computer_use_readiness)}</span></div>
          <div class="stat-row"><span class="stat-label">Multi-Agent</span><span>${badge(si.multi_agent_orchestration)}</span></div>
        </div>
      </div>
    </div>
  `;
}

function cardModel(modelData) {
  const m = modelData || {};
  const modelName = m.model || '—';
  const provider = m.provider || '—';
  return `
    <div class="card">
      <div class="card-header">⚙ Modell-Konfiguration</div>
      <div class="card-body">
        <div class="stat-row"><span class="stat-label">Modell</span><span class="stat-value">${escapeHtml(modelName)}</span></div>
        <div class="stat-row"><span class="stat-label">Provider</span><span class="stat-value">${escapeHtml(provider)}</span></div>
        <div class="stat-row"><span class="stat-label">Base URL</span><span class="stat-value" style="font-size:.8rem;">${escapeHtml(m.base_url || '—')}</span></div>
        <div class="stat-row"><span class="stat-label">Fallback-Kette</span><span class="stat-value">${escapeHtml(m.fallback_chain || 'keine')}</span></div>
      </div>
    </div>
  `;
}

function cardUsage(usageData) {
  const u = usageData || {};
  const totalTokens = u.total_tokens ?? 0;
  const totalCost   = u.total_cost ?? '0.00';
  const tokensIn    = u.tokens_in ?? 0;
  const tokensOut   = u.tokens_out ?? 0;
  const sessionCount = u.session_count ?? 0;
  // maxTokens aus Konfiguration oder Default
  const maxTokens = u.max_monthly_tokens || 50000000;
  const pct = maxTokens > 0 ? Math.min(100, (totalTokens / maxTokens) * 100) : 0;
  return `
    <div class="card">
      <div class="card-header">💰 Token-Verbrauch</div>
      <div class="card-body">
        <div class="stat-row"><span class="stat-label">Gesamt-Token</span><span class="stat-value">${totalTokens.toLocaleString('de-DE')}</span></div>
        <div class="stat-row"><span class="stat-label">Input-Token</span><span class="stat-value">${tokensIn.toLocaleString('de-DE')}</span></div>
        <div class="stat-row"><span class="stat-label">Output-Token</span><span class="stat-value">${tokensOut.toLocaleString('de-DE')}</span></div>
        <div class="stat-row"><span class="stat-label">Gesamtkosten</span><span class="stat-value">${escapeHtml(totalCost)} USD</span></div>
        <div class="stat-row"><span class="stat-label">Sitzungen</span><span class="stat-value">${sessionCount}</span></div>
        <div class="usage-bar"><div class="usage-bar-fill" style="width:${pct.toFixed(1)}%"></div></div>
        <div style="font-size:.75rem;color:var(--text-dim);margin-top:.2rem;text-align:right;">${pct.toFixed(1)}% des Limits</div>
      </div>
    </div>
  `;
}

function cardProviders(providers) {
  const list = Array.isArray(providers) ? providers : [];
  if (list.length === 0) {
    return `
      <div class="card">
        <div class="card-header">🔌 Provider</div>
        <div class="card-body"><div class="empty-state">Keine Provider konfiguriert</div></div>
      </div>`;
  }
  const rows = list.map(p => `
    <tr>
      <td>${escapeHtml(p.name)}</td>
      <td>${badge(p.status)}</td>
      <td style="font-size:.8rem;color:var(--text-dim);">${escapeHtml(p.model || '—')}</td>
      <td style="font-size:.8rem;">${escapeHtml(p.tokens || '—')}</td>
    </tr>
  `).join('');
  return `
    <div class="card">
      <div class="card-header">🔌 Provider-Status</div>
      <div class="card-body">
        <table class="provider-table">
          <thead><tr><th>Name</th><th>Status</th><th>Modell</th><th>Token</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function cardSkills(skillsData) {
  const list = Array.isArray(skillsData) ? skillsData : [];
  if (list.length === 0) {
    return `
      <div class="card">
        <div class="card-header">🧠 Skills (${list.length})</div>
        <div class="card-body"><div class="empty-state">Keine Skills gefunden</div></div>
      </div>`;
  }
  const items = list.slice(0, 20).map(s => `
    <div class="skill-item">
      <span class="skill-name">${escapeHtml(s.name || '—')}</span>
      <span class="skill-category">${escapeHtml(s.category || '—')}</span>
    </div>
  `).join('');
  const more = list.length > 20 ? `<div class="skill-item" style="color:var(--text-dim);font-size:.8rem;">… und ${list.length - 20} weitere</div>` : '';
  return `
    <div class="card">
      <div class="card-header">🧠 Skills (${list.length})</div>
      <div class="card-body">${items}${more}</div>
    </div>
  `;
}

function cardMemory(memoryData) {
  const m = memoryData || {};
  const memFiles   = m.memory_files ?? 0;
  const memSize    = m.memory_size_mb ?? '0.0';
  const vectorSize = m.vector_size_mb ?? '0.0';
  const memPct     = m.usage_pct ?? 0;
  return `
    <div class="card">
      <div class="card-header">💾 Memory</div>
      <div class="card-body">
        <div class="stat-row"><span class="stat-label">Memory-Dateien</span><span class="stat-value">${memFiles}</span></div>
        <div class="stat-row"><span class="stat-label">Memory-Größe</span><span class="stat-value">${escapeHtml(memSize)} MB</span></div>
        <div class="stat-row"><span class="stat-label">Vector Memory</span><span class="stat-value">${escapeHtml(vectorSize)} MB</span></div>
        <div class="memory-bar-container">
          <div class="memory-bar"><div class="memory-bar-fill" style="width:${memPct}%;background:${memPct > 80 ? 'var(--red)' : memPct > 50 ? 'var(--yellow)' : 'var(--green)'}"></div></div>
          <div class="memory-bar-text"><span>Speichernutzung</span><span>${memPct}%</span></div>
        </div>
      </div>
    </div>
  `;
}

// ── Dashboard rendern ──
function renderDashboard(data) {
  const grid = document.getElementById('dashboardGrid');
  grid.innerHTML = [
    cardStatus(data.status),
    cardModel(data.model),
    cardUsage(data.usage),
    cardProviders(data.providers),
    cardSkills(data.skills),
    cardMemory(data.memory),
  ].join('');
  updateTimestamp();
}

// ── Fehlerzustand ──
function renderError(message) {
  document.getElementById('dashboardGrid').innerHTML = `
    <div class="card" style="grid-column:1/-1;">
      <div class="card-body error-state">⚠ ${escapeHtml(message)}</div>
    </div>
  `;
  document.getElementById('statusIndicator').textContent = '⚠ Fehler';
  document.getElementById('statusIndicator').className = 'version-badge';
}

// ── Daten laden ──
async function fetchAll() {
  const statusEl = document.getElementById('statusIndicator');
  statusEl.textContent = '⟳ aktualisiere…';
  statusEl.className = 'version-badge';

  try {
    const [statusRes, modelRes, usageRes, providersRes, skillsRes, memoryRes] = await Promise.all([
      fetch('/api/status').then(r => r.ok ? r.json() : Promise.reject(r.status)),
      fetch('/api/model').then(r => r.ok ? r.json() : Promise.reject(r.status)),
      fetch('/api/usage').then(r => r.ok ? r.json() : Promise.reject(r.status)),
      fetch('/api/providers').then(r => r.ok ? r.json() : Promise.reject(r.status)),
      fetch('/api/skills').then(r => r.ok ? r.json() : Promise.reject(r.status)),
      fetch('/api/memory').then(r => r.ok ? r.json() : Promise.reject(r.status)),
    ]);

    renderDashboard({
      status: statusRes,
      model: modelRes,
      usage: usageRes,
      providers: providersRes,
      skills: skillsRes,
      memory: memoryRes,
    });

    statusEl.textContent = '✓ aktiv';
    statusEl.className = 'badge badge-pass';
  } catch (err) {
    console.error('Hub fetch error:', err);
    renderError('Verbindung zum Hub-Server verloren — erneuter Versuch in 3s …');
    statusEl.textContent = '⟳ Fehler';
    statusEl.className = 'badge badge-fail';
    // Retry after delay
    _timeoutId = setTimeout(fetchAll, RETRY_DELAY_MS);
    return;
  }

  // Nächsten Refresh planen
  _timeoutId = setTimeout(fetchAll, REFRESH_INTERVAL_MS);
}

// ── Start ──
document.addEventListener('DOMContentLoaded', () => {
  fetchAll();
});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Hilfsfunktionen für API-Daten
# ---------------------------------------------------------------------------


def _get_openamer_home() -> Path:
    """Ermittelt OPENAMER_HOME."""
    try:
        return get_openamer_home()
    except Exception:
        return Path.home() / ".openamer"


def _get_superintelligence_status() -> dict[str, Any]:
    """Sammelt Superintelligence-Status-Daten."""
    try:
        si = check_all_systems()
        if isinstance(si, SuperintelligenceStatus):
            return {
                "overall_score": si.overall_score,
                "brain_learning_loop": si.brain_learning_loop,
                "a2a_swarm_connectivity": si.a2a_swarm_connectivity,
                "skills_count": si.skills_count,
                "skills_improvement_rate": si.skills_improvement_rate,
                "memory_usage": si.memory_usage,
                "memory_growth": si.memory_growth,
                "computer_use_readiness": si.computer_use_readiness,
                "multi_agent_orchestration": si.multi_agent_orchestration,
            }
    except Exception:
        pass
    return {"overall_score": 0}


def _get_model_config() -> dict[str, Any]:
    """Liest die aktuelle Modell-Konfiguration."""
    try:
        cfg = load_config() or {}
        model_cfg = cfg.get("model", {})
        if isinstance(model_cfg, dict):
            return {
                "model": model_cfg.get("default", model_cfg.get("name", "")),
                "provider": model_cfg.get("provider", ""),
                "base_url": model_cfg.get("base_url", ""),
                "fallback_chain": model_cfg.get("fallbacks", []),
            }
    except Exception:
        pass
    return {"model": "", "provider": "", "base_url": "", "fallback_chain": []}


def _get_token_usage() -> dict[str, Any]:
    """Ermittelt Token-Verbrauch aus CostStore (falls verfügbar)."""
    result: dict[str, Any] = {
        "total_tokens": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "total_cost": "0.00",
        "session_count": 0,
        "max_monthly_tokens": 50000000,
    }
    if CostStore is None:
        return result
    try:
        home = _get_openamer_home()
        store = CostStore(str(home / "state" / "costs.db"))
        summary = store.get_summary()
        if summary:
            result["total_tokens"] = summary.get("total_tokens", 0)
            result["tokens_in"] = summary.get("tokens_in", 0)
            result["tokens_out"] = summary.get("tokens_out", 0)
            result["total_cost"] = str(summary.get("total_cost", "0.00"))
            result["session_count"] = summary.get("session_count", 0)
        return result
    except Exception:
        return result


def _get_providers() -> list[dict[str, Any]]:
    """Sammelt Provider-Statusinformationen."""
    providers: list[dict[str, Any]] = []
    try:
        cfg = load_config() or {}
        model_cfg = cfg.get("model", {})
        active_provider = (
            model_cfg.get("provider", "").lower() if isinstance(model_cfg, dict) else ""
        )

        # Bekannte Provider
        known = [
            "openrouter",
            "openai",
            "anthropic",
            "google",
            "deepseek",
            "xai",
            "groq",
            "together",
        ]
        for name in known:
            status = "active" if name == active_provider else "inactive"
            providers.append({
                "name": name,
                "status": status,
                "model": model_cfg.get("default", "") if name == active_provider else "",
                "tokens": "",
            })

        # OpenRouter als Default hervorheben
        if not active_provider:
            providers.insert(
                0,
                {"name": "openrouter", "status": "active", "model": "", "tokens": ""},
            )
    except Exception:
        pass
    return providers


def _get_skills_list() -> list[dict[str, Any]]:
    """Listet installierte Skills auf."""
    try:
        skills = list_skills()
        return [{"name": s.get("name", "—"), "category": s.get("category", "")} for s in skills]
    except Exception:
        return []


def _get_memory_status() -> dict[str, Any]:
    """Ermittelt Memory-Status aus dem Dateisystem."""
    result: dict[str, Any] = {
        "memory_files": 0,
        "memory_size_mb": "0.0",
        "vector_size_mb": "0.0",
        "usage_pct": 0,
    }
    try:
        home = _get_openamer_home()
        mem_dir = home / "memories"
        vec_dir = home / "vector_memory"

        if mem_dir.is_dir():
            files = list(mem_dir.rglob("*"))
            result["memory_files"] = sum(1 for f in files if f.is_file())
            size = sum(f.stat().st_size for f in files if f.is_file())
            result["memory_size_mb"] = round(size / (1024 * 1024), 1)

        if vec_dir.is_dir():
            vfiles = list(vec_dir.rglob("*"))
            vsize = sum(f.stat().st_size for f in vfiles if f.is_file())
            result["vector_size_mb"] = round(vsize / (1024 * 1024), 1)

        # Speichernutzung (willkürlich, basierend auf Dateigröße)
        total_mb = float(result["memory_size_mb"]) + float(result["vector_size_mb"])
        result["usage_pct"] = min(100, round((total_mb / 500) * 100))
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------


class _HubRequestHandler(BaseHTTPRequestHandler):
    """HTTP-Handler für das Hub Dashboard."""

    # Mapping: Pfad → (data_fn, content_type)
    _API_ROUTES: dict[str, tuple] = {}

    # Referenz auf die HubPortal-Instanz (wird bei Start gesetzt)
    portal: HubPortal = None  # type: ignore[assignment]

    def log_message(self, format: str, *args: Any) -> None:
        """Leise loggen (nur Anfragen-Pfad + Status)."""
        try:
            if self.portal and getattr(self.portal, "quiet", False):
                return
        except Exception:
            pass
        sys.stderr.write(f"[Hub] {self.address_string()} - {format % args}\n")

    def _send_json(self, data: Any, status: int = 200) -> None:
        """JSON-Antwort senden."""
        payload = json.dumps(data, ensure_ascii=False, default=str)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(payload.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def _send_html(self, html: str, status: int = 200) -> None:
        """HTML-Antwort senden."""
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_404(self) -> None:
        self._send_json({"error": "not_found", "message": "Endpunkt nicht gefunden"}, 404)

    def _send_500(self, exc: Exception) -> None:
        self._send_json({"error": "server_error", "message": str(exc)}, 500)

    def do_GET(self) -> None:
        """GET-Dispatch."""
        path = self.path.split("?")[0]  # Query-String entfernen
        try:
            if path == "/":
                self._send_html(self.portal.render_dashboard())
            elif path == "/api/status":
                self._send_json(self.portal._collect_status())
            elif path == "/api/model":
                self._send_json(_get_model_config())
            elif path == "/api/usage":
                self._send_json(_get_token_usage())
            elif path == "/api/providers":
                self._send_json(_get_providers())
            elif path == "/api/skills":
                self._send_json(_get_skills_list())
            elif path == "/api/memory":
                self._send_json(_get_memory_status())
            else:
                self._send_404()
        except Exception as exc:
            self._send_500(exc)

    do_POST = do_GET  # POST same as GET for simplicity


# ---------------------------------------------------------------------------
# HubPortal Klasse
# ---------------------------------------------------------------------------


@dataclass
class HubPortal:
    """Lokales Web-Dashboard für OpenAmer.

    Startet einen eigenständigen HTTP-Server (kein Flask) und serviert
    eine interaktive HTML-Dashboard-Seite mit Live-Updates.
    """

    port: int = 5000
    host: str = "127.0.0.1"
    quiet: bool = True
    _server: HTTPServer | None = None
    _thread: threading.Thread | None = None

    # ── Lifecycle ──

    def start(self, port: int | None = None) -> HTTPServer:
        """Startet den HTTP-Server (blockiert nicht).

        Args:
            port: Port zum Binden (überschreibt ``self.port``).

        Returns:
            Die ``HTTPServer``-Instanz.
        """
        if self._server is not None:
            print(f"[Hub] Dashboard läuft bereits auf http://{self.host}:{self.port}")
            return self._server

        if port is not None:
            self.port = port

        # Handler mit Portal-Referenz versorgen
        handler = type(
            "_BoundHandler",
            (_HubRequestHandler,),
            {"portal": self},
        )

        self._server = HTTPServer((self.host, self.port), handler)
        # Bei auto-assigned port (port=0) den tatsächlichen Port übernehmen
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="hub-portal",
        )
        self._thread.start()

        print(f"[Hub] OpenAmer Hub Dashboard gestartet → http://{self.host}:{self.port}")
        return self._server

    def stop(self) -> None:
        """Stoppt den HTTP-Server."""
        if self._server is None:
            print("[Hub] Kein aktiver Server gefunden.")
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None
        print("[Hub] Dashboard gestoppt.")

    @property
    def is_running(self) -> bool:
        """Ob der Server läuft."""
        return self._server is not None and self._thread is not None

    # ── Dashboard HTML ──

    def render_dashboard(self) -> str:
        """Gibt die Dashboard-HTML-Seite zurück."""
        return _SYSTEM_DASHBOARD_HTML.replace("${PORTAL_VERSION}", _PORTAL_VERSION)

    # ── API Data ──

    def _collect_status(self) -> dict[str, Any]:
        """Sammelt den Systemstatus für ``/api/status``."""
        si = _get_superintelligence_status()
        model_cfg = _get_model_config()
        skills = _get_skills_list()
        providers = _get_providers()
        tools_count = len(providers)

        return {
            "version": _PORTAL_VERSION,
            "overall_score": si.get("overall_score", 0),
            "tools_count": tools_count,
            "skills_count": len(skills),
            "brain_learning_loop": si.get("brain_learning_loop", "unknown"),
            "a2a_swarm_connectivity": si.get("a2a_swarm_connectivity", "unknown"),
            "memory_usage": si.get("memory_usage", "unknown"),
            "memory_growth": si.get("memory_growth", "unknown"),
            "computer_use_readiness": si.get("computer_use_readiness", "unknown"),
            "multi_agent_orchestration": si.get("multi_agent_orchestration", "unknown"),
            "active_model": model_cfg.get("model", ""),
            "active_provider": model_cfg.get("provider", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Module-Level Singleton
# ---------------------------------------------------------------------------

_portal_singleton: HubPortal | None = None


def _get_portal() -> HubPortal:
    """Liefert die (einmalig erzeugte) HubPortal-Instanz."""
    global _portal_singleton
    if _portal_singleton is None:
        _portal_singleton = HubPortal()
    return _portal_singleton


# ---------------------------------------------------------------------------
# CLI-Befehle (aufgerufen aus main.py)
# ---------------------------------------------------------------------------


def cmd_hub(args) -> int:
    """Dispatch für ``openamer hub <subcommand>``."""
    sub = getattr(args, "hub_command", None)
    if sub == "start":
        return _cmd_hub_start(args)
    if sub == "status":
        return _cmd_hub_status(args)
    if sub == "stop":
        return _cmd_hub_stop(args)
    print("Unbekannter hub-Befehl. Verwende: openamer hub {start|status|stop}", file=sys.stderr)
    return 1


def _cmd_hub_start(args) -> int:
    """``openamer hub start [--port PORT]``."""
    port = getattr(args, "port", 5000)
    portal = HubPortal(port=port, quiet=False)
    portal.start()
    print()
    print("  Dashboard: http://127.0.0.1:{}/".format(port))
    print("  API:       http://127.0.0.1:{}/api/".format(port))
    print()
    print("  Drücke Ctrl+C zum Stoppen.")
    print()
    try:
        while portal.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        portal.stop()
    return 0


def _cmd_hub_status(args) -> int:
    """``openamer hub status``."""
    if _portal_singleton and _portal_singleton.is_running:
        print(f"[Hub] Dashboard AKTIV → http://{_portal_singleton.host}:{_portal_singleton.port}")
        return 0
    # Nach Prozess-Scan: laufen andere Instanzen?
    # (Einfach prüfen, ob Port bereits belegt ist)
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port = getattr(args, "port", 5000)
    try:
        s.bind(("127.0.0.1", port))
        print(f"[Hub] Dashboard INAKTIV (Port {port} frei).")
        s.close()
        return 0
    except OSError:
        print(f"[Hub] Dashboard aktiv auf Port {port} (von externem Prozess).")
        s.close()
        return 0


def _cmd_hub_stop(args) -> int:
    """``openamer hub stop``."""
    if _portal_singleton and _portal_singleton.is_running:
        _portal_singleton.stop()
        return 0
    print("[Hub] Kein aktives Dashboard gefunden.")
    return 0


# ---------------------------------------------------------------------------
# Parser-Registrierung
# ---------------------------------------------------------------------------


def add_parser(subparsers) -> None:
    """Registriert den ``openamer hub`` Subbefehl auf *subparsers*.

    Aufruf aus ``main.py``::

        from openamer_cli.hub_portal import add_parser as add_hub_parser
        add_hub_parser(subparsers)
    """
    hub_parser = subparsers.add_parser(
        "hub",
        help="OpenAmer Hub Dashboard — lokales Web-Dashboard",
        description=(
            "Starte das OpenAmer Hub Dashboard — ein lokales Web-Dashboard "
            "mit Provider-Status, Modell-Konfiguration, Token-Verbrauch, "
            "Skills-Übersicht und Superintelligence Score."
        ),
    )
    hub_sub = hub_parser.add_subparsers(dest="hub_command")

    # hub start
    start_parser = hub_sub.add_parser(
        "start",
        help="Starte das Hub Dashboard",
        description="Startet das lokale Web-Dashboard auf dem angegebenen Port.",
    )
    start_parser.add_argument(
        "--port", "-p", type=int, default=5000,
        help="Port (Standard: 5000)",
    )
    start_parser.set_defaults(func=cmd_hub)

    # hub status
    status_parser = hub_sub.add_parser(
        "status",
        help="Zeige ob das Dashboard läuft",
        description="Prüft ob der Hub Dashboard-Server aktiv ist.",
    )
    status_parser.add_argument(
        "--port", "-p", type=int, default=5000,
        help=argparse.SUPPRESS,
    )
    status_parser.set_defaults(func=cmd_hub)

    # hub stop
    stop_parser = hub_sub.add_parser(
        "stop",
        help="Stoppe das Hub Dashboard",
        description="Stoppt den laufenden Dashboard-Server.",
    )
    stop_parser.set_defaults(func=cmd_hub)

    hub_parser.set_defaults(func=cmd_hub)
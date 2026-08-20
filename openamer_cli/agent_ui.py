"""Visual Drag-Drop Agent Builder Web UI — Browser-based agent creation.

Starts a local web server that provides a drag-and-drop visual interface
for creating, editing, and managing agents. Uses the agent_builder module
as backend.

Usage:
    openamer agent ui              # Start web UI on default port
    openamer agent ui --port 8080  # Custom port
"""

from __future__ import annotations

import json
import logging
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from openamer_cli.agent_builder import (
    AgentSpec,
    build_agent,
    list_agents,
    delete_agent,
    show_agent,
    create_agent_from_description,
)

logger = logging.getLogger(__name__)

_AGENTS_FILE = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer")) / "agent-designs.json"

# ---------------------------------------------------------------------------
# HTML Template — all-in-one drag-drop visual builder
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenAmer Agent Builder</title>
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #c9d1d9; --text-dim: #8b949e;
    --accent: #22D3EE; --accent-dim: #155e6b;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --toolbar: #0d1117; --canvas-bg: #0d1117;
    --node-skill: #2ea043; --node-cron: #58a6ff;
    --node-tool: #d29922; --node-prompt: #bc8cff;
    --node-output: #f85149;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; }
  
  /* ── Layout ── */
  #app { display: flex; height: 100vh; }
  #sidebar { width: 280px; min-width: 280px; background: var(--card); border-right: 1px solid var(--border); display: flex; flex-direction: column; overflow-y: auto; }
  #canvas-area { flex: 1; display: flex; flex-direction: column; }
  #toolbar { background: var(--card); border-bottom: 1px solid var(--border); padding: 8px 16px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  #dropzone { flex: 1; position: relative; overflow: auto; background: var(--canvas-bg);
    background-image: radial-gradient(circle, var(--border) 1px, transparent 1px);
    background-size: 24px 24px;
  }
  
  /* ── Panels ── */
  .panel-title { padding: 12px 16px 8px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-dim); }
  .panel-section { border-bottom: 1px solid var(--border); padding-bottom: 8px; }
  
  /* ── Node palette ── */
  .palette-item { display: flex; align-items: center; gap: 10px; padding: 8px 16px; cursor: grab; transition: background 0.15s; user-select: none; }
  .palette-item:hover { background: rgba(34,211,238,0.08); }
  .palette-item:active { cursor: grabbing; }
  .palette-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .palette-label { font-size: 13px; }
  .palette-desc { font-size: 11px; color: var(--text-dim); }
  
  /* ── Template buttons ── */
  .template-btn { display: block; width: calc(100% - 32px); margin: 4px 16px; padding: 8px 12px; background: #21262d; border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 12px; text-align: left; cursor: pointer; transition: border-color 0.15s; }
  .template-btn:hover { border-color: var(--accent); }
  .template-btn .tpl-name { font-weight: 600; font-size: 13px; }
  .template-btn .tpl-desc { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
  
  /* ── Toolbar buttons ── */
  .tb-btn { padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px; background: #21262d; color: var(--text); font-size: 12px; cursor: pointer; transition: all 0.15s; }
  .tb-btn:hover { border-color: var(--accent); background: var(--accent-dim); }
  .tb-btn.primary { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
  .tb-btn.primary:hover { background: #1ab8d0; }
  .tb-btn.danger { border-color: var(--red); color: var(--red); }
  .tb-btn.danger:hover { background: var(--red); color: #fff; }
  .tb-spacer { flex: 1; }
  .tb-status { font-size: 11px; color: var(--text-dim); }
  
  /* ── Canvas nodes ── */
  .canvas-node { position: absolute; min-width: 160px; max-width: 240px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); cursor: move; user-select: none; z-index: 10; }
  .canvas-node:hover { box-shadow: 0 4px 16px rgba(34,211,238,0.15); }
  .canvas-node.selected { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent), 0 4px 16px rgba(34,211,238,0.2); }
  .node-header { padding: 8px 12px; border-radius: 7px 7px 0 0; font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: space-between; }
  .node-header .node-title { flex: 1; }
  .node-header .node-del { background: none; border: none; color: var(--text-dim); cursor: pointer; font-size: 14px; padding: 0 0 0 8px; }
  .node-header .node-del:hover { color: var(--red); }
  .node-body { padding: 8px 12px; font-size: 12px; }
  .node-body input, .node-body textarea, .node-body select { width: 100%; padding: 4px 8px; background: #0d1117; border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-size: 11px; margin-top: 4px; }
  .node-body textarea { min-height: 40px; resize: vertical; font-family: monospace; }
  .node-body label { display: block; font-size: 11px; color: var(--text-dim); margin-top: 6px; }
  
  .node-ports { display: flex; justify-content: space-between; padding: 4px 8px 6px; }
  .port { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--border); background: var(--card); cursor: crosshair; position: relative; transition: transform 0.15s; }
  .port:hover { transform: scale(1.3); }
  .port.input { border-color: var(--accent); }
  .port.output { border-color: var(--green); }
  .port-label { font-size: 9px; color: var(--text-dim); text-align: center; margin-top: 1px; }
  
  /* Color per node type */
  .node-skill .node-header { background: var(--node-skill); color: #000; }
  .node-cron .node-header { background: var(--node-cron); color: #000; }
  .node-tool .node-header { background: var(--node-tool); color: #000; }
  .node-prompt .node-header { background: var(--node-prompt); color: #000; }
  .node-output .node-header { background: var(--node-output); color: #fff; }
  
  /* ── SVG connections layer ── */
  #connections { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 5; }
  #connections path { fill: none; stroke: var(--accent); stroke-width: 2; pointer-events: stroke; cursor: pointer; }
  #connections path:hover { stroke: var(--yellow); stroke-width: 3; }
  #connections path.dragging { stroke: var(--yellow); stroke-dasharray: 5,3; }
  
  /* ── Modals ── */
  .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 1000; }
  .modal { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 24px; min-width: 400px; max-width: 600px; max-height: 80vh; overflow-y: auto; }
  .modal h2 { margin-bottom: 16px; color: var(--accent); }
  .modal label { display: block; margin: 12px 0 4px; font-size: 12px; color: var(--text-dim); }
  .modal input, .modal textarea, .modal select { width: 100%; padding: 8px 12px; background: #0d1117; border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; }
  .modal textarea { min-height: 60px; }
  .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
  
  /* ── Scrolling helpers ── */  
  .scroll-y { overflow-y: auto; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  
  .toast { position: fixed; bottom: 20px; right: 20px; padding: 10px 20px; border-radius: 8px; font-size: 13px; z-index: 2000; animation: fadein 0.3s; }
  .toast.success { background: #0d5320; color: var(--green); border: 1px solid var(--green); }
  .toast.error { background: #3d1111; color: var(--red); border: 1px solid var(--red); }
  @keyframes fadein { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
</head>
<body>
<div id="app">
  <!-- Sidebar -->
  <div id="sidebar">
    <div style="padding:16px;border-bottom:1px solid var(--border)">
      <h1 style="font-size:16px;color:var(--accent);margin:0">🧩 Agent Builder</h1>
      <div style="font-size:11px;color:var(--text-dim);margin-top:4px">Drag nodes onto canvas</div>
    </div>

    <div class="panel-section">
      <div class="panel-title">📦 Node Palette</div>
      <div class="palette-item" data-type="skill" draggable="true">
        <div class="palette-dot" style="background:var(--node-skill)"></div>
        <div><div class="palette-label">Skill Node</div><div class="palette-desc">Load a skill module</div></div>
      </div>
      <div class="palette-item" data-type="cron" draggable="true">
        <div class="palette-dot" style="background:var(--node-cron)"></div>
        <div><div class="palette-label">Cron Node</div><div class="palette-desc">Schedule trigger</div></div>
      </div>
      <div class="palette-item" data-type="tool" draggable="true">
        <div class="palette-dot" style="background:var(--node-tool)"></div>
        <div><div class="palette-label">Tool Node</div><div class="palette-desc">Enable a tool</div></div>
      </div>
      <div class="palette-item" data-type="prompt" draggable="true">
        <div class="palette-dot" style="background:var(--node-prompt)"></div>
        <div><div class="palette-label">Prompt Node</div><div class="palette-desc">Custom instruction</div></div>
      </div>
      <div class="palette-item" data-type="output" draggable="true">
        <div class="palette-dot" style="background:var(--node-output)"></div>
        <div><div class="palette-label">Output Node</div><div class="palette-desc">Result / action</div></div>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-title">📋 Templates</div>
      <button class="template-btn" onclick="loadTemplate('research')">
        <div class="tpl-name">🔬 Research &amp; Summarize</div>
        <div class="tpl-desc">Web research → Summarize → Report output</div>
      </button>
      <button class="template-btn" onclick="loadTemplate('code-reviewer')">
        <div class="tpl-name">✅ Code Reviewer</div>
        <div class="tpl-desc">Analyze code → Review → Post results</div>
      </button>
      <button class="template-btn" onclick="loadTemplate('daily-report')">
        <div class="tpl-name">📊 Daily Report</div>
        <div class="tpl-desc">Cron trigger → Collect data → Format report</div>
      </button>
      <button class="template-btn" onclick="loadTemplate('social-poster')">
        <div class="tpl-name">📱 Social Media Poster</div>
        <div class="tpl-desc">Cron trigger → Generate post → Publish</div>
      </button>
    </div>

    <div style="padding:12px 16px;margin-top:auto">
      <button class="tb-btn" style="width:100%;margin-bottom:6px" onclick="showSaveModal()">💾 Save Design</button>
      <button class="tb-btn" style="width:100%;margin-bottom:6px" onclick="document.getElementById('loadFile').click()">📂 Load Design</button>
      <input type="file" id="loadFile" accept=".json" style="display:none" onchange="loadDesign(event)">
      <button class="tb-btn danger" style="width:100%" onclick="clearCanvas()">🗑️ Clear All</button>
    </div>
  </div>

  <!-- Canvas Area -->
  <div id="canvas-area">
    <div id="toolbar">
      <span style="font-weight:600;font-size:13px">Canvas</span>
      <span class="tb-status" id="nodeCount">0 nodes</span>
      <span class="tb-status" id="connCount">0 connections</span>
      <div class="tb-spacer"></div>
      <button class="tb-btn" onclick="zoomIn()">🔍+</button>
      <button class="tb-btn" onclick="zoomOut()">🔍−</button>
      <button class="tb-btn" onclick="resetView()">⊞ Fit</button>
      <button class="tb-btn primary" onclick="buildFromCanvas()">🚀 Build Agent</button>
    </div>
    <div id="dropzone">
      <svg id="connections"></svg>
    </div>
  </div>
</div>

<!-- Save Modal -->
<div id="saveModal" class="modal-overlay" style="display:none">
  <div class="modal">
    <h2>💾 Save Agent Design</h2>
    <label>Agent Name</label>
    <input id="saveName" placeholder="my-agent">
    <label>Description (optional)</label>
    <textarea id="saveDesc" placeholder="What does this agent do?"></textarea>
    <label>Goal (optional)</label>
    <textarea id="saveGoal" placeholder="Primary goal for the agent"></textarea>
    <div class="modal-actions">
      <button class="tb-btn" onclick="closeSaveModal()">Cancel</button>
      <button class="tb-btn primary" onclick="saveDesign()">Save</button>
    </div>
  </div>
</div>

<script>
// ── State ──
let nodes = [];
let connections = [];
let nextNodeId = 1;
let selectedNodeId = null;
let dragNodeId = null;
let dragOffset = { x: 0, y: 0 };
let connectFrom = null;  // { nodeId, portType }
let zoom = 1;
let pan = { x: 0, y: 0 };

const NODE_TYPES = {
  skill:  { label: 'Skill Node',    color: '#2ea043', config: { skillName: '' } },
  cron:   { label: 'Cron Node',     color: '#58a6ff', config: { schedule: '0 9 * * *' } },
  tool:   { label: 'Tool Node',     color: '#d29922', config: { toolName: '' } },
  prompt: { label: 'Prompt Node',   color: '#bc8cff', config: { text: '' } },
  output: { label: 'Output Node',   color: '#f85149', config: { action: 'report' } },
};

const TEMPLATES = {
  'research': {
    name: 'Research & Summarize',
    nodes: [
      { id: 1, type: 'tool',   x: 40, y: 40,  config: { toolName: 'web-search' } },
      { id: 2, type: 'tool',   x: 40, y: 160, config: { toolName: 'web-extract' } },
      { id: 3, type: 'prompt', x: 300, y: 80, config: { text: 'Summarize the research findings in 3 bullet points.' } },
      { id: 4, type: 'output', x: 560, y: 80, config: { action: 'report' } },
    ],
    connections: [
      { from: 1, to: 3 }, { from: 2, to: 3 }, { from: 3, to: 4 }
    ]
  },
  'code-reviewer': {
    name: 'Code Reviewer',
    nodes: [
      { id: 1, type: 'skill',  x: 40, y: 40,  config: { skillName: 'code-review' } },
      { id: 2, type: 'prompt', x: 300, y: 60, config: { text: 'Review the code changes for security issues, bugs, and style.' } },
      { id: 3, type: 'output', x: 560, y: 40, config: { action: 'report' } },
      { id: 4, type: 'tool',   x: 300, y: 200, config: { toolName: 'github' } },
    ],
    connections: [
      { from: 1, to: 2 }, { from: 2, to: 3 }, { from: 4, to: 2 }
    ]
  },
  'daily-report': {
    name: 'Daily Report',
    nodes: [
      { id: 1, type: 'cron',   x: 40, y: 40,  config: { schedule: '0 9 * * *' } },
      { id: 2, type: 'skill',  x: 260, y: 40, config: { skillName: 'web-research' } },
      { id: 3, type: 'prompt', x: 480, y: 40, config: { text: 'Create a concise daily report with key updates and metrics.' } },
      { id: 4, type: 'output', x: 680, y: 40, config: { action: 'report' } },
    ],
    connections: [
      { from: 1, to: 2 }, { from: 2, to: 3 }, { from: 3, to: 4 }
    ]
  },
  'social-poster': {
    name: 'Social Media Poster',
    nodes: [
      { id: 1, type: 'cron',   x: 40, y: 40,  config: { schedule: '0 8,12,18 * * *' } },
      { id: 2, type: 'prompt', x: 280, y: 40, config: { text: 'Write an engaging social media post about today\'s topic.' } },
      { id: 3, type: 'tool',   x: 520, y: 40, config: { toolName: 'twitter' } },
      { id: 4, type: 'output', x: 520, y: 160, config: { action: 'publish' } },
    ],
    connections: [
      { from: 1, to: 2 }, { from: 2, to: 3 }, { from: 3, to: 4 }
    ]
  }
};

// ── Toast ──
function toast(msg, type) {
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── Rendering ──
function render() {
  const dz = document.getElementById('dropzone');
  // Remove old nodes
  dz.querySelectorAll('.canvas-node').forEach(n => n.remove());
  // Remove old svg paths (keep the svg element)
  const svg = document.getElementById('connections');
  svg.innerHTML = '';

  // Sort nodes so selected is on top
  const sorted = [...nodes];
  const selIdx = sorted.findIndex(n => n.id === selectedNodeId);
  if (selIdx >= 0) { const s = sorted.splice(selIdx, 1)[0]; sorted.push(s); }

  sorted.forEach(n => {
    const div = document.createElement('div');
    const typeInfo = NODE_TYPES[n.type] || NODE_TYPES.skill;
    div.className = `canvas-node node-${n.type}`;
    if (n.id === selectedNodeId) div.classList.add('selected');
    div.style.left = (n.x * zoom + pan.x) + 'px';
    div.style.top = (n.y * zoom + pan.y) + 'px';
    div.style.transform = `scale(${zoom})`;
    div.style.transformOrigin = 'top left';
    div.dataset.nodeId = n.id;

    const cfg = n.config || {};
    let bodyHTML = '';
    if (n.type === 'skill') {
      bodyHTML = `<label>Skill Name</label><input value="${cfg.skillName || ''}" onchange="updateNodeConfig(${n.id},'skillName',this.value)" placeholder="e.g. web-research">`;
    } else if (n.type === 'cron') {
      bodyHTML = `<label>Schedule (cron)</label><input value="${cfg.schedule || '0 9 * * *'}" onchange="updateNodeConfig(${n.id},'schedule',this.value)" placeholder="0 9 * * *">`;
    } else if (n.type === 'tool') {
      bodyHTML = `<label>Tool Name</label><input value="${cfg.toolName || ''}" onchange="updateNodeConfig(${n.id},'toolName',this.value)" placeholder="e.g. web-search">`;
    } else if (n.type === 'prompt') {
      bodyHTML = `<label>Instruction</label><textarea onchange="updateNodeConfig(${n.id},'text',this.value)" placeholder="Enter prompt...">${cfg.text || ''}</textarea>`;
    } else if (n.type === 'output') {
      bodyHTML = `<label>Action</label><select onchange="updateNodeConfig(${n.id},'action',this.value)">
        <option value="report" ${cfg.action === 'report' ? 'selected':''}>Report</option>
        <option value="publish" ${cfg.action === 'publish' ? 'selected':''}>Publish</option>
        <option value="save" ${cfg.action === 'save' ? 'selected':''}>Save</option>
        <option value="notify" ${cfg.action === 'notify' ? 'selected':''}>Notify</option>
      </select>`;
    }

    div.innerHTML = `
      <div class="node-header" onmousedown="startDrag(${n.id}, event)">
        <span class="node-title">${typeInfo.label}</span>
        <button class="node-del" onclick="deleteNode(${n.id})">✕</button>
      </div>
      <div class="node-body">${bodyHTML}</div>
      <div class="node-ports">
        <div><div class="port input" data-port="${n.id}-input" onmousedown="startConnect(${n.id},'input',event)"></div><div class="port-label">In</div></div>
        <div><div class="port output" data-port="${n.id}-output" onmousedown="startConnect(${n.id},'output',event)"></div><div class="port-label">Out</div></div>
      </div>`;

    div.addEventListener('click', () => selectNode(n.id));
    dz.appendChild(div);
  });

  // Render connections
  connections.forEach((conn, idx) => {
    const fromNode = nodes.find(n => n.id === conn.from);
    const toNode = nodes.find(n => n.id === conn.to);
    if (!fromNode || !toNode) return;
    const fromEl = dz.querySelector(`[data-port="${conn.from}-output"]`);
    const toEl = dz.querySelector(`[data-port="${conn.to}-input"]`);
    if (!fromEl || !toEl) return;
    const dzRect = dz.getBoundingClientRect();
    const fRect = fromEl.getBoundingClientRect();
    const tRect = toEl.getBoundingClientRect();
    const x1 = fRect.left - dzRect.left + fRect.width / 2;
    const y1 = fRect.top - dzRect.top + fRect.height / 2;
    const x2 = tRect.left - dzRect.left + tRect.width / 2;
    const y2 = tRect.top - dzRect.top + tRect.height / 2;
    const cx1 = x1 + (x2 - x1) * 0.4;
    const cy1 = y1;
    const cx2 = x2 - (x2 - x1) * 0.4;
    const cy2 = y2;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${x1},${y1} C${cx1},${cy1} ${cx2},${cy2} ${x2},${y2}`);
    path.dataset.connIdx = idx;
    path.addEventListener('dblclick', () => { connections.splice(idx, 1); render(); });
    svg.appendChild(path);
  });

  document.getElementById('nodeCount').textContent = nodes.length + ' nodes';
  document.getElementById('connCount').textContent = connections.length + ' connections';
}

// ── Node management ──
function addNode(type, x, y) {
  const node = { id: nextNodeId++, type, x, y, config: { ...NODE_TYPES[type].config } };
  nodes.push(node);
  render();
  return node;
}

function deleteNode(id) {
  nodes = nodes.filter(n => n.id !== id);
  connections = connections.filter(c => c.from !== id && c.to !== id);
  if (selectedNodeId === id) selectedNodeId = null;
  render();
}

function selectNode(id) {
  selectedNodeId = id;
  render();
}

function updateNodeConfig(id, key, value) {
  const node = nodes.find(n => n.id === id);
  if (node) node.config[key] = value;
}

// ── Drag from palette ──
document.querySelectorAll('.palette-item[draggable]').forEach(el => {
  el.addEventListener('dragstart', e => {
    e.dataTransfer.setData('text/plain', el.dataset.type);
    e.dataTransfer.effectAllowed = 'copy';
  });
});

document.getElementById('dropzone').addEventListener('dragover', e => {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
});

document.getElementById('dropzone').addEventListener('drop', e => {
  e.preventDefault();
  const type = e.dataTransfer.getData('text/plain');
  if (!type || !NODE_TYPES[type]) return;
  const rect = document.getElementById('dropzone').getBoundingClientRect();
  const x = (e.clientX - rect.left - pan.x) / zoom;
  const y = (e.clientY - rect.top - pan.y) / zoom;
  addNode(type, Math.max(0, x - 80), Math.max(0, y - 20));
});

// ── Move nodes on canvas ──
function startDrag(id, e) {
  if (e.button !== 0) return;
  dragNodeId = id;
  const node = nodes.find(n => n.id === id);
  if (!node) return;
  const rect = document.getElementById('dropzone').getBoundingClientRect();
  dragOffset.x = (e.clientX - rect.left - pan.x) / zoom - node.x;
  dragOffset.y = (e.clientY - rect.top - pan.y) / zoom - node.y;
  e.stopPropagation();
}

document.addEventListener('mousemove', e => {
  if (dragNodeId === null) return;
  const node = nodes.find(n => n.id === dragNodeId);
  if (!node) return;
  const rect = document.getElementById('dropzone').getBoundingClientRect();
  node.x = Math.max(0, (e.clientX - rect.left - pan.x) / zoom - dragOffset.x);
  node.y = Math.max(0, (e.clientY - rect.top - pan.y) / zoom - dragOffset.y);
  render();
  // Update dragging connection if active
  if (connectFrom) renderDragConnection(e);
});

document.addEventListener('mouseup', () => {
  dragNodeId = null;
});

// ── Connection drawing ──
function startConnect(nodeId, portType, e) {
  e.stopPropagation();
  if (portType === 'output') {
    connectFrom = { nodeId, portType };
  } else if (portType === 'input' && connectFrom) {
    const fromId = connectFrom.nodeId;
    if (fromId !== nodeId && !connections.find(c => c.from === fromId && c.to === nodeId)) {
      connections.push({ from: fromId, to: nodeId });
    }
    connectFrom = null;
    render();
  } else {
    connectFrom = null;
  }
}

function renderDragConnection(e) {
  if (!connectFrom) return;
  const svg = document.getElementById('connections');
  // Remove temporary drag path
  svg.querySelectorAll('path.dragging').forEach(p => p.remove());
  const fromNode = nodes.find(n => n.id === connectFrom.nodeId);
  if (!fromNode) return;
  const dz = document.getElementById('dropzone');
  const portEl = dz.querySelector(`[data-port="${connectFrom.nodeId}-output"]`);
  if (!portEl) return;
  const dzRect = dz.getBoundingClientRect();
  const fRect = portEl.getBoundingClientRect();
  const x1 = fRect.left - dzRect.left + fRect.width / 2;
  const y1 = fRect.top - dzRect.top + fRect.height / 2;
  const x2 = e.clientX - dzRect.left;
  const y2 = e.clientY - dzRect.top;
  const cx1 = x1 + (x2 - x1) * 0.4;
  const cy1 = y1;
  const cx2 = x2 - (x2 - x1) * 0.4;
  const cy2 = y2;
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', `M${x1},${y1} C${cx1},${cy1} ${cx2},${cy2} ${x2},${y2}`);
  path.classList.add('dragging');
  svg.appendChild(path);
}

// Cancel connection on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { connectFrom = null; render(); }
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedNodeId) { deleteNode(selectedNodeId); }
  }
});

// ── Zoom & Pan ──
function zoomIn() { zoom = Math.min(2, zoom * 1.2); render(); }
function zoomOut() { zoom = Math.max(0.3, zoom / 1.2); render(); }
function resetView() { zoom = 1; pan = { x: 0, y: 0 }; render(); }

// Canvas pan via middle-click or ctrl+drag
let panning = false, panStart = { x: 0, y: 0 };
document.getElementById('dropzone').addEventListener('mousedown', e => {
  if (e.button === 1 || (e.ctrlKey && e.button === 0)) {
    panning = true;
    panStart = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    e.preventDefault();
  }
});
document.addEventListener('mousemove', e => {
  if (panning) {
    pan.x = e.clientX - panStart.x;
    pan.y = e.clientY - panStart.y;
    render();
  }
});
document.addEventListener('mouseup', () => { panning = false; });

// ── Templates ──
function loadTemplate(name) {
  const tpl = TEMPLATES[name];
  if (!tpl) return;
  nodes = [];
  connections = [];
  nextNodeId = 1;
  // Re-index template node IDs
  const idMap = {};
  tpl.nodes.forEach(n => {
    const newId = nextNodeId++;
    idMap[n.id] = newId;
    nodes.push({ id: newId, type: n.type, x: n.x, y: n.y, config: { ...NODE_TYPES[n.type].config, ...n.config } });
  });
  tpl.connections.forEach(c => {
    connections.push({ from: idMap[c.from], to: idMap[c.to] });
  });
  selectedNodeId = null;
  toast('Loaded template: ' + tpl.name, 'success');
  render();
}

// ── Save/Load ──
function showSaveModal() {
  document.getElementById('saveModal').style.display = 'flex';
}

function closeSaveModal() {
  document.getElementById('saveModal').style.display = 'none';
}

function saveDesign() {
  const name = document.getElementById('saveName').value.trim() || 'untitled';
  const desc = document.getElementById('saveDesc').value.trim();
  const goal = document.getElementById('saveGoal').value.trim();
  const design = { name, description: desc, goal, nodes, connections, version: 1 };
  const blob = new Blob([JSON.stringify(design, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name.replace(/[^a-z0-9_-]/gi, '_') + '.agent.json';
  a.click();
  closeSaveModal();
  toast('Design saved!', 'success');
}

function loadDesign(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const design = JSON.parse(e.target.result);
      if (design.nodes && Array.isArray(design.nodes)) {
        nodes = design.nodes;
        connections = design.connections || [];
        nextNodeId = (nodes.reduce((m, n) => Math.max(m, n.id), 0) || 0) + 1;
        selectedNodeId = null;
        toast('Design loaded: ' + (design.name || file.name), 'success');
        render();
      } else {
        toast('Invalid design file', 'error');
      }
    } catch (err) {
      toast('Error loading design: ' + err.message, 'error');
    }
  };
  reader.readAsText(file);
  event.target.value = '';
}

function clearCanvas() {
  if (nodes.length === 0) return;
  if (!confirm('Clear all nodes and connections?')) return;
  nodes = [];
  connections = [];
  nextNodeId = 1;
  selectedNodeId = null;
  render();
  toast('Canvas cleared', 'success');
}

// ── Build agent from canvas ──
function buildFromCanvas() {
  const name = prompt('Agent name:', 'my-agent');
  if (!name) return;

  const skills = [];
  const tools = [];
  let description = '';
  let goal = '';
  let cron_schedule = null;

  nodes.forEach(n => {
    if (n.type === 'skill' && n.config.skillName) skills.push(n.config.skillName);
    if (n.type === 'tool' && n.config.toolName) tools.push(n.config.toolName);
    if (n.type === 'cron' && n.config.schedule) cron_schedule = n.config.schedule;
    if (n.type === 'prompt' && n.config.text) {
      description += (description ? ' | ' : '') + n.config.text;
      goal += (goal ? ' ' : '') + n.config.text;
    }
    if (n.type === 'output' && n.config.action) {
      goal += (goal ? ' ' : '') + 'Action: ' + n.config.action;
    }
  });

  if (!description) description = 'Agent built from visual canvas';
  if (!goal) goal = description;

  fetch('/api/agent/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description, goal, cron_schedule, skills, tools })
  })
  .then(r => r.json())
  .then(d => {
    if (d.ok || d.name) {
      toast('Agent built: ' + d.name, 'success');
    } else {
      toast(d.error || 'Build failed', 'error');
    }
  })
  .catch(e => toast('Error: ' + e.message, 'error'));
}

// ── Init ──
render();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------


class _AgentUIHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Agent Builder UI."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(200, _HTML)
        elif self.path == "/api/agents":
            self._send_json(200, {"agents": list_agents()})
        elif self.path.startswith("/api/agent/show/"):
            name = self.path.split("/")[-1]
            agent = show_agent(name)
            if agent:
                self._send_json(200, agent)
            else:
                self._send_json(404, {"error": f"Agent '{name}' not found"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        data = json.loads(body) if body else {}

        if self.path == "/api/agent/build":
            spec = AgentSpec(
                name=data.get("name", ""),
                description=data.get("description", ""),
                goal=data.get("goal", ""),
                cron_schedule=data.get("cron_schedule"),
                skills=data.get("skills", []),
                tools=data.get("tools", []),
            )
            result = build_agent(spec)
            self._send_json(200 if result.get("ok", True) else 400, result)

        elif self.path == "/api/agent/create-from-nl":
            desc = data.get("description", "")
            if not desc:
                self._send_json(400, {"ok": False, "error": "No description provided"})
                return
            spec = create_agent_from_description(desc)
            result = build_agent(spec)
            self._send_json(200 if result.get("ok", True) else 400, result)

        elif self.path == "/api/agent/delete":
            name = data.get("name", "")
            if not name:
                self._send_json(400, {"ok": False, "error": "No name provided"})
                return
            ok = delete_agent(name)
            self._send_json(200, {"ok": ok, "name": name})

        else:
            self._send_json(404, {"error": "Not found"})

    def _send_html(self, code: int, html: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cmd_agent_ui(args) -> None:
    """Start the Agent Builder web UI."""
    port = getattr(args, "port", 8080)
    server = HTTPServer(("127.0.0.1", port), _AgentUIHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"OpenAmer Agent Builder UI running at: {url}")
    print("Press Ctrl+C to stop.")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


def build_agent_ui_parser(subparsers) -> None:
    """Add the ``openamer agent-ui`` subcommand."""
    parser = subparsers.add_parser(
        "agent-ui",
        help="Start the Agent Builder web UI",
        description="Start a local web server with a visual drag-drop agent builder interface.",
    )
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.set_defaults(func=cmd_agent_ui)
---
name: vscode-extension-scaffold
description: "Scaffold VS Code extensions: webview, MCP, commands, menus."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [vscode, extension, scaffolding, typescript, mcp, webview]
    related_skills: [greenfield-agent-project, plan]
---

# Scaffolding a VS Code Extension

When the user asks to build a VS Code extension (not a core tool, but a plugin/separate repo under a larger project), produce a complete source-only scaffold. The extension should be minimal, functional, and follow standard VS Code Extension API patterns.

## When to Use

- User asks for a "VS Code extension" as a sidecar plugin
- User says "create a VS Code extension for X" in any domain (MCP client, chat panel, code analysis, etc.)

## Standard File Layout

```
apps/vscode/
  package.json   — contributed APIs (commands, menus, views, statusBar)
  tsconfig.json  — strict TS with Node16/esModuleInterop
  src/
    extension.ts — activate/deactivate, command handlers, webview, MCP client
  README.md      — usage, commands, development, license
```

## 1. `package.json` — Contribution Anatomy

VS Code extensions declare their UI surface in `contributes`. The key sections:

### Commands
Register all commands here. Each gets a unique `command` id and a `title`.

```json
"contributes": {
  "commands": [
    { "command": "openamer.chat", "title": "OpenAmer: Chat" },
    { "command": "openamer.explain", "title": "Ask OpenAmer to explain this" },
    { "command": "openamer.fix", "title": "Ask OpenAmer to fix this" }
  ],
```

### Menus
Wire commands into context menus. Use `when` clauses for conditional visibility.

- `editor/context`: right-click in editor. Use `editorHasSelection` for selection-dependent commands.
- `explorer/context`: right-click on file in explorer tree. Use `group` for ordering (`openamer@1`).

```json
"menus": {
  "editor/context": [
    { "command": "openamer.fix", "when": "editorHasSelection", "group": "openamer@2" }
  ],
  "explorer/context": [
    { "command": "openamer.explain", "group": "openamer@1" }
  ]
}
```

### Views & View Containers
Activity bar sidebar with a webview panel:

```json
"viewsContainers": {
  "activitybar": [
    { "id": "openamer", "title": "OpenAmer Agent", "icon": "$(comment-discussion)" }
  ]
},
"views": {
  "openamer": [
    { "type": "webview", "id": "openamerChat", "name": "Chat" }
  ]
}
```

### Status Bar
A named status bar item (VS Code 1.90+):

```json
"statusBar": [
  { "id": "openamer.status", "name": "OpenAmer Connection Status", "alignment": "right", "priority": 100 }
]
```

### Activation Events
List `onCommand:` for every command and `onView:` for every view so the extension loads lazily.

## 2. `tsconfig.json` — Strict TypeScript

Use `Node16` module, `ES2022` target. Enable `strict`, `esModuleInterop`, `skipLibCheck`, `sourceMap`, `declaration`. Point `outDir` to `out/` and `rootDir` to `src/`.

```json
{
  "compilerOptions": {
    "module": "Node16",
    "target": "ES2022",
    "lib": ["ES2022"],
    "outDir": "out",
    "rootDir": "src",
    "sourceMap": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "out", ".vscode-test"]
}
```

DevDependencies: `@types/node`, `@types/vscode`, `typescript`. Do NOT add runtime deps for a minimal scaffold — the MCP client and webview are stdlib only.

## 3. `src/extension.ts` — Patterns

### Structure
Always export `activate` and `deactivate`. Gate everything behind `context.subscriptions.push(...)`.

### MCP Client (stdio JSON-RPC)
Build a lightweight MCP client from scratch using `child_process.spawn`. No library needed.

Key methods:
- `connect(command, args)` — spawns the process, sends `initialize` request
- `request(method, params)` — sends a JSON-RPC request with a unique id, returns a promise
- `chat(message, onToken)` — calls `tools/call` with `openamer_chat`, streams text back
- `listTools()` — calls `tools/list`, returns available tools
- `disconnect()` — kills the child process

Buffer incoming lines from stdout, parse each complete JSON line, match against pending request ids.

The connect method should also handle protocol handshake: send `initialize` with `protocolVersion: '2024-11-05'`, then `notifications/initialized`.

### Chat Webview Provider
Implement `vscode.WebviewViewProvider`:
- `resolveWebviewView()` sets `webview.options.enableScripts = true` and provides HTML
- Receive chat messages from the webview via `onDidReceiveMessage`
- Post messages back (addMessage, updateLastAssistant) via `webview.postMessage`
- The HTML is a complete inline page with CSP nonce, basic chat styling, and JS bridge to `acquireVsCodeApi()`

### Status Bar
```ts
const item = vscode.window.createStatusBarItem('openamer.status', vscode.StatusBarAlignment.Right, 100);
item.text = '$(debug-disconnect) OpenAmer: disconnected';
item.show();
context.subscriptions.push(item);
```
Update with different icon strings: `$(check)` for connected, `$(sync~spin)` for connecting, `$(debug-disconnect)` for disconnected.

### Commands
- **openamer.chat**: `vscode.commands.executeCommand('workbench.view.extension.openamer')` to focus the sidebar
- **openamer.explain**: Read the active editor or provided URI, get text, send to MCP chat, show result
- **openamer.fix**: Get selected text, send to MCP chat, show result

### Auto-connect
Try to spawn `openamer mcp` on activation with retries. Resolve the binary via PATH (and `process.env.OPENAMER_PATH`). On failure, show a warning and set status bar to disconnected.

## 4. `README.md`

Sections: Features, Requirements, Usage, Commands, Development (`npm install && npm run compile`), license.

## Verification

After creating files, verify:
1. `node -e "JSON.parse(...)"` on package.json and tsconfig.json for syntax
2. Structural validation: grep for `registerCommand`, `registerWebviewViewProvider`, `createStatusBarItem`, `editor/context` menus, `viewsContainers`
3. **Compute** `tsc --noEmit` passes with zero errors — install deps via `npm install` (or rely on workspace hoisting in a monorepo) and compile

## Pitfalls

- **npm workspace hoisting**: If the extension lives under a repo that has workspaces defined in its root package.json, running `npm install` inside the extension dir will hoist all deps to the root node_modules/. The local node_modules/ will be incomplete. Two options:
  - **Option A**: Use `npx --no-install tsc` or compile from the root level with `npx -w apps/vscode tsc`. The local package-lock.json won't be generated; the root workspace lock covers it.
  - **Option B**: Run `npm install --no-workspaces` inside the extension dir to force local install. Cleaner for pure-scaffold extensions (devDeps only) — `npx tsc` works directly without `--no-install`. See `references/session-details.md` for the full trade-off analysis.
- **`npx tsc` with `--noEmit` is the safest compile check**: It checks types without emitting files, so it works even when the output dir doesn't exist yet.
- **Webview CSP**: Must include a `nonce` for inline scripts and set `style-src` to `cspSource` with `'unsafe-inline'` for VS Code's theme variables to work. Default-src must be `'none'` for security.
- **`@types/vscode` must match the `engines.vscode` version**: If `engines.vscode` is `^1.90.0`, install `@types/vscode@1.90.x` or later. Compilation errors like `Cannot find module 'vscode'` usually mean the types are missing or version-mismatched.
- **ActivationEvents must match**: Every `onCommand:openamer.xxx` and `onView:openamerChat` in `activationEvents` must correspond to a registered command or view, or the extension may not activate.
- **`editor/context` vs `explorer/context`**: `editor/context` triggers when right-clicking *in the editor*, `explorer/context` when right-clicking a *file in the file tree*. Their `when` clauses use different context keys (e.g. `editorHasDocumentation` may not fire for explorer — use broader conditions or none, or the menu entry silently won't appear).

## JetBrains IntelliJ Companion

A JetBrains IDE extension scaffold (Kotlin) exists as a companion — see `references/jetbrains-extension-scaffold.md` under this skill. The JetBrains version mirrors the VS Code pattern:

| VS Code (this skill) | JetBrains (companion ref) |
|---|---|
| `package.json contributes` | `plugin.xml <extensions>` / `<actions>` |
| `registerCommand()` | `AnAction` subclass |
| `child_process.spawn` | `java.lang.ProcessBuilder` |
| `vscode.WebviewViewProvider` | `JCEFHtmlPanel` |
| `npm install && tsc` | IntelliJ Gradle Plugin |

When the user asks for a JetBrains extension, load this skill first for general IDE extension patterns, then consult the companion for JetBrains-specific details.
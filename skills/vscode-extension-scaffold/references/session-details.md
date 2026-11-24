# VS Code Extension Reference — Session Artifacts

## MCP Client: Wire Protocol

The MCP client communicates over stdio using JSON-RPC 2.0, one JSON object per line terminated by `\n`.

### Init handshake

```
→ {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"clientInfo":{"name":"openamer-vscode","version":"0.1.0"}}}
← {"jsonrpc":"2.0","id":1,"result":{...}}
→ {"jsonrpc":"2.0","method":"notifications/initialized"}
```

### Request/Response

```
→ {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"openamer_chat","arguments":{"message":"explain this code"}}}
← {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"..."}]}}
```

### Key implementation details

- Buffer stdout data into a string, split on `\n`, parse each line as JSON
- Use `Map<number, {resolve, reject}>` for pending requests with a 30s timeout
- `stderr` output is logged to `console.error` but not parsed as protocol messages
- `onClose` callback fires when the child process exits — rejects all pending promises

## Workspace Hoisting Resolution

In the `openamer/openamer` monorepo, the root `package.json` defines workspaces:

```json
"workspaces": ["apps/*", "ui-tui", ...]
```

This means `npm install` inside `apps/vscode/` hoists all dependencies to `../../node_modules/` (the root). The local `node_modules/` will be empty or have symlinks. `package-lock.json` is written to the root, not the extension directory.

### Approach A: Compile via workspace root (no local install)

```bash
# From the extension dir:
npx --no-install tsc --noEmit    # type-check only, no emit
npx --no-install tsc              # full compile

# Or from the repo root (if the workspace name matches the dir):
npx -w apps/vscode tsc
```

### Approach B: `npm install --no-workspaces` (local install, cleaner)

This forces npm to install deps *inside* the extension directory, ignoring the parent workspace. The local `node_modules/` gets real copies, `npx tsc` works without `--no-install`, and `package-lock.json` is generated locally.

```bash
cd apps/vscode
npm install --no-workspaces
npx tsc --noEmit    # works directly
npx tsc             # full compile
```

Works best when the extension has only devDependencies (`@types/node`, `@types/vscode`, `typescript`) — install is fast (< 2s) and produces a clean, self-contained dev environment. Also avoids the ambiguity of workspace-hoisted types when the root uses a different TypeScript version.

**Trade-off**: If the extension later needs runtime deps installed at the workspace level, mixing `--no-workspaces` with workspace-installed packages can cause duplicates. For pure-scaffold extensions (stdlib MCP client + webview) this is never an issue.

## Extension.ts Anatomy (from the scaffold)

See the generated `src/extension.ts` for a complete working example. Key patterns:

1. **`MCPClient` class**: ~120 lines, self-contained, no external deps
2. **`ChatWebviewProvider` class**: implements `WebviewViewProvider`, ~100 lines 
3. **`activate()`**: registers all 3 commands, status bar, webview, auto-connects MCP
4. **`deactivate()`**: disconnects MCP client

The webview HTML includes:
- CSP meta tag with nonce-based script security
- `acquireVsCodeApi()` for VS Code message bridge
- `onDidReceiveMessage` for chat input → MCP communication
- `postMessage` for assistant responses → webview rendering
- Dark-theme-aware CSS using `var(--vscode-*)` variables

## Tool/Resource Fallback

The `chat()` method has a fallback: if `tools/call` fails, it tries `prompts/get` as a fallback method. This handles MCP servers that don't expose `openamer_chat` as a tool.

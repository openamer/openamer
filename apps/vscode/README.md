# OpenAmer Agent — VS Code Extension

AI-powered code assistance via the [OpenAmer Agent](https://github.com/openamer/openamer).

## Features

- **Chat sidebar** — talk to OpenAmer directly from the VS Code sidebar
- **Explain code** — right-click a file → "Ask OpenAmer to explain this"
- **Fix code** — select code → right-click → "Ask OpenAmer to fix this"
- **Status bar** — shows connection status at a glance

## Requirements

- [OpenAmer CLI](https://github.com/openamer/openamer) installed on `PATH` (or set `OPENAMER_PATH` env var)
- VS Code 1.90+

## Usage

1. Install the extension from VSIX or the Marketplace
2. The extension auto-connects to `openamer mcp` on startup
3. Click the 📝 OpenAmer Agent icon in the activity bar (left sidebar) to open the chat panel
4. Or use commands:
   - `Ctrl+Shift+P` → `OpenAmer: Chat`
   - Right-click a file → `Ask OpenAmer to explain this`
   - Select code → right-click → `Ask OpenAmer to fix this`

## Commands

| Command | ID | Keybinding |
|---|---|---|
| OpenAmer: Chat | `openamer.chat` | — (sidebar icon) |
| Ask OpenAmer to explain this | `openamer.explain` | Editor/Explorer context menu |
| Ask OpenAmer to fix this | `openamer.fix` | Editor context menu (selection) |

## Development

```bash
npm install
npm run compile   # tsc -p ./
```

Launch the extension in VS Code: F5 → "Extension Development Host".

## Extension API

This extension connects to OpenAmer via the [Model Context Protocol](https://modelcontextprotocol.io) (JSON-RPC over stdio). It spawns `openamer mcp` as a child process and communicates via the MCP protocol.

## License

MIT
# OpenAmer Agent - VS Code Extension

OpenAmer AI Agent integration for Visual Studio Code. Chat with OpenAmer, explain files, and fix code — all from within VS Code.

## Features

- **🤖 OpenAmer Chat** — Full chat interface in the VS Code Sidebar. Ask questions, get code help, run prompts.
- **📖 Explain This** — Right-click any file in the Explorer or type `Ask OpenAmer to explain this` to get an AI analysis of the file.
- **🔧 Fix This** — Select code in the editor, right-click, and choose `Ask OpenAmer to fix this` to get AI-generated fixes.
- **🔌 MCP Client** — Automatically starts `openamer mcp` via stdio JSON-RPC. Status bar shows connection state.
- **📊 Status Bar** — Shows connection status at a glance. Click to open the Chat view.

## Requirements

- **OpenAmer CLI** installed and available in PATH (`openamer` or `openamer.exe`)
- **VS Code** ^1.90.0
- **Node.js** ^18 or later (for development only)

## Installation

### From VSIX (recommended)

1. Download the latest `.vsix` from the releases page
2. In VS Code: Extensions → `...` → Install from VSIX
3. Select the downloaded file
4. Reload VS Code

### From source

```bash
git clone <repo>
cd openamer-vscode
npm install
npm run compile
code --install-extension openamer-vscode-0.1.0.vsix
```

## Usage

### Start chatting

1. Click the OpenAmer icon in the Activity Bar (or run `OpenAmer: Chat` from the command palette)
2. The Chat view opens in the Sidebar
3. Type your question and press Enter

### Explain a file

- **Explorer context menu:** Right-click any file → `Ask OpenAmer to explain this`
- **Command palette:** Run `Ask OpenAmer to explain this` with a file open

### Fix selected code

1. Select the code you want fixed in the editor
2. Right-click → `Ask OpenAmer to fix this` (only appears when text is selected)

## Commands

| Command | Title | Description |
|---------|-------|-------------|
| `openamer.chat` | OpenAmer: Chat | Open the OpenAmer Chat view |
| `openamer.explain` | Ask OpenAmer to explain this | Explain the active file or selection |
| `openamer.fix` | Ask OpenAmer to fix this | Fix the selected code |

## Configuration

Set in VS Code settings (`settings.json`):

```json
{
  "openamer.mcpCommand": "openamer"
}
```

If OpenAmer is not in PATH, set the full path:

```json
{
  "openamer.mcpCommand": "C:\\Users\\damir\\AppData\\Local\\openamer-laptop\\openamer.exe"
}
```

## Context Menus

- **Editor context menu** — `Ask OpenAmer to fix this` (shown when text is selected)
- **Explorer context menu** — `Ask OpenAmer to explain this` (shown on file right-click)

## Development

```bash
# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Watch mode (auto-compile on changes)
npm run watch

# Package as VSIX
npm install -g @vscode/vsce
vsce package
```

### Project structure

```
openamer-vscode/
├── package.json          # Extension manifest
├── tsconfig.json          # TypeScript config
├── src/
│   └── extension.ts       # Main extension code
└── README.md
```

## Extension Settings

This extension contributes the following settings:

* `openamer.mcpCommand`: Path or command name for the Openamer CLI (default: auto-detect)

## Known Issues

- MCP auto-connect requires `openamer mcp` to be a valid command. Ensure OpenAmer is installed.
- Long responses are truncated in the status bar notification. Full response appears in the Chat view.

## Release Notes

### 0.1.0

- Initial release
- MCP client with stdio JSON-RPC
- Chat Webview in sidebar
- Explain and Fix commands
- Status bar connection indicator
- Context menus for Explorer and Editor
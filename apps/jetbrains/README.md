# OpenAmer JetBrains IDE Extension

AI-powered code assistance inside IntelliJ IDEA, PyCharm, and other JetBrains IDEs.

## Features

- **Chat** (`Ctrl+Shift+A`) — Open the OpenAmer Agent chat sidebar
- **Explain** (right-click a file) — Ask OpenAmer to explain the current file
- **Fix** (right-click a selection) — Ask OpenAmer to fix selected code

All actions connect to the OpenAmer MCP server running on your machine via stdio JSON-RPC 2.0.

## Project Structure

```
apps/jetbrains/
├── plugin.xml                       # Plugin descriptor (actions, tool window, extensions)
├── gradle.build.kts                 # IntelliJ Platform Gradle build
├── README.md                        # This file
└── src/
    └── com/openamer/
        ├── ActionOpenAmerChat.kt       # Ctrl+Shift+A → Open Chat sidebar
        ├── ActionOpenAmerExplain.kt    # Right-click file → Explain
        ├── ActionOpenAmerFix.kt        # Right-click selection → Fix
        ├── OpenAmerToolWindow.kt       # Tool window factory + chat panel
        ├── MCPClient.kt                # MCP JSON-RPC client (ProcessBuilder → openamer mcp)
        └── OpenAmerNotifications.kt    # IDE notification helpers
```

## How It Works

1. **MCP Client** (`MCPClient.kt`) spawns `openamer mcp` as a subprocess via `ProcessBuilder`
2. Communication is over stdio using JSON-RPC 2.0 (MCP protocol)
3. The **Chat tool window** embeds a JCEF (Chromium) webview with a minimal HTML chat UI
4. **Explain** and **Fix** actions send file content / selected code as chat messages to the MCP server

## Building

The scaffold requires the IntelliJ Platform Gradle Plugin. It does not need to compile as-is — it demonstrates the complete source structure.

```bash
# Inside IntelliJ IDEA:
# Open the jetbrains/ directory as a project
# IntelliJ will detect the Gradle build file and import it
# Run or debug with the Gradle runIde task
```

## Prerequisites

- OpenAmer CLI installed and on PATH (`openamer mcp` must work)
- IntelliJ IDEA 2024.3+ (or any JetBrains IDE with the Platform Plugin SDK)
- JDK 21+

## Configuration

The extension auto-connects to `openamer mcp` on startup. You can set the `OPENAMER_PATH` environment variable to use a specific OpenAmer binary, or ensure `openamer` is on your PATH.

---

*Part of the [OpenAmer Agent](https://github.com/openamer/openamer) project.*
# OpenAmer Agent — IntelliJ Plugin

OpenAmer AI Agent integration for JetBrains IDEs (IntelliJ IDEA, PyCharm, WebStorm, etc.).

## Features

- **Chat Panel** — Sidebar tool window with a JCEF-based webview chat UI
- **Explain Code** — Select code in the editor, right-click → "Ask OpenAmer to explain this"
- **Fix Code** — Select code, right-click → "Ask OpenAmer to fix this"
- **MCP Backend** — Communicates with the OpenAmer MCP server over stdio JSON-RPC

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 IntelliJ IDE                     │
│  ┌───────────────────────────────────────────┐  │
│  │   ToolWindow "OpenAmerChat"               │  │
│  │   ┌─────────────────────────────────┐     │  │
│  │   │  JCEFHtmlPanel (Webview)        │     │  │
│  │   │  - Dark-themed chat UI          │     │  │
│  │   │  - User/assistant messages      │     │  │
│  │   │  - Typing indicator             │     │  │
│  │   └─────────────────────────────────┘     │  │
│  │                                            │  │
│  │   MCPClient (stdio JSON-RPC)               │  │
│  │   └─ ProcessBuilder("openamer mcp")        │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  Actions:                                        │
│  - Ctrl+Shift+A  → OpenAmer Chat                 │
│  - EditorPopup   → Explain / Fix (selected code) │
└─────────────────────────────────────────────────┘
```

## Build

### Prerequisites
- JDK 21+
- IntelliJ IDEA Community or Ultimate 2024.3+
- OpenAmer CLI installed and available on `PATH`

### Build from source

```bash
cd apps/jetbrains
./gradlew buildPlugin
```

The plugin artifact will be at `build/distributions/OpenAmerAgent-0.1.0.zip`.

### Install

1. Open IntelliJ IDEA → **Settings** → **Plugins** → ⚙️ → **Install Plugin from Disk...**
2. Select the built `.zip` file
3. Restart the IDE

## Usage

### Chat
1. Press `Ctrl+Shift+A` or use **Tools** → **OpenAmer Chat**
2. Type your question in the chat panel and press Enter
3. The plugin communicates with the OpenAmer MCP server running in the background

### Explain Code
1. Select code in the editor
2. Right-click → **Ask OpenAmer to explain this**
3. The chat panel opens with the selected code sent as an explain request

### Fix Code
1. Select code in the editor
2. Right-click → **Ask OpenAmer to fix this**
3. The chat panel opens with the selected code sent as a fix request

## Development

### Project structure
```
apps/jetbrains/
├── build.gradle.kts          # Gradle build with IntelliJ Platform Plugin
├── resources/
│   └── META-INF/
│       └── plugin.xml         # Plugin descriptor
├── src/
│   └── com/
│       └── openamer/
│           ├── ActionOpenAmerChat.kt       # Chat action (Ctrl+Shift+A)
│           ├── ActionOpenAmerExplain.kt    # Explain context action
│           ├── ActionOpenAmerFix.kt        # Fix context action
│           ├── MCPClient.kt               # JSON-RPC MCP client
│           ├── OpenAmerNotifications.kt   # Notification helpers
│           └── OpenAmerToolWindow.kt      # ToolWindow + JCEF chat panel
└── README.md
```

### Key classes

| Class | Responsibility |
|-------|---------------|
| `MCPClient` | Spawns `openamer mcp` as subprocess, sends/receives JSON-RPC 2.0 over stdio |
| `OpenAmerToolWindowFactory` | Registers the tool window; companion `openAndSend()` for actions |
| `ChatPanel` | JCEF HTML panel with dark-themed chat UI and JS bridge |
| `ActionOpenAmerChat` | Opens the chat panel, bound to `Ctrl+Shift+A` |
| `ActionOpenAmerExplain` | Sends selected code as explain request via context menu |
| `ActionOpenAmerFix` | Sends selected code as fix request via context menu |
| `OpenAmerNotifications` | IDE balloon notifications for connection status and results |

## Configuration

The MCP client spawns `openamer mcp` with default PATH. If `openamer` is not on PATH,
update the command in `ChatPanel.connectMCP()` to use the absolute path.

## License

MIT
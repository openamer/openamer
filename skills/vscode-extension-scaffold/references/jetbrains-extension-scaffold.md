# JetBrains IDE Extension Scaffold (companion to VS Code)

When asked to build a JetBrains (IntelliJ Platform) extension analogous to a VS Code extension, produce a complete source-only scaffold matching the VS Code extension's feature set.

## File Layout

```
apps/jetbrains/
├── plugin.xml                       # Plugin descriptor (actions, tool window, menus)
├── gradle.build.kts                 # IntelliJ Platform Gradle build
├── README.md
└── src/com/openamer/
    ├── ActionOpenAmerChat.kt        # Ctrl+Shift+A → focus chat tool window
    ├── ActionOpenAmerExplain.kt     # Right-click file → send to MCP for explanation
    ├── ActionOpenAmerFix.kt         # Right-click selection → send to MCP for fix
    ├── OpenAmerToolWindow.kt        # ToolWindowFactory + JCEF chat panel
    ├── MCPClient.kt                 # MCP JSON-RPC client via ProcessBuilder
    └── OpenAmerNotifications.kt     # IDE notification helpers
```

## Key Differences from VS Code

| Concern | VS Code (TypeScript) | JetBrains (Kotlin) |
|---|---|---|
| Extension type | npm package | Gradle + IntelliJ Platform Plugin |
| Registration | `package.json` `contributes` | `plugin.xml` `<extensions>` / `<actions>` |
| Actions | `registerCommand()` | `AnAction` subclass + `plugin.xml` |
| Shortcut | In `package.json` via `keybindings` | In `plugin.xml` via `<keyboard-shortcut>` |
| Context menu | `editor/context`, `explorer/context` | `EditorPopupMenu` group via `<add-to-group>` |
| Webview | `WebviewViewProvider` + HTML string | `JCEFHtmlPanel` + HTML string |
| MCP client | `child_process.spawn` | `java.lang.ProcessBuilder` |
| Build | `tsc` (TypeScript) | IntelliJ Gradle Plugin + Kotlin 2.1 |
| Minimum IDE | VS Code 1.90 | IntelliJ IDEA 2024.3 |

## 1. `plugin.xml` — Manifest Anatomy

### Tool Window
```xml
<extensions defaultExtensionNs="com.intellij">
    <toolWindow
            id="OpenAmerChat"
            anchor="right"
            icon="AllIcons.General.Chat"
            factoryClass="com.openamer.OpenAmerToolWindowFactory"
            doNotActivateOnStart="true"/>
</extensions>
```

### Actions with Keyboard Shortcut
```xml
<actions>
    <action id="OpenAmer.Chat"
            class="com.openamer.ActionOpenAmerChat"
            text="OpenAmer Chat"
            description="Open the OpenAmer Agent chat panel"
            icon="AllIcons.General.Chat">
        <keyboard-shortcut keymap="$default"
                           first-keystroke="control shift A"/>
    </action>
</actions>
```

### Context Menu (Right-Click)
```xml
<action id="OpenAmer.Explain"
        class="com.openamer.ActionOpenAmerExplain"
        text="Ask OpenAmer to explain this">
    <add-to-group group-id="EditorPopupMenu" anchor="first"/>
</action>
<action id="OpenAmer.Fix"
        class="com.openamer.ActionOpenAmerFix"
        text="Ask OpenAmer to fix this">
    <add-to-group group-id="EditorPopupMenu" anchor="after"
                  relative-to-action="OpenAmer.Explain"/>
</action>
```

## 2. Action Classes (Kotlin)

### Chat Action
```kotlin
class ActionOpenAmerChat : AnAction(), DumbAware {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val toolWindow = ToolWindowManager.getInstance(project)
            .getToolWindow("OpenAmerChat") ?: return
        if (!toolWindow.isAvailable) toolWindow.isAvailable = true
        toolWindow.activate(null, true, true)
    }
    override fun update(e: AnActionEvent) {
        e.presentation.isEnabledAndVisible = e.project != null
    }
}
```

### Explain Action (reads full file)
```kotlin
class ActionOpenAmerExplain : AnAction(), DumbAware {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        if (file == null || file.isDirectory) return
        val text = file.loadTextOrNull() ?: return
        OpenAmerToolWindowChat.submitMessage(project,
            "Explain this code:\n\n```${file.extension}\n${text.take(8000)}\n```")
    }

    private fun VirtualFile.loadTextOrNull(): String? = try {
        if (length > 200_000) null else String(contentsToByteArray(), charset)
    } catch (_: Exception) { null }
}
```

### Fix Action (reads editor selection)
```kotlin
class ActionOpenAmerFix : AnAction(), DumbAware {
    override fun actionPerformed(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val selected = editor.selectionModel.selectedText ?: return
        OpenAmerToolWindowChat.submitMessage(e.project!!,
            "Fix this code:\n\n```text\n${selected.take(8000)}\n```")
    }
    override fun update(e: AnActionEvent) {
        val selection = e.getData(CommonDataKeys.EDITOR)?.selectionModel?.hasSelection()
        e.presentation.isEnabledAndVisible = selection == true
    }
}
```

## 3. Tool Window with JCEF Webview

```kotlin
class OpenAmerToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val chatPanel = OpenAmerToolWindowChat(project)
        val content = ContentFactory.getInstance()
            .createContent(chatPanel, "", false)
        toolWindow.contentManager.addContent(content)
    }
}
```

The chat panel extends `JPanel` and embeds a `JCEFHtmlPanel` (Chromium Embedded Framework). Messages flow from IDE actions → static `submitMessage()` → panel's `sendMessage()` → MCP client.

Pitfall: `JCEFHtmlPanel` requires JCEF jar on classpath and may not be available in all JetBrains IDEs (community IDEs bundle it; some have restrictions). For maximum compatibility, use an `EditorPane` with HTML instead.

## 4. MCP Client via ProcessBuilder

```kotlin
class MCPClient {
    private var process: Process? = null
    private val pending = ConcurrentHashMap<Int, PendingRequest>()
    private val reqId = AtomicInteger(0)

    fun connect(command: List<String>): Boolean {
        val pb = ProcessBuilder(command)
        pb.redirectErrorStream(false)
        process = pb.start()

        // Reader thread for stdout JSON-RPC
        val reader = BufferedReader(InputStreamReader(process!!.inputStream, "UTF-8"))
        Thread {
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                dispatchMessage(line!!)
            }
        }.apply { isDaemon = true; name = "openamer-mcp-reader"; start() }

        // Handshake
        request("initialize", mapOf(
            "protocolVersion" to "2024-11-05",
            "capabilities" to mapOf("tools" to emptyMap<String, String>()),
            "clientInfo" to mapOf("name" to "openamer-jetbrains", "version" to "0.1.0")
        ))
        notify("notifications/initialized")
        isConnected = true
        return true
    }

    fun chat(message: String): String? {
        val result = request("tools/call", mapOf(
            "name" to "openamer_chat",
            "arguments" to mapOf("message" to message)
        ))
        @Suppress("UNCHECKED_CAST")
        val content = (result as? Map<*, *>)?.get("content") as? List<Map<String, Any>>
        return content?.mapNotNull { c ->
            if (c["type"] == "text") c["text"] as? String else null
        }?.joinToString("")
    }
}
```

Pitfalls:
- **`dispatchMessage`** must use a daemon reader thread so it doesn't block the EDT
- **JSON parsing**: For a scaffold, a minimal hand-written parser suffices (see `MCPClient.kt` in the repo for a working ~50-line parser). For production, use Gson or kotlinx.serialization.
- **Timeout**: Always add a 30-second CompletableFuture timeout to `request()` to prevent hangs
- **Process cleanup**: `destroyForcibly()` in `disconnect()` — Process.destroy() is cooperative and may not terminate a hanging MCP server
- **EDT safety**: All UI updates must be wrapped in `SwingUtilities.invokeLater`

## 5. `gradle.build.kts`

```kotlin
plugins {
    id("org.jetbrains.intellij.platform.gradle") version "2.2.1"
    kotlin("jvm") version "2.1.0"
}

dependencies {
    intellijPlatform { intellijIdeaCommunity("2024.3") }
    implementation("com.google.code.gson:gson:2.11.0")
}

intellijPlatform {
    pluginConfiguration { id = "com.openamer.jetbrains"; name = "OpenAmer Agent"; version = "0.1.0" }
}

kotlin { jvmToolchain(21) }
```

Pitfall: `intellijIdeaCommunity` builds for the Community Edition. For Ultimate or other IDEs, use `intellijIdeaUltimate("2024.3")` or the appropriate platform type.

## Verification

After creating files, verify:
1. `plugin.xml` is well-formed XML (xsi:schemaLocation, no unclosed tags)
2. Every `class="com.openamer.Xxx"` in plugin.xml has a corresponding `.kt` file
3. Every `<keyboard-shortcut>` has both `keymap` and `first-keystroke`
4. The MCP handshake sequence matches the VS Code version (identical JSON-RPC protocol)
5. The `build_repomap_parser` style subcommand parser follows `openamer-feature-engineering` conventions

## Companion Skill

See also: `vscode-extension-scaffold` (primary skill — this file documents only the JetBrains-specific delta).
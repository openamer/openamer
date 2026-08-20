package com.openamer

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import com.intellij.ui.jcef.JCEFHtmlPanel
import java.awt.BorderLayout
import java.util.concurrent.CopyOnWriteArrayList
import javax.swing.JPanel
import javax.swing.SwingUtilities

// ──────────────────────────────────────────────────────────────────────────────
// Tool Window Factory
// ──────────────────────────────────────────────────────────────────────────────

/**
 * Factory that creates the OpenAmer Chat tool window registered in plugin.xml.
 */
class OpenAmerToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val chatPanel = OpenAmerToolWindowChat(project)
        val content = ContentFactory.getInstance()
            .createContent(chatPanel, "", false)
        toolWindow.contentManager.addContent(content)
    }

    override fun shouldBeAvailable(project: Project): Boolean = true
}

// ──────────────────────────────────────────────────────────────────────────────
// Chat Panel
// ──────────────────────────────────────────────────────────────────────────────

/**
 * Sidebar panel with a full chat UI rendered via JCEF (embedded Chromium).
 *
 * In production this would be a richer HTML/JS chat interface backed by the
 * MCP client. For the scaffold, it provides a minimal send-a-message flow.
 */
class OpenAmerToolWindowChat(project: Project) : JPanel(BorderLayout()) {

    private val browser = JCEFHtmlPanel(null, initialHtml())
    private val mcpClient = MCPClient()

    init {
        add(browser, BorderLayout.CENTER)
        browser.loadHTML(initialHtml())

        // Auto-connect to the MCP server
        mcpClient.connect(listOf("openamer", "mcp")).let { connected ->
            if (!connected) {
                updateContent(
                    "assistant",
                    "⚠️ Could not connect to OpenAmer MCP server.\n" +
                        "Make sure `openamer mcp` is running on your system."
                )
            } else {
                updateContent("assistant", "👋 Connected. Ask me anything about your code.")
            }
        }
    }

    /** Send a chat message from the IDE (e.g. Explain / Fix actions). */
    fun sendMessage(text: String) {
        if (text.isBlank()) return
        updateContent("user", text)

        if (!mcpClient.isConnected) {
            updateContent("assistant", "❌ Not connected to OpenAmer MCP server.")
            return
        }

        SwingUtilities.invokeLater {
            val response = mcpClient.chat(text)
            updateContent("assistant", response ?: "⚠️ Empty response from MCP server.")
        }
    }

    /** Show a notification line in the chat HTML. */
    private fun updateContent(role: String, text: String) {
        val escaped = text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("\n", "<br>")

        browser.executeJavaScript(
            "addMessage('$role', '${escaped.replace("'", "\\'")}');",
            null, 0
        )
    }

    companion object {
        /** Convenience entry point for actions to submit a message to the active chat panel. */
        private val instances = CopyOnWriteArrayList<OpenAmerToolWindowChat>()

        fun submitMessage(project: Project, text: String) {
            val instance = instances.firstOrNull() ?: run {
                val toolWindow =
                    com.intellij.openapi.wm.ToolWindowManager.getInstance(project)
                        .getToolWindow("OpenAmerChat")
                toolWindow?.activate(null, true, true)
                return
            }
            instance.sendMessage(text)
        }
    }

    private fun initialHtml(): String = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    color: var(--jb-foreground, #1e1e1e);
    background: var(--jb-background, #ffffff);
    display: flex; flex-direction: column; height: 100vh;
  }
  #messages { flex: 1; overflow-y: auto; padding: 8px; }
  .msg { margin-bottom: 8px; padding: 6px 8px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; }
  .msg.user { background: #e3f2fd; border-left: 3px solid #1565c0; }
  .msg.assistant { background: #f5f5f5; border-left: 3px solid #43a047; }
  #input-bar { display: flex; border-top: 1px solid #ccc; padding: 6px; gap: 4px; }
  #input { flex: 1; resize: none; border: 1px solid #ccc; border-radius: 2px; padding: 6px; font-family: inherit; font-size: inherit; }
  #input:focus { outline: 1px solid #1565c0; }
  #send { background: #1565c0; color: #fff; border: none; padding: 4px 12px; border-radius: 2px; cursor: pointer; }
  #send:hover { background: #0d47a1; }
</style>
</head>
<body>
  <div id="messages">
    <div class="msg assistant">Connecting to OpenAmer…</div>
  </div>
  <div id="input-bar">
    <textarea id="input" rows="3" placeholder="Ask OpenAmer…"></textarea>
    <button id="send">Send</button>
  </div>
  <script>
    function addMessage(role, text) {
      const el = document.getElementById('messages');
      const div = document.createElement('div');
      div.className = 'msg ' + role;
      div.textContent = text.replace(/<br>/g, '\\n');
      el.appendChild(div);
      el.scrollTop = el.scrollHeight;
    }
    document.getElementById('send').onclick = function() {
      const input = document.getElementById('input');
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
    };
    document.getElementById('input').onkeydown = function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('send').click();
      }
    };
  </script>
</body>
</html>""".trimIndent()
}
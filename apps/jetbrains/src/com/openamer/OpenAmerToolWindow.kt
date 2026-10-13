package com.openamer

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.jcef.JCEFHtmlPanel
import com.intellij.ui.content.ContentFactory
import org.cef.browser.CefBrowser
import org.cef.handler.CefLoadHandlerAdapter
import java.awt.BorderLayout
import java.awt.Dimension
import java.util.concurrent.CompletableFuture
import javax.swing.JPanel
import javax.swing.SwingUtilities

/**
 * ToolWindowFactory that creates the OpenAmer Chat side panel.
 * The panel embeds a JCEFHtmlPanel that communicates with the MCP backend
 * via a JavaScript bridge injected into the page.
 */
class OpenAmerToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = ChatPanel(project)
        val content = ContentFactory.getInstance().createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)

        // Store reference so static openAndSend() can find it
        synchronized(OPEN_PANELS) {
            OPEN_PANELS[project] = panel
        }
    }

    override fun init(toolWindow: ToolWindow) {
        toolWindow.stripeTitle = "OpenAmer Chat"
    }

    override fun shouldBeAvailable(project: Project): Boolean = true

    companion object {
        private val OPEN_PANELS = HashMap<Project, ChatPanel>()

        /**
         * Opens the OpenAmer Chat tool window and sends the given message.
         * Safe to call from any thread — dispatches to EDT if needed.
         */
        fun openAndSend(project: Project, message: String) {
            val toolWindow = com.intellij.openapi.wm.ToolWindowManager.getInstance(project)
                .getToolWindow("OpenAmerChat") ?: return

            toolWindow.activate(null, true)

            val panel = synchronized(OPEN_PANELS) { OPEN_PANELS[project] }
            if (panel != null) {
                panel.sendMessage(message)
            }
        }
    }
}

/**
 * The actual chat panel component containing the JCEF webview.
 */
class ChatPanel(private val project: Project) : JPanel(BorderLayout()) {

    private val htmlPanel: JCEFHtmlPanel
    private val callbacks = mutableMapOf<String, CompletableFuture<String>>()
    private var requestIdCounter = 0
    private val mcpClient = MCPClient()

    init {
        preferredSize = Dimension(400, 600)

        htmlPanel = JCEFHtmlPanel(null, "about:blank")
        htmlPanel.setPreferredSize(Dimension(400, 600))

        add(htmlPanel, BorderLayout.CENTER)

        // Wait for the browser to finish loading, then inject the UI
        htmlPanel.cefBrowser.addLoadHandler(object : CefLoadHandlerAdapter() {
            override fun onLoadEnd(browser: CefBrowser?, frame: CefBrowser?,
                                    httpStatusCode: Int) {
                if (frame?.isMain == true) {
                    injectChatUI()
                    // Register the JS bridge for receiving responses
                    registerJSBridge()
                }
            }
        })

        // Load the initial HTML page
        htmlPanel.loadHTML(initialChatHTML())

        // Connect to the MCP backend
        connectMCP()
    }

    private fun connectMCP() {
        try {
            mcpClient.connect(listOf("openamer", "mcp"))
            // List available tools on connect
            mcpClient.listTools()?.let { tools ->
                val toolsJson = com.google.gson.GsonBuilder().setPrettyPrinting().create()
                    .toJson(tools)
                executeJavaScript("updateToolsList($toolsJson)")
            }
        } catch (ex: Exception) {
            executeJavaScript("showError('Failed to connect to OpenAmer MCP: ${ex.message}')")
        }
    }

    /**
     * Sends a message to the chat UI and forwards it to the MCP backend.
     */
    fun sendMessage(message: String) {
        // Add user message to the chat UI
        val escaped = message.replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "")
        executeJavaScript("addUserMessage('$escaped')")

        // Send to MCP backend
        sendToMCP(message)
    }

    private fun sendToMCP(message: String) {
        Thread {
            try {
                val response = mcpClient.chat(message)
                val responseText = response?.get("content")?.asString ?: "No response"
                val escaped = responseText.replace("'", "\\'")
                    .replace("\n", "\\n")
                    .replace("\r", "")
                executeJavaScript("addAssistantMessage('$escaped')")
            } catch (ex: Exception) {
                val escaped = ex.message?.replace("'", "\\'")
                    ?.replace("\n", "\\n") ?: "Unknown error"
                executeJavaScript("showError('$escaped')")
            }
        }.apply { isDaemon = true }.start()
    }

    private fun executeJavaScript(script: String) {
        SwingUtilities.invokeLater {
            htmlPanel.cefBrowser.executeJavaScript(script, htmlPanel.cefBrowser.url, 0)
        }
    }

    private fun registerJSBridge() {
        // Register a JS function that the page can call to receive responses
        val js = """
            window.openamerBridge = {
                sendMessage: function(msg) {
                    // This will be called from JS when user sends a message
                    // We use the CefMessageRouter or a polling approach
                },
                receiveResponse: function(id, response) {
                    // Called from Java when response arrives
                    var event = new CustomEvent('openamer-response', {
                        detail: { id: id, response: response }
                    });
                    window.dispatchEvent(event);
                }
            };
        """.trimIndent()
        htmlPanel.cefBrowser.executeJavaScript(js, "about:blank", 0)
    }

    private fun injectChatUI() {
        // The chat UI is already in the HTML — this hook is for post-load injection
    }

    private fun initialChatHTML(): String {
        return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1e1e1e;
    color: #d4d4d4;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  #header {
    padding: 12px 16px;
    background: #2d2d2d;
    border-bottom: 1px solid #3c3c3c;
    font-size: 14px;
    font-weight: 600;
    color: #569cd6;
    flex-shrink: 0;
  }
  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .message {
    padding: 8px 12px;
    border-radius: 6px;
    max-width: 85%;
    line-height: 1.4;
    font-size: 13px;
    white-space: pre-wrap;
    word-wrap: break-word;
  }
  .user {
    background: #094771;
    align-self: flex-end;
    color: #e0e0e0;
  }
  .assistant {
    background: #2d2d2d;
    align-self: flex-start;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
  }
  .error {
    background: #5a1d1d;
    align-self: center;
    color: #f48771;
    border: 1px solid #6e2d2d;
    font-size: 12px;
  }
  .system {
    background: #1e3a5f;
    align-self: center;
    color: #9cdcfe;
    font-size: 11px;
    padding: 4px 8px;
  }
  #input-area {
    display: flex;
    padding: 8px 12px;
    background: #252526;
    border-top: 1px solid #3c3c3c;
    gap: 8px;
    flex-shrink: 0;
  }
  #input {
    flex: 1;
    background: #3c3c3c;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 8px 12px;
    color: #d4d4d4;
    font-size: 13px;
    outline: none;
    resize: none;
  }
  #input:focus { border-color: #569cd6; }
  #send-btn {
    background: #569cd6;
    color: #1e1e1e;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    align-self: flex-end;
  }
  #send-btn:hover { background: #75b8e8; }
  #send-btn:disabled { opacity: 0.5; cursor: default; }
  #status {
    padding: 4px 12px;
    font-size: 11px;
    color: #888;
    flex-shrink: 0;
  }
  .connected { color: #6a9955; }
  .disconnected { color: #f48771; }
  .typing-indicator {
    font-style: italic;
    color: #888;
    font-size: 12px;
    padding: 4px 12px;
  }
</style>
</head>
<body>
<div id="header">OpenAmer Agent</div>
<div id="messages"></div>
<div id="status" class="disconnected">● Disconnected</div>
<div id="input-area">
  <textarea id="input" rows="2" placeholder="Ask OpenAmer anything..." 
    onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMessage();}"></textarea>
  <button id="send-btn" onclick="sendMessage()">Send</button>
</div>
<script>
  function addUserMessage(text) {
    var div = document.createElement('div');
    div.className = 'message user';
    div.textContent = text;
    document.getElementById('messages').appendChild(div);
    scrollToBottom();
  }
  function addAssistantMessage(text) {
    removeTypingIndicator();
    var div = document.createElement('div');
    div.className = 'message assistant';
    div.textContent = text;
    document.getElementById('messages').appendChild(div);
    scrollToBottom();
  }
  function showError(text) {
    removeTypingIndicator();
    var div = document.createElement('div');
    div.className = 'message error';
    div.textContent = '⚠ ' + text;
    document.getElementById('messages').appendChild(div);
    scrollToBottom();
  }
  function showTypingIndicator() {
    removeTypingIndicator();
    var div = document.createElement('div');
    div.className = 'typing-indicator';
    div.id = 'typing-indicator';
    div.textContent = 'OpenAmer is thinking...';
    document.getElementById('messages').appendChild(div);
    scrollToBottom();
  }
  function removeTypingIndicator() {
    var el = document.getElementById('typing-indicator');
    if (el) el.remove();
  }
  function setConnected(connected) {
    var status = document.getElementById('status');
    status.textContent = connected ? '● Connected' : '● Disconnected';
    status.className = connected ? 'connected' : 'disconnected';
    document.getElementById('send-btn').disabled = !connected;
  }
  function updateToolsList(tools) {
    console.log('Available tools:', tools);
  }
  function scrollToBottom() {
    var msgs = document.getElementById('messages');
    msgs.scrollTop = msgs.scrollHeight;
  }
  function sendMessage() {
    var input = document.getElementById('input');
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    addUserMessage(text);
    showTypingIndicator();
    // Notify Java via the JS bridge
    try {
      window.openamerBridge.sendMessage(text);
    } catch(e) {
      // Fallback: Java will poll via executeJavaScript
    }
    // The Java side handles the actual send via the bridge
    // We dispatch a custom event that Java can listen for
    var event = new CustomEvent('user-message', { detail: text });
    window.dispatchEvent(event);
  }
</script>
</body>
</html>
        """.trimIndent()
    }
}
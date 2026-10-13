"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const cp = __importStar(require("child_process"));
const path = __importStar(require("path"));
const crypto = __importStar(require("crypto"));
// ─── MCP Client ──────────────────────────────────────────────────────────────
class MCPClient {
    process = null;
    buffer = '';
    pending = new Map();
    nextId = 1;
    connected = false;
    onMessage = null;
    onStatusChange = null;
    set onMessageCallback(cb) {
        this.onMessage = cb;
    }
    set onStatusChangeCallback(cb) {
        this.onStatusChange = cb;
    }
    get isConnected() {
        return this.connected;
    }
    async connect(command) {
        if (this.process) {
            this.disconnect();
        }
        return new Promise((resolve, reject) => {
            try {
                // Split command into program and args
                const parts = command.split(' ');
                const program = parts[0];
                const args = parts.slice(1);
                this.process = cp.spawn(program, args, {
                    stdio: ['pipe', 'pipe', 'pipe'],
                    shell: process.platform === 'win32',
                });
                const timeout = setTimeout(() => {
                    reject(new Error('MCP connection timeout'));
                }, 15000);
                this.process.stdout?.on('data', (data) => {
                    this.buffer += data.toString('utf-8');
                    this.processBuffer();
                });
                this.process.stderr?.on('data', (data) => {
                    console.error(`[openamer-mcp:stderr] ${data.toString().trim()}`);
                });
                this.process.on('error', (err) => {
                    clearTimeout(timeout);
                    this.setConnected(false);
                    reject(new Error(`MCP process error: ${err.message}`));
                });
                this.process.on('exit', (code) => {
                    this.setConnected(false);
                    this.process = null;
                    // Reject all pending requests
                    for (const [, pending] of this.pending) {
                        pending.reject(new Error(`MCP process exited with code ${code}`));
                    }
                    this.pending.clear();
                });
                // Send initialize request
                this.request('initialize', {
                    protocolVersion: '2024-11-05',
                    capabilities: {},
                    clientInfo: { name: 'openamer-vscode', version: '0.1.0' },
                })
                    .then(() => {
                    clearTimeout(timeout);
                    this.setConnected(true);
                    resolve();
                })
                    .catch((err) => {
                    clearTimeout(timeout);
                    reject(err);
                });
            }
            catch (err) {
                reject(err);
            }
        });
    }
    async request(method, params) {
        if (!this.process || !this.process.stdin) {
            throw new Error('MCP not connected');
        }
        const id = this.nextId++;
        const request = {
            jsonrpc: '2.0',
            id,
            method,
            params,
        };
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
            const message = JSON.stringify(request) + '\n';
            this.process.stdin.write(message, 'utf-8');
        });
    }
    async chat(message) {
        const result = await this.request('tools/call', {
            name: 'chat',
            arguments: { message },
        });
        return JSON.stringify(result);
    }
    async listTools() {
        const result = await this.request('tools/list');
        return result.tools || [];
    }
    disconnect() {
        if (this.process) {
            try {
                this.process.stdin?.end();
                this.process.kill();
            }
            catch {
                // ignore
            }
            this.process = null;
        }
        this.setConnected(false);
        this.pending.clear();
    }
    processBuffer() {
        const lines = this.buffer.split('\n');
        // Keep the last incomplete line in the buffer
        this.buffer = lines.pop() || '';
        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed)
                continue;
            try {
                const msg = JSON.parse(trimmed);
                if ('id' in msg && 'result' in msg) {
                    // Response
                    const pending = this.pending.get(msg.id);
                    if (pending) {
                        this.pending.delete(msg.id);
                        if (msg.error) {
                            pending.reject(new Error(msg.error.message));
                        }
                        else {
                            pending.resolve(msg.result);
                        }
                    }
                }
                else if ('id' in msg && 'error' in msg) {
                    // Error response
                    const pending = this.pending.get(msg.id);
                    if (pending) {
                        this.pending.delete(msg.id);
                        pending.reject(new Error(msg.error.message));
                    }
                }
                else if ('method' in msg && !('id' in msg)) {
                    // Notification from server
                    const notification = msg;
                    if (notification.method === 'message' && this.onMessage) {
                        this.onMessage(JSON.stringify(notification.params));
                    }
                }
            }
            catch {
                // Skip malformed JSON
            }
        }
    }
    setConnected(state) {
        if (this.connected !== state) {
            this.connected = state;
            this.onStatusChange?.(state);
        }
    }
}
// ─── Chat Webview Provider ───────────────────────────────────────────────────
class ChatWebviewProvider {
    _extensionUri;
    static viewType = 'openamerChat';
    _view;
    _mcpClient;
    constructor(_extensionUri, mcpClient) {
        this._extensionUri = _extensionUri;
        this._mcpClient = mcpClient;
    }
    resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };
        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'sendMessage':
                    if (data.text) {
                        webviewView.webview.postMessage({
                            type: 'addMessage',
                            role: 'user',
                            content: data.text,
                        });
                        try {
                            const response = await this._mcpClient.chat(data.text);
                            webviewView.webview.postMessage({
                                type: 'addMessage',
                                role: 'assistant',
                                content: response,
                            });
                        }
                        catch (err) {
                            webviewView.webview.postMessage({
                                type: 'addMessage',
                                role: 'assistant',
                                content: `**Error:** ${err instanceof Error ? err.message : 'Unknown error'}`,
                            });
                        }
                    }
                    break;
            }
        });
    }
    postMessage(message) {
        this._view?.webview.postMessage(message);
    }
    _getHtmlForWebview(webview) {
        const nonce = crypto.randomBytes(16).toString('base64');
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'nonce-${nonce}';">
  <title>OpenAmer Chat</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
      font-size: var(--vscode-font-size, 13px);
      color: var(--vscode-editor-foreground, #ccc);
      background: var(--vscode-sideBar-background, #1e1e1e);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    #messages {
      flex: 1;
      overflow-y: auto;
      padding: 8px 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .message {
      padding: 8px 12px;
      border-radius: 6px;
      max-width: 90%;
      word-wrap: break-word;
      white-space: pre-wrap;
      line-height: 1.4;
    }
    .message.user {
      background: var(--vscode-textBlockQuote-background, #2a2d2e);
      align-self: flex-end;
      border: 1px solid var(--vscode-input-border, #3c3c3c);
    }
    .message.assistant {
      background: var(--vscode-editor-background, #1e1e1e);
      align-self: flex-start;
      border: 1px solid var(--vscode-input-border, #3c3c3c);
    }
    .message .role-label {
      font-size: 10px;
      text-transform: uppercase;
      opacity: 0.6;
      margin-bottom: 4px;
      font-weight: 600;
    }
    .message .content {
      font-size: var(--vscode-font-size, 13px);
    }
    #input-area {
      display: flex;
      gap: 6px;
      padding: 8px 12px;
      border-top: 1px solid var(--vscode-input-border, #3c3c3c);
      background: var(--vscode-sideBar-background, #1e1e1e);
    }
    #input {
      flex: 1;
      background: var(--vscode-input-background, #3c3c3c);
      color: var(--vscode-input-foreground, #ccc);
      border: 1px solid var(--vscode-input-border, #555);
      border-radius: 4px;
      padding: 6px 10px;
      font-family: inherit;
      font-size: inherit;
      resize: none;
      outline: none;
    }
    #input:focus {
      border-color: var(--vscode-focusBorder, #007acc);
    }
    #send {
      background: var(--vscode-button-background, #007acc);
      color: var(--vscode-button-foreground, #fff);
      border: none;
      border-radius: 4px;
      padding: 6px 14px;
      cursor: pointer;
      font-family: inherit;
      font-size: inherit;
      font-weight: 600;
    }
    #send:hover {
      background: var(--vscode-button-hoverBackground, #005f9e);
    }
    #send:disabled {
      opacity: 0.5;
      cursor: default;
    }
    .status-bar {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      font-size: 11px;
      border-top: 1px solid var(--vscode-input-border, #3c3c3c);
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    .status-dot.connected { background: #4ecdc4; }
    .status-dot.disconnected { background: #ff6b6b; }
    .status-text { opacity: 0.7; }
  </style>
</head>
<body>
  <div id="messages"></div>
  <div id="input-area">
    <textarea id="input" rows="2" placeholder="Ask OpenAmer..."></textarea>
    <button id="send">Send</button>
  </div>
  <div class="status-bar">
    <div class="status-dot disconnected" id="statusDot"></div>
    <span class="status-text" id="statusText">Disconnected</span>
  </div>
  <script nonce="${nonce}">
    (function() {
      const vscode = acquireVsCodeApi();
      const messagesEl = document.getElementById('messages');
      const inputEl = document.getElementById('input');
      const sendBtn = document.getElementById('send');
      const statusDot = document.getElementById('statusDot');
      const statusText = document.getElementById('statusText');

      function addMessage(role, content) {
        const div = document.createElement('div');
        div.className = 'message ' + role;
        div.innerHTML = '<div class="role-label">' + role + '</div><div class="content">' + escapeHtml(content) + '</div>';
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }

      function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
      }

      function sendMessage() {
        const text = inputEl.value.trim();
        if (!text) return;
        inputEl.value = '';
        sendBtn.disabled = true;
        vscode.postMessage({ type: 'sendMessage', text: text });
      }

      inputEl.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });

      sendBtn.addEventListener('click', sendMessage);

      window.addEventListener('message', function(event) {
        const msg = event.data;
        switch (msg.type) {
          case 'addMessage':
            addMessage(msg.role, msg.content);
            sendBtn.disabled = false;
            break;
          case 'setStatus':
            statusDot.className = 'status-dot ' + (msg.connected ? 'connected' : 'disconnected');
            statusText.textContent = msg.connected ? 'Connected' : 'Disconnected';
            break;
        }
      });
    })();
  </script>
</body>
</html>`;
    }
}
// ─── Extension Activation ────────────────────────────────────────────────────
let mcpClient;
let statusBarItem;
function activate(context) {
    mcpClient = new MCPClient();
    // Status bar
    statusBarItem = vscode.window.createStatusBarItem('openamer.status', vscode.StatusBarAlignment.Right, 100);
    statusBarItem.text = '$(comment-discussion) OpenAmer';
    statusBarItem.tooltip = 'OpenAmer Agent - Click to open chat';
    statusBarItem.command = 'openamer.chat';
    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    statusBarItem.show();
    updateStatusBar(false);
    mcpClient.onStatusChangeCallback = (connected) => {
        updateStatusBar(connected);
    };
    // Webview provider
    const provider = new ChatWebviewProvider(context.extensionUri, mcpClient);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(ChatWebviewProvider.viewType, provider, {
        webviewOptions: { retainContextWhenHidden: true },
    }));
    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand('openamer.chat', () => {
        vscode.commands.executeCommand('workbench.view.extension.openamer');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('openamer.explain', async (uri) => {
        let filePath = '';
        let fileContent = '';
        if (uri) {
            // Called from explorer context menu
            filePath = uri.fsPath;
            try {
                const doc = await vscode.workspace.openTextDocument(uri);
                fileContent = doc.getText().substring(0, 8000);
            }
            catch {
                fileContent = '(unable to read file)';
            }
        }
        else {
            // Called from command palette - use active editor
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                filePath = editor.document.uri.fsPath;
                fileContent = editor.document.getText().substring(0, 8000);
            }
            else {
                vscode.window.showErrorMessage('No file selected');
                return;
            }
        }
        const message = `Explain this file:\n\n\`\`\`\nPath: ${filePath}\n\n${fileContent}\n\`\`\``;
        vscode.window.showInformationMessage(`OpenAmer: Explaining ${path.basename(filePath)}...`);
        try {
            if (mcpClient?.isConnected) {
                const response = await mcpClient.chat(message);
                vscode.window.showInformationMessage(`OpenAmer: ${response.substring(0, 200)}...`);
                // Open chat view to show result
                vscode.commands.executeCommand('workbench.view.extension.openamer');
                provider.postMessage({ type: 'addMessage', role: 'user', content: message });
                provider.postMessage({ type: 'addMessage', role: 'assistant', content: response });
            }
            else {
                vscode.window.showWarningMessage('OpenAmer MCP is not connected. Open the chat view to connect.');
                vscode.commands.executeCommand('workbench.view.extension.openamer');
            }
        }
        catch (err) {
            vscode.window.showErrorMessage(`OpenAmer error: ${err instanceof Error ? err.message : 'Unknown error'}`);
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('openamer.fix', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active editor');
            return;
        }
        const selection = editor.selection;
        const text = editor.document.getText(selection).substring(0, 6000);
        if (!text) {
            vscode.window.showErrorMessage('No text selected');
            return;
        }
        const filePath = editor.document.uri.fsPath;
        const message = `Fix this code from ${path.basename(filePath)}:\n\n\`\`\`\n${text}\n\`\`\`\n\nReturn the fixed code only.`;
        vscode.window.showInformationMessage('OpenAmer: Fixing selected code...');
        try {
            if (mcpClient?.isConnected) {
                const response = await mcpClient.chat(message);
                // Show result in chat
                vscode.commands.executeCommand('workbench.view.extension.openamer');
                provider.postMessage({ type: 'addMessage', role: 'user', content: message });
                provider.postMessage({ type: 'addMessage', role: 'assistant', content: response });
                vscode.window.showInformationMessage('OpenAmer: Fix suggestion ready in chat');
            }
            else {
                vscode.window.showWarningMessage('OpenAmer MCP is not connected. Open the chat view to connect.');
                vscode.commands.executeCommand('workbench.view.extension.openamer');
            }
        }
        catch (err) {
            vscode.window.showErrorMessage(`OpenAmer error: ${err instanceof Error ? err.message : 'Unknown error'}`);
        }
    }));
    // Auto-connect to MCP
    autoConnectMCP();
}
function updateStatusBar(connected) {
    if (!statusBarItem)
        return;
    if (connected) {
        statusBarItem.text = '$(comment-discussion) OpenAmer';
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentForeground');
        statusBarItem.tooltip = 'OpenAmer Agent - Connected';
    }
    else {
        statusBarItem.text = '$(comment-discussion) OpenAmer';
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        statusBarItem.tooltip = 'OpenAmer Agent - Disconnected';
    }
}
async function autoConnectMCP() {
    // Try to find openamer in PATH or known locations
    const config = vscode.workspace.getConfiguration('openamer');
    let mcpCommand = config.get('mcpCommand', '');
    if (!mcpCommand) {
        // Try common locations
        const candidates = ['openamer', 'openamer.exe'];
        const home = process.env.OPENAMER_HOME || '';
        if (home) {
            candidates.unshift(path.join(home, 'openamer'));
            candidates.unshift(path.join(home, 'openamer.exe'));
        }
        for (const cmd of candidates) {
            try {
                await execCommand(`${cmd} --version`);
                mcpCommand = cmd;
                break;
            }
            catch {
                continue;
            }
        }
    }
    if (!mcpCommand) {
        vscode.window.showWarningMessage('OpenAmer CLI not found. Set "openamer.mcpCommand" in settings or ensure openamer is in PATH.');
        return;
    }
    try {
        await mcpClient.connect(`${mcpCommand} mcp`);
        vscode.window.showInformationMessage('OpenAmer MCP connected');
    }
    catch (err) {
        vscode.window.showWarningMessage(`OpenAmer MCP connection failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
}
function execCommand(command) {
    return new Promise((resolve, reject) => {
        cp.exec(command, { timeout: 5000 }, (err, stdout) => {
            if (err)
                reject(err);
            else
                resolve(stdout.trim());
        });
    });
}
function deactivate() {
    mcpClient?.disconnect();
    mcpClient = undefined;
}
//# sourceMappingURL=extension.js.map
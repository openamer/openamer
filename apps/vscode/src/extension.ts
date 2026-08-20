import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';

/* ------------------------------------------------------------------ */
/*  MCP Client — lightweight stdio JSON-RPC 2.0                       */
/* ------------------------------------------------------------------ */

interface MCPRequest {
  jsonrpc: '2.0';
  id: number;
  method: string;
  params?: unknown;
}

interface MCPResponse {
  jsonrpc: '2.0';
  id: number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

interface MCPNotification {
  jsonrpc: '2.0';
  method: string;
  params?: unknown;
}

type MCPMessage = MCPResponse | MCPNotification;

class MCPClient {
  private proc: cp.ChildProcess | null = null;
  private buf = '';
  private reqId = 0;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private onNotification: ((method: string, params: unknown) => void) | null = null;
  private onClose: (() => void) | null = null;

  get connected(): boolean {
    return this.proc !== null && this.proc.pid !== undefined && !this.proc.killed;
  }

  async connect(command: string, args: string[] = []): Promise<void> {
    this.proc = cp.spawn(command, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    });

    this.proc.stdout?.on('data', (chunk: Buffer) => {
      this.buf += chunk.toString();
      this.processBuffer();
    });

    this.proc.stderr?.on('data', (chunk: Buffer) => {
      console.error('[openamer:mcp]', chunk.toString());
    });

    this.proc.on('exit', () => {
      for (const [, p] of this.pending) p.reject(new Error('MCP server disconnected'));
      this.pending.clear();
      this.proc = null;
      this.onClose?.();
    });

    await this.request('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: { tools: {} },
      clientInfo: { name: 'openamer-vscode', version: '0.1.0' },
    });

    this.notify('notifications/initialized');
  }

  disconnect(): void {
    this.proc?.kill();
    this.proc = null;
  }

  async request(method: string, params?: unknown): Promise<unknown> {
    const id = ++this.reqId;
    const msg: MCPRequest = { jsonrpc: '2.0', id, method, params };

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`MCP request timed out: ${method}`));
      }, 30_000);

      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });

      this.write(JSON.stringify(msg) + '\n');
    });
  }

  notify(method: string, params?: unknown): void {
    const msg: MCPNotification = { jsonrpc: '2.0', method, params };
    this.write(JSON.stringify(msg) + '\n');
  }

  /** Send a chat message to the MCP server and stream back the response. */
  async chat(
    message: string,
    onToken: (text: string) => void,
  ): Promise<string> {
    try {
      const result = await this.request('tools/call', {
        name: 'openamer_chat',
        arguments: { message },
      });

      const r = result as { content?: Array<{ type: string; text?: string }> };
      const full =
        r?.content?.map((c) => (c.type === 'text' ? c.text ?? '' : '')).join('') ?? '';
      if (full) onToken(full);
      return full;
    } catch {
      // Fallback: treat the message as a prompt request
      const result = await this.request('prompts/get', {
        name: 'openamer_chat',
        arguments: { message },
      });
      const r = result as { messages?: Array<{ content: { text?: string } }> };
      const full =
        r?.messages?.map((m) => m.content?.text ?? '').join('') ?? '';
      if (full) onToken(full);
      return full;
    }
  }

  async listTools(): Promise<Array<{ name: string; description?: string }>> {
    const result = await this.request('tools/list');
    const r = result as { tools?: Array<{ name: string; description?: string }> };
    return r?.tools ?? [];
  }

  // ------------------------------------------------------------------ //
  private processBuffer(): void {
    const lines = this.buf.split('\n');
    this.buf = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg: MCPMessage = JSON.parse(line);
        if ('id' in msg) {
          const p = this.pending.get(msg.id);
          if (p) {
            this.pending.delete(msg.id);
            if (msg.error) p.reject(new Error(msg.error.message));
            else p.resolve(msg.result);
          }
        } else if ('method' in msg) {
          this.onNotification?.(msg.method, msg.params);
        }
      } catch { /* skip malformed lines */ }
    }
  }

  private write(data: string): void {
    if (this.proc?.stdin?.writable) {
      this.proc.stdin.write(data);
    }
  }

  set onNotificationCb(cb: ((method: string, params: unknown) => void) | null) {
    this.onNotification = cb;
  }

  set onCloseCb(cb: (() => void) | null) {
    this.onClose = cb;
  }
}

/* ------------------------------------------------------------------ */
/*  Chat Webview Provider                                              */
/* ------------------------------------------------------------------ */

class ChatWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'openamerChat';
  private _view?: vscode.WebviewView;

  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this._view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this._getHtml(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === 'chat') {
        const text = (msg.text ?? '').trim();
        if (!text) return;

        webviewView.webview.postMessage({ type: 'addMessage', role: 'user', text });

        const mcp = getMCP();
        if (!mcp?.connected) {
          webviewView.webview.postMessage({
            type: 'addMessage',
            role: 'assistant',
            text: '❌ Not connected to OpenAmer MCP server. Make sure `openamer mcp` is running.',
          });
          return;
        }

        webviewView.webview.postMessage({ type: 'addMessage', role: 'assistant', text: '⏳ Thinking…' });

        try {
          const full = await mcp.chat(text, (token) => {
            // Replace the thinking indicator with the real response
            webviewView.webview.postMessage({
              type: 'updateLastAssistant',
              text: token,
            });
          });
          webviewView.webview.postMessage({
            type: 'updateLastAssistant',
            text: full,
          });
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          webviewView.webview.postMessage({
            type: 'addMessage',
            role: 'assistant',
            text: `❌ Error: ${msg}`,
          });
        }
      }
    });
  }

  private _getHtml(webview: vscode.Webview): string {
    const csp = webview.cspSource;
    const nonce = Date.now().toString(36);

    return /* html */`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${csp} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OpenAmer Chat</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--vscode-font-family); font-size: 13px; color: var(--vscode-editor-foreground); background: var(--vscode-sideBar-background); display: flex; flex-direction: column; height: 100vh; }
    #messages { flex: 1; overflow-y: auto; padding: 8px; }
    .msg { margin-bottom: 8px; padding: 6px 8px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; }
    .msg.user { background: var(--vscode-textBlockQuote-background); border-left: 3px solid var(--vscode-textLink-foreground); }
    .msg.assistant { background: var(--vscode-editor-inactiveSelectionBackground); border-left: 3px solid var(--vscode-editorInfo-foreground); }
    #input-bar { display: flex; border-top: 1px solid var(--vscode-panel-border); padding: 6px; gap: 4px; }
    #input { flex: 1; resize: none; border: 1px solid var(--vscode-input-border); background: var(--vscode-input-background); color: var(--vscode-input-foreground); padding: 6px; border-radius: 2px; font-family: inherit; font-size: inherit; }
    #input:focus { outline: 1px solid var(--vscode-focusBorder); }
    #send { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 4px 12px; border-radius: 2px; cursor: pointer; }
    #send:hover { background: var(--vscode-button-hoverBackground); }
  </style>
</head>
<body>
  <div id="messages"></div>
  <div id="input-bar">
    <textarea id="input" rows="3" placeholder="Ask OpenAmer…"></textarea>
    <button id="send">Send</button>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const messages = document.getElementById('messages');
    const input = document.getElementById('input');
    const send = document.getElementById('send');

    function addMessage(role, text) {
      const div = document.createElement('div');
      div.className = 'msg ' + role;
      div.textContent = text;
      messages.appendChild(div);
      messages.scrollTop = messages.scrollHeight;
      return div;
    }

    function updateLastAssistant(text) {
      const els = messages.querySelectorAll('.msg.assistant');
      if (els.length) els[els.length - 1].textContent = text;
    }

    window.addEventListener('message', e => {
      const msg = e.data;
      if (msg.type === 'addMessage') addMessage(msg.role, msg.text);
      else if (msg.type === 'updateLastAssistant') updateLastAssistant(msg.text);
    });

    function sendMessage() {
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      vscode.postMessage({ type: 'chat', text });
    }

    input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    send.addEventListener('click', sendMessage);

    addMessage('assistant', '👋 Connected. Ask me anything about your code.');
  </script>
</body>
</html>`;
  }
}

/* ------------------------------------------------------------------ */
/*  Extension Entry Point                                              */
/* ------------------------------------------------------------------ */

let mcpClient: MCPClient | null = null;
let statusBarItem: vscode.StatusBarItem | null = null;

function getMCP(): MCPClient | null {
  return mcpClient;
}

function updateStatusBar(text: string, tooltip?: string): void {
  if (statusBarItem) {
    statusBarItem.text = text;
    if (tooltip) statusBarItem.tooltip = tooltip;
  }
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  // --- Status Bar ---
  statusBarItem = vscode.window.createStatusBarItem('openamer.status', vscode.StatusBarAlignment.Right, 100);
  statusBarItem.name = 'OpenAmer Connection Status';
  statusBarItem.text = '$(debug-disconnect) OpenAmer: disconnected';
  statusBarItem.tooltip = 'Click to connect to OpenAmer MCP server';
  statusBarItem.command = 'openamer.chat';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // --- MCP Client ---
  mcpClient = new MCPClient();
  mcpClient.onCloseCb = () => {
    updateStatusBar('$(debug-disconnect) OpenAmer: disconnected');
  };

  // Auto-connect
  connectMCP(context);

  // --- Chat Webview ---
  const provider = new ChatWebviewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(ChatWebviewProvider.viewType, provider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
  );

  // --- Commands ---

  // openamer.chat – focus the sidebar
  context.subscriptions.push(
    vscode.commands.registerCommand('openamer.chat', () => {
      vscode.commands.executeCommand('workbench.view.extension.openamer');
    }),
  );

  // openamer.explain – explain current file / selected file
  context.subscriptions.push(
    vscode.commands.registerCommand('openamer.explain', async (uri?: vscode.Uri) => {
      const fileUri = uri ?? vscode.window.activeTextEditor?.document.uri;
      if (!fileUri) {
        vscode.window.showErrorMessage('No file selected to explain.');
        return;
      }
      const doc = await vscode.workspace.openTextDocument(fileUri);
      const text = doc.getText();

      const mcp = getMCP();
      if (!mcp?.connected) {
        vscode.window.showErrorMessage('OpenAmer MCP server is not connected.');
        return;
      }

      updateStatusBar('$(sync~spin) OpenAmer: explaining…');
      try {
        await sendToMCPChat(mcp, `Explain this code:\n\n\`\`\`${doc.languageId}\n${text.slice(0, 8000)}\n\`\`\``);
        vscode.commands.executeCommand('workbench.view.extension.openamer');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`Explain failed: ${msg}`);
      } finally {
        updateStatusBar('$(check) OpenAmer: connected');
      }
    }),
  );

  // openamer.fix – fix selected text
  context.subscriptions.push(
    vscode.commands.registerCommand('openamer.fix', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showErrorMessage('No active editor.');
        return;
      }
      const selection = editor.selection;
      if (selection.isEmpty) {
        vscode.window.showErrorMessage('No text selected to fix.');
        return;
      }
      const text = editor.document.getText(selection);

      const mcp = getMCP();
      if (!mcp?.connected) {
        vscode.window.showErrorMessage('OpenAmer MCP server is not connected.');
        return;
      }

      updateStatusBar('$(sync~spin) OpenAmer: fixing…');
      try {
        await sendToMCPChat(mcp, `Fix this code:\n\n\`\`\`${editor.document.languageId}\n${text.slice(0, 8000)}\n\`\`\``);
        vscode.commands.executeCommand('workbench.view.extension.openamer');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`Fix failed: ${msg}`);
      } finally {
        updateStatusBar('$(check) OpenAmer: connected');
      }
    }),
  );
}

/** Attempt to connect to the MCP server, with retries. */
async function connectMCP(context: vscode.ExtensionContext, retries = 3): Promise<void> {
  const mcpPath = resolveMcpCommand();
  if (!mcpPath) {
    updateStatusBar('$(error) OpenAmer: mcp not found');
    vscode.window.showWarningMessage(
      'OpenAmer CLI not found on PATH. Install it or set the OPENAMER_PATH environment variable.',
    );
    return;
  }

  updateStatusBar('$(sync~spin) OpenAmer: connecting…');

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      await mcpClient!.connect(mcpPath, ['mcp']);
      updateStatusBar('$(check) OpenAmer: connected', 'Click to open chat');

      // Log available tools
      const tools = await mcpClient!.listTools();
      console.log(`[openamer] MCP connected. Tools available: ${tools.map(t => t.name).join(', ') || 'none'}`);

      return;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`[openamer] MCP connect attempt ${attempt + 1}/${retries} failed: ${msg}`);
      if (attempt < retries - 1) await sleep(1000);
    }
  }

  updateStatusBar('$(debug-disconnect) OpenAmer: disconnected');
}

/** Resolve the `openamer` binary to an absolute path. */
function resolveMcpCommand(): string | null {
  const envPath = process.env.OPENAMER_PATH;
  if (envPath) return envPath;

  const paths = (process.env.PATH ?? '').split(path.delimiter);
  for (const dir of paths) {
    try {
      const full = path.join(dir, 'openamer');
      if (process.platform === 'win32') {
        for (const ext of ['', '.cmd', '.exe', '.bat']) {
          try { cp.execSync(`where "${full}${ext}"`, { stdio: 'ignore' }); return full + ext; }
          catch { /* not here */ }
        }
      } else {
        try { cp.execSync(`command -v "${full}"`, { stdio: 'ignore' }); return full; }
        catch { /* not here */ }
      }
    } catch { /* skip */ }
  }

  // Fallback: try openamer on PATH directly
  return 'openamer';
}

/** Send a message to the MCP chat and show a notification. */
async function sendToMCPChat(mcp: MCPClient, text: string): Promise<void> {
  const full = await mcp.chat(text, () => {});
  const preview = full.slice(0, 200);
  vscode.window.showInformationMessage(`OpenAmer response: ${preview}${full.length > 200 ? '…' : ''}`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export function deactivate(): void {
  mcpClient?.disconnect();
  mcpClient = null;
}
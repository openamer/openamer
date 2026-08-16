<p align="center">
  <img src="assets/banner.png" alt="OpenAmer Agent" width="100%">
</p>

# OpenAmer Agent
<p align="center">
  <a href="https://github.com/openamer/openamer/">OpenAmer Agent</a> | <a href="https://github.com/openamer/openamer/">OpenAmer Desktop</a>
</p>
<p align="center">
  <a href="https://github.com/openamer/openamer/blob/main/website/docs/"><img src="https://img.shields.io/badge/Docs-openamer.GitHub.io-22D3EE?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/NousResearch"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/openamer/openamer/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/openamer/openamer/releases"><img src="https://img.shields.io/badge/Releases-OpenAmer-38BDF8?style=for-the-badge" alt="Releases"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
  <a href="README.ur-pk.md"><img src="https://img.shields.io/badge/Lang-اردو-green?style=for-the-badge" alt="اردو"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/Lang-Español-orange?style=for-the-badge" alt="Español"></a>
</p>

**The self-improving, self-learning AI agent.** It's the only agent with a built-in learning loop — it creates skills from experience, improves them during use, nudges itself to persist knowledge, searches its own past conversations, and builds a deepening model of who you are across sessions. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that costs nearly nothing when idle. It's not tied to your laptop — talk to it from Telegram while it works on a cloud VM.

Use any model you want — OpenRouter, OpenAI, your own endpoint, and [many others](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers). Switch with `openamer model` — no code changes, no lock-in.

<table>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Six terminal backends — local, Docker, SSH, Singularity, Modal, and Daytona. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

---

## Quick Install

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://github.com/openamer/openamer/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs OpenAmer without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux/macOS one-liner above works there too. Found a bug? Please [file issues](https://github.com/openamer/openamer/issues).

Run this in PowerShell:

```powershell
iex (irm https://github.com/openamer/openamer/install.ps1)
```

The installer handles everything: uv, Python 3.11, Node.js, ripgrep, ffmpeg, **and a portable Git Bash** (MinGit, unpacked to `%LOCALAPPDATA%\openamer\git` — no admin required, completely isolated from any system Git install). OpenAmer uses this bundled Git Bash to run shell commands.

If you already have Git installed, the installer detects it and uses that instead. Otherwise a ~45MB MinGit download is all you need — it won't touch or interfere with any system Git.

> **Android / Termux:** The tested manual path is documented in the [Termux guide](https://github.com/openamer/openamer/blob/main/website/docs/getting-started/termux). On Termux, OpenAmer installs a curated `.[termux]` extra because the full `.[all]` extra currently pulls Android-incompatible voice dependencies.
>
> **Windows:** Native Windows is fully supported — the PowerShell one-liner above installs everything. If you'd rather use WSL2, the Linux command works there too. Native Windows install lives under `%LOCALAPPDATA%\openamer`; WSL2 installs under `~/.openamer` as on Linux.

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
openamer              # start chatting!
```

### Troubleshooting

#### Windows Defender or antivirus flags `uv.exe` as malware

If your antivirus (Bitdefender, Windows Defender, etc.) quarantines `uv.exe` from the OpenAmer `bin` folder (`%LOCALAPPDATA%\openamer\bin\uv.exe`), this is a **false positive**. The file is Astral's `uv` — the Rust Python package manager OpenAmer bundles to manage its Python environment. ML-based antivirus engines commonly flag unsigned Rust binaries that download and install packages.

**To verify your copy is authentic:**

```powershell
# Install GitHub CLI if needed
winget install --id GitHub.cli

# Login to GitHub
gh auth login

# Run verification
$uv = "$env:LOCALAPPDATA\openamer\bin\uv.exe"
$ver = (& $uv --version).Split(' ')[1]
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$zip = "$env:TEMP\uv.zip"
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$ver/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip -UseBasicParsing
gh attestation verify $zip --repo astral-sh/uv
Expand-Archive $zip "$env:TEMP\uv_x" -Force
(Get-FileHash "$env:TEMP\uv_x\uv.exe").Hash -eq (Get-FileHash $uv).Hash
```

If attestation says "Verification succeeded" and the last line prints `True`, you're good.

**To whitelist OpenAmer:**
- **Windows Defender:** Run PowerShell as Admin → `Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\openamer\bin"`
- **Bitdefender:** Add an exception in the Bitdefender console (Protection > Antivirus > Settings > Manage Exceptions)
- Whitelist the **folder**, not the file hash — OpenAmer updates `uv` and the hash changes every version

For more context, see the upstream Astral reports: [astral-sh/uv#13553](https://github.com/astral-sh/uv/issues/13553), [astral-sh/uv#15011](https://github.com/astral-sh/uv/issues/15011), [astral-sh/uv#10079](https://github.com/astral-sh/uv/issues/10079).

---

## Getting Started

```bash
openamer              # Interactive CLI — start a conversation
openamer model        # Choose your LLM provider and model
openamer tools        # Configure which tools are enabled
openamer config set   # Set individual config values
openamer config get   # Print individual config values
openamer gateway      # Start the messaging gateway (Telegram, Discord, etc.)
openamer setup        # Run the full setup wizard (configures everything at once)
openamer claw migrate # Migrate from OpenClaw (if coming from OpenClaw)
openamer update       # Update to the latest version
openamer doctor       # Diagnose any issues
```

📖 **[Full documentation →](https://github.com/openamer/openamer/blob/main/website/docs/)**

---

## Bring your own keys

OpenAmer works with whatever provider you want — that's not changing. Configure each tool you use (model, web search, image generation, TTS, cloud browser) with whichever API keys you choose. The tools are wired per-backend, not all-or-nothing.

---

## CLI vs Messaging Quick Reference

OpenAmer has two entry points: start the terminal UI with `openamer`, or run the gateway and talk to it from Telegram, Discord, Slack, WhatsApp, Signal, or Email. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action                         | CLI                                           | Messaging platforms                                                              |
| ------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Start chatting                 | `openamer`                                      | Run `openamer gateway setup` + `openamer gateway start`, then send the bot a message |
| Start fresh conversation       | `/new` or `/reset`                            | `/new` or `/reset`                                                               |
| Change model                   | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| Set a personality              | `/personality [name]`                         | `/personality [name]`                                                            |
| Retry or undo the last turn    | `/retry`, `/undo`                             | `/retry`, `/undo`                                                                |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]`                                        |
| Browse skills                  | `/skills` or `/<skill-name>`                  | `/<skill-name>`                                                                  |
| Interrupt current work         | `Ctrl+C` or send a new message                | `/stop` or send a new message                                                    |
| Platform-specific status       | `/platforms`                                  | `/status`, `/sethome`                                                            |

For the full command lists, see the [CLI guide](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/cli) and the [Messaging Gateway guide](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[OpenAmer Docs](https://github.com/openamer/openamer/blob/main/website/docs/)**:

| Section                                                                                             | What's Covered                                             |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Quickstart](https://github.com/openamer/openamer/blob/main/website/docs/getting-started/quickstart)                 | Install → setup → first conversation in 2 minutes          |
| [CLI Usage](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/cli)                              | Commands, keybindings, personalities, sessions             |
| [Configuration](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/configuration)                | Config file, providers, models, all options                |
| [Messaging Gateway](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/messaging)                | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/security)                          | Command approval, DM pairing, container isolation          |
| [Tools & Toolsets](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/features/tools)            | 40+ tools, toolset system, terminal backends               |
| [Skills System](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/features/skills)              | Procedural memory, Skills Hub, creating skills             |
| [Memory](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/features/memory)                     | Persistent memory, user profiles, best practices           |
| [MCP Integration](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/features/mcp)               | Connect any MCP server for extended capabilities           |
| [Cron Scheduling](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/features/cron)              | Scheduled tasks with platform delivery                     |
| [Context Files](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/features/context-files)       | Project context that shapes every conversation             |
| [Architecture](https://github.com/openamer/openamer/blob/main/website/docs/developer-guide/architecture)             | Project structure, agent loop, key classes                 |
| [Contributing](https://github.com/openamer/openamer/blob/main/website/docs/developer-guide/contributing)             | Development setup, PR process, code style                  |
| [CLI Reference](https://github.com/openamer/openamer/blob/main/website/docs/reference/cli-commands)                  | All commands and flags                                     |
| [Environment Variables](https://github.com/openamer/openamer/blob/main/website/docs/reference/environment-variables) | Complete env var reference                                 |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, OpenAmer can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`openamer setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
openamer claw migrate              # Interactive migration (full preset)
openamer claw migrate --dry-run    # Preview what would be migrated
openamer claw migrate --preset user-data   # Migrate without secrets
openamer claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:

- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.openamer/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `openamer claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://github.com/openamer/openamer/blob/main/website/docs/developer-guide/contributing) for development setup, code style, and PR process.

Quick start for contributors — use the standard installer, then work from the
full git checkout it creates at `$OPENAMER_HOME/openamer-agent` (usually
`~/.openamer/openamer-agent`). This matches the layout used by `openamer update`, the
managed venv, lazy dependencies, gateway, and docs tooling.

```bash
curl -fsSL https://github.com/openamer/openamer/install.sh | bash
cd "${OPENAMER_HOME:-$HOME/.openamer}/openamer-agent"
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

Manual clone fallback (for throwaway clones/CI where you intentionally do not
want the managed install layout):

Create the venv outside the cloned source tree — a venv inside the directory
the agent operates from can be wiped by a relative-path command the agent runs
against its own checkout, destroying the running runtime mid-session.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv ~/.openamer/venvs/openamer-dev --python 3.11
source ~/.openamer/venvs/openamer-dev/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

---

## Community

- 💬 [Discord](https://discord.gg/NousResearch)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server for OpenAmer and other MCP hosts, with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [OpenAmerClaw](https://github.com/AaronWong1999/openamerclaw) — Community WeChat bridge: Run OpenAmer Agent and OpenClaw on the same WeChat account.

---

## License

MIT — see [LICENSE](LICENSE).

OpenAmer Agent.

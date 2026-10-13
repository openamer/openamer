# OpenAmer CLI Reference

Live sources when anything looks stale: `openamer --help`, `openamer <command> --help`,
https://github.com/openamer/openamer/blob/main/website/docs/reference/cli-commands

### Global Flags

```
openamer [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
openamer chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
openamer setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
openamer model                Interactive model/provider picker
openamer fallback [add|remove|list]  Fallback provider chain
openamer config [show|edit|get|set|unset|path|env-path|check|migrate]
openamer login / logout       OAuth sign-in / clear stored auth
openamer doctor [--fix]       Check dependencies and config
openamer status [--all]       Component status
```

### Tools & Skills

```
openamer tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

openamer skills list|browse|search QUERY|inspect ID
openamer skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
openamer skills config        Enable/disable skills per platform
openamer skills check|update|uninstall|publish PATH
openamer skills tap add REPO  Add a GitHub repo as a skill source
openamer bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
openamer mcp add NAME (--url or --command) | remove | list | test NAME
openamer mcp catalog | install NAME     Curated catalog install
openamer mcp configure NAME             Toggle tool selection
openamer mcp serve                      Run OpenAmer as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
openamer gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `openamer photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://github.com/openamer/openamer/blob/main/website/docs/user-guide/messaging/

### Sessions

```
openamer sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
openamer cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
openamer webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
openamer profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
openamer profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
openamer auth                 Interactive credential manager
openamer auth add [PROVIDER]  Add OAuth or API-key credential (openamer, openai-codex, qwen-oauth, …)
openamer auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
openamer desktop / gui        Native desktop app
openamer dashboard            Web admin panel + embedded chat (--stop / --status)
openamer proxy                OpenAI-compatible local proxy backed by an OAuth provider
openamer portal               Quick setup / sign in via your hosted provider
openamer kanban <verb>        Multi-agent work-queue board
openamer project              Named multi-folder workspaces
openamer skin list|use|set    Switch/tweak skins (see references/themes.md)
openamer pets <verb>          Pet mascots (see references/petdex.md)
openamer memory setup|status|off|reset   Memory provider
openamer secrets bitwarden|onepassword   External secret stores
openamer moa                  Mixture-of-Agents slots
openamer hooks / security / backup / import / checkpoints / console
openamer logs [-f] [errors]   View agent/error logs
openamer send                 One-off message through a gateway platform
openamer pairing / plugins / insights / journey / computer-use
openamer acp                  ACP server (IDE integration)
openamer completion bash|zsh|fish
openamer update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `openamer photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `openamer config edit` · [Configuration docs](https://github.com/openamer/openamer/blob/main/website/docs/user-guide/configuration) |
| Tools / toolsets | `openamer tools list` · [Tools reference](https://github.com/openamer/openamer/blob/main/website/docs/reference/tools-reference) |
| Skills catalog | `openamer skills browse` · [Skills catalog](https://github.com/openamer/openamer/blob/main/website/docs/reference/skills-catalog) |
| Provider setup | `openamer model` · [Providers guide](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers) |
| Env variables | `openamer config env-path` · [Env vars reference](https://github.com/openamer/openamer/blob/main/website/docs/reference/environment-variables) |
| Gateway logs | `~/.openamer/logs/gateway.log` (or `openamer logs`) |
| Sessions | `openamer sessions browse` (reads state.db) |

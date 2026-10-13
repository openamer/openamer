# agent-browser Headless Fallback — Windows

When no Chromium desktop app has a visible window (no Brave, no Chrome, Edge
is headless), use agent-browser's headless mode via `browser_navigate`.

## Install

```bash
npm install -g agent-browser
npm approve-scripts agent-browser  # allow the postinstall script
agent-browser install              # downloads Chrome 152 for testing
```

This installs Chrome under `~\.agent-browser\browsers\chrome-152.0.7977.54`.

## Usage (headless, no visible window)

```python
# Works without any visible browser window
browser_navigate(url="https://github.com/settings/tokens")
browser_snapshot()  # full AX tree returned
browser_click(ref="@e3")
browser_type(ref="@e3", text="username")
```

## Limitations

- **Bot detection**: Shows "Running WITHOUT residential proxies" warning on
  GitHub login pages. For anonymous browsing (docs, public repos) it works fine.
- **No screenshots**: agent-browser returns the AX tree only — no visual
  rendering. Use `computer_use` with a desktop Chromium for visual work.
- **Stealth features**: Only `local` mode available without Browserbase plan.

## When to Use

| Situation | Tool |
|-----------|------|
| Need to click a web page, no browser visible | `browser_navigate` |
| Need to fill forms, read page content | `browser_navigate` + `browser_snapshot` |
| Need visual verification or screenshots | `computer_use` with desktop Brave |
| GitHub login or bot-detected pages | Prefer `computer_use` with desktop Brave |
| No desktop browser installed at all | `browser_navigate` (agent-browser)
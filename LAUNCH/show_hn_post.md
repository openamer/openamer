# 🚀 Show HN: OpenAmer — Self-improving AI agent with Background Computer-Use

**Titel (max 80 Zeichen):**
Show HN: OpenAmer – self-improving AI agent with background computer-use

**Body:**

Hi HN!

I built **OpenAmer** – an open-source AI agent that doesn't just chat. It *acts* on your computer, in the background, without stealing your mouse.

## Why I built it

AI agents are all talk. They reply, they plan, but they can't *do* anything on your machine. OpenAmer changes that: it drives the actual desktop (click, type, scroll) **in the background** — you keep working, it works alongside you. No VM, no browser-only sandbox.

## What it does

- 🖥 **Background Computer-Use** — drives your real desktop without focus steal (cua-driver)
- 🕸 **A2A Swarm** — spawns worker agents that parallelize tasks (master/worker, debate mode)
- 🧠 **Vector Memory** — persistent memory across sessions, searchable
- 🧩 **Plugin + Skill system** — 250+ skills included, extend with plugins
- 🎙 **Voice** — TTS/STT interface
- 🌐 **Own Browser** — CDP-controlled Chromium at :9333, no Cloudflare blocks
- ✅ **100/100 code quality score** — 203+ tests passing, Windows-native

## The interesting part

Most "computer use" agents need a VM or run headless. OpenAmer runs **on your Windows machine**, controls the real screen in the background, and you can watch it work — or just let it finish and check results.

It's a fork of the hermes-agent architecture, heavily extended.

## Tech

- Python 3.11, Windows-native
- Electron-based custom browser (CDP :9333)
- 99+ tools, 250+ skills
- MIT license

**Repo:** https://github.com/openamer/openamer
**Product Hunt:** https://www.producthunt.com/posts/openamer

Happy to answer questions! What would you automate first?

---

**Optimierung für HN:**
- Posten: Dienstag-Donnerstag, 9-11 Uhr US-Ostküste (14-16 Uhr deutscher Zeit)
- Der Titel ist ehrlich und konkret — kein Clickbait
- "Show HN:" Präfix ist Pflicht
- Body: Problem → Lösung → Tech → Link, kein Buzzword-Spam

**Warum dieser Post funktioniert:**
1. "Background Computer-Use" ist ein differenzierendes Feature — die meisten kennen nur VM-basiert
2. Konkrete Zahlen (203+ Tests, 99+ Tools) = Glaubwürdigkeit
3. "What would you automate first?" = Engagement-Frage für Kommentare
4. Eigenes Browser-Feature = Gesprächsthema

**Zeitpunkt-Hinweis:** HN-Algorithmus bevorzugt frühe Upvotes (erste 2 Stunden). Bester Zeitpunkt: Dienstag/Mittwoch 9-10 Uhr ET.

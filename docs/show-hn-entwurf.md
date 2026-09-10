# Show HN: OpenAmer — self-improving AI agent, runs 24/7 at 0 EUR (<1 kWh/day)

## Title (max 80 chars)
Show HN: OpenAmer — a self-improving agent that runs on your laptop for free

## Text (first comment)
Hi HN! I've spent the last years building OpenAmer, an open-source AI agent
that runs persistently on your own hardware — no VM, no hosted tier, no
phone-home.

What makes it different:

- **Built-in learning loop**: it creates skills from experience, improves
  them during use, and evolves its skill population genetically (Darwin
  engine: mutation + crossover + fitness-based selection, 243 skills).
- **Continuity of self**: a world-model of cause→effect edges with real
  embeddings, nightly memory consolidation (REM replay + deep sleep
  phases), and a nightly diary written in first person about what
  happened, what was learned, what was decided.
- **Workflow Immune System**: register a UI workflow once (selectors only);
  when a site redesigns overnight, it detects the drift, re-finds the
  element, patches itself, and retries — with healing-strategy
  competitions (epsilon-greedy over tokens/text/role/classes).
- **Runs for nearly nothing**: local 2B model for tool orchestration,
  free-cloud reasoning chain for deep distillation. 0 €/day, <1 kWh/day.
- **Yours**: state, memory, credentials on your hardware. Windows-native,
  no WSL required.

It's early (single-digit stars) but every superpower is shipped and
verified with test evidence. I'm here to answer questions.

Repo: https://github.com/openamer/openamer
Landing: https://openamer.github.io/openamer/
Docs: https://github.com/openamer/openamer/tree/main/website/docs

Subreddit: r/LocalLLaMA
Title: I built an AI agent whose skills evolve through natural selection — runs on local Ollama, zero API cost

I've been working on OpenAmer, an agent framework where skills literally evolve through Darwinian selection. Here's what makes it different:

**Skills fight for survival.** Every skill has a fitness score based on real usage. Weak skills get consumed by stronger ones (predation). New skills are born through mutation and speciation. The population self-regulates — no human curation.

**The workers are LLM agents.** Each one has a personality, uses local Ollama (gemma3:4b) for reasoning, and decides its own actions: MUTATE, PREDATE, CHALLENGE, EXPLORE, or REST. At zero API cost.

**Everything is evidence-based.** Skills compete in real duels decided by exit codes, not benchmarks. Failed mutations are archived, never deleted.

**There's a grid.** Machines push their evolved genomes to github.com/openamer/darwin-grid and duel each other's skills cross-machine.

**It's fully autonomous.** A cron runs every 30 minutes: the swarm introspects itself, detects gaps, creates tasks from those gaps, auctions them, and executes approved actions.

Demo video: https://www.youtube.com/watch?v=SJ2ODpyn234
GitHub: https://github.com/openamer/openamer
143 tests passing. 25 phases. Would love feedback.
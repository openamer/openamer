# Verifying this health-check reference

After a cron health sweep where you used `mini-openamer-cron-health-check.md`,
verify by re-running the KEY number checks and comparing them to the reference:

```bash
# Episodic memory total (should match what you reported)
wc -l memory/longterm_episodes.jsonl

# World model total
wc -l memory/world_model.jsonl

# Brain training data
cat scripts/training/.brain_count
cat scripts/training/.online_marker
cat scripts/training/.last_retrain

# Router state freshness
cat scripts/training/.router_state.json | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('last_refresh','?'), len(d.get('free_chain', [])))"
```

The identity.md was also updated — confirm with:
```bash
grep -E '^\- [0-9]+' memory/self_model/identity.md
```
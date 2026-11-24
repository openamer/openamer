# Competitor Learning Patterns — Evolution of Internet Learner (2026-11-22)

## User Criticism
> "amateurish — same approach every time, no new question generation"

The current learner rotates through fixed source types (A-F) with static seeds + 8-angle rotation.
This produces repetitive queries once all (seed × angle) combinations are exhausted.

## Competitor Analysis Needed

### 1. AutoGPT / AgentGPT
- **Learning loop**: Task decomposition → web research → synthesis → memory update
- **Question generation**: LLM-driven sub-question decomposition from high-level goals
- **Novelty**: Each task spawns unique research branches

### 2. OpenHands (formerly OpenDevin)
- **Learning loop**: Observe → Plan → Act → Reflect
- **Question generation**: Reflection phase generates new hypotheses to test
- **Novelty**: Self-reflection drives new inquiry directions

### 3. Devin AI
- **Learning loop**: Continuous integration of external knowledge via browsing
- **Question generation**: Dynamic based on current task context and gaps
- **Novelty**: Task-aware research, not fixed rotation

### 4. LangChain / LangGraph Agents
- **Learning loop**: Tool-use → observation → reasoning → memory
- **Question generation**: Chain-of-thought prompting for research planning
- **Novelty**: Structured reasoning traces guide next questions

## Required Evolution for OpenAmer Internet Learner

### Phase 1: Dynamic Question Generation
- Replace static seed list with LLM-synthesized questions based on:
  - Current world model gaps (query `world_model.jsonl` for low-confidence areas)
  - Recent conversation topics (episodic memory)
  - Failed tool calls / knowledge gaps detected during tasks

### Phase 2: Competitor-Inspired Research Loop
```
1. IDENTIFY GAP → 2. PLAN RESEARCH → 3. EXECUTE → 4. SYNTHESIZE → 5. UPDATE WORLD MODEL → 6. GENERATE NEW QUESTIONS
```
- Each cycle produces 1-3 novel follow-up questions
- Questions stored in novelty ledger with embeddings for similarity detection

### Phase 3: Cross-Domain Synthesis
- Current: 6 isolated source types (A-F)
- Target: Cross-pollinate insights (e.g., competitor changelog + paper → new technique)
- Use Mini-OpenAmer to synthesize connections

## Implementation Sketch
```python
def generate_novel_questions(context: dict) -> list[str]:
    """LLM-driven question generation based on knowledge gaps."""
    prompt = f"""
    Current world model gaps: {context['gaps']}
    Recent tasks: {context['recent_tasks']}
    Failed tool calls: {context['failures']}
    
    Generate 3 specific, narrow, technical SEARCH QUERIES that would
    fill these gaps. Prefer concrete tools, libraries, versions, techniques.
    Output ONLY the queries, one per line.
    """
    # Call mini_backend or cloud model
    return parse_queries(response)
```

## Files to Modify
- `scripts/training/internet_learner.py` — core cycle logic
- Add `generate_novel_questions()` function
- Replace static seed rotation with dynamic generation
- Keep novelty ledger (`_SEEN_Q`) for deduplication

## Success Metrics
- Zero "rejected, not trained (duplicate)" cycles after warmup
- Each cycle produces ≥1 genuinely new insight (measured by buffer growth)
- Questions cover domains not in fixed A-F rotation
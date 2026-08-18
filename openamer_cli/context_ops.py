"""Deterministic context- and tool-result management helpers.

These are pure, side-effect-free functions: no LLM calls, no I/O. They exist so
a long agent run stays focused and within the provider's context window without
flooding it with huge tool dumps. Because they are pure, they are trivially
unit-testable and safe to call anywhere (conversation assembly, session recap,
export) without touching the fragile agent loop.

The heuristic token estimate is deliberately model-free: it uses a rough
~4 chars/token rule, which is a reasonable approximation for prose and JSON
alike and is deterministic (the same string always maps to the same count).
Callers that know the exact provider budget can pass an explicit budget.
"""

from __future__ import annotations

from typing import Optional

# Rough chars-per-token heuristic (deterministic, model-free).
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Return a deterministic token estimate (``ceil(len/chars_per_token)``)."""
    if not text:
        return 0
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


def _head(text: str, budget_chars: int) -> str:
    """Keep the start of *text* plus a clear truncation marker."""
    if len(text) <= budget_chars:
        return text
    marker = "\n… [output truncated; N chars remaining]"
    keep = max(0, budget_chars - len(marker))
    return text[:keep] + marker


def _tail(text: str, budget_chars: int) -> str:
    """Keep the end of *text* plus a clear truncation marker.

    Many tool dumps (build logs, diffs, test output) carry the interesting
    result at the END (exit status, summary line, final error). Keeping the
    tail preserves that signal.
    """
    if len(text) <= budget_chars:
        return text
    marker = "[output truncated; N chars…]\n"
    keep = max(0, budget_chars - len(marker))
    return marker + text[-keep:]


def prune_tool_result(
    content: str,
    *,
    budget_tokens: int,
    max_chars: Optional[int] = None,
    prefer: str = "tail",
) -> str:
    """Return a shortened copy of a tool result bounded by *budget_tokens*.

    Model-free and lossy by design — the goal is to keep the highest-signal
    part of a large tool output inside the context window, not to preserve
    every byte.

    Parameters
    ----------
    content
        The raw tool output text.
    budget_tokens
        Upper bound on the returned output's token estimate.
    max_chars
        Optional hard char cap applied first (safety net against absurdly
        long single lines). Defaults to ``budget_tokens * chars_per_token``.
    prefer
        ``"tail"`` (default): keep the end of the output (exit status,
        summary, final error). ``"head"``: keep the start (headers, first
        lines). ``"head+tail"``: keep both a small head and a small tail
        around a truncation marker (best for structured listings).

    Returns
    -------
    The pruned string, never longer than the budget (when the input is
    smaller it is returned unchanged).
    """
    if not content:
        return content

    char_budget = budget_tokens * _CHARS_PER_TOKEN
    if max_chars is not None:
        char_budget = min(char_budget, max_chars)

    if len(content) <= char_budget:
        return content

    if prefer == "head":
        return _head(content, char_budget)
    if prefer == "tail":
        return _tail(content, char_budget)
    # head+tail: keep ~40% head / ~60% tail with a marker between. Reserve
    # marker overhead first so the total (head+marker+tail) stays within the
    # char budget — otherwise the marker itself can blow past budget_tokens.
    marker = "\n… [middle output truncated]\n"
    usable = max(0, char_budget - len(marker))
    head_chars = int(usable * 0.4)
    tail_chars = usable - head_chars
    head = content[:head_chars].rstrip()
    tail = content[-tail_chars:].lstrip()
    return head + marker + tail


def compact_messages(
    messages: list[dict],
    *,
    budget_tokens: int,
    per_message_budget_tokens: Optional[int] = None,
) -> list[dict]:
    """Return a context-bounded copy of a message list.

    Lightweight, deterministic compaction for long sessions: oversize tool
    messages are pruned (model-free) and the oldest low-signal assistant/user
    turns are summarized to a one-line placeholder, newest turns preserved
    intact.

    Parameters
    ----------
    messages
        Conversation messages, each a dict with at least ``content``
        (str) and ``role`` (str). Unknown keys are preserved untouched.
    budget_tokens
        Total budget for the returned list's token estimate.
    per_message_budget_tokens
        Optional per-message cap applied to the newest messages before the
        whole-list budget pass.

    Returns
    -------
    A new list of dicts (never mutates the input). If the input is already
    within budget, it is returned unchanged (same objects).
    """
    if not messages:
        return messages

    per_message_budget_tokens = per_message_budget_tokens or budget_tokens
    out: list[dict] = []

    # 1) Per-message cap (protects against one absurd tool dump even when the
    #    whole session is small). Never prune the newest USER message — it is
    #    the user's current prompt and must reach the model intact. A newest
    #    message that is a tool/assistant result (no pending prompt) may still
    #    be pruned so one giant dump can't blow the window.
    for idx, msg in enumerate(messages):
        content = msg.get("content") or ""
        is_newest_user = (
            idx == len(messages) - 1 and msg.get("role") == "user"
        )
        if (
            not is_newest_user
            and isinstance(content, str)
            and estimate_tokens(content) > per_message_budget_tokens
        ):
            item = dict(msg)
            item["content"] = prune_tool_result(
                content, budget_tokens=per_message_budget_tokens, prefer="tail"
            )
            out.append(item)
        else:
            out.append(msg)

    total = sum(
        estimate_tokens(m.get("content") or "")
        for m in out
        if isinstance(m.get("content"), str)
    )
    if total <= budget_tokens:
        return out

    # 2) Whole-list pass: collapse the OLDEST non-newest low-signal turns to a
    #    placeholder until under budget. Never touch the newest message (it is
    #    the user's current prompt).
    placeholder = "[earlier context compacted]"
    newest_idx = len(out) - 1
    # Compaction score: prefer compacting low-signal, non-tool, non-user-newest.
    def _score(i: int, msg: dict) -> int:
        content = msg.get("content") or ""
        if not isinstance(content, str):
            return 10_000_000
        role = msg.get("role", "")
        # Keep tool results that are already small; compact big ones first.
        size = estimate_tokens(content)
        if role == "tool":
            return size + 0
        if role == "assistant":
            return size + 1_000
        if role == "user" and i != newest_idx:
            return size + 2_000
        return 10_000_000  # newest user — never compact

    while total > budget_tokens:
        # Pick the oldest compactable message.
        candidates = [
            (i, m) for i, m in enumerate(out)
            if i != newest_idx and isinstance(m.get("content"), str)
        ]
        if not candidates:
            break
        i, _m = min(candidates, key=lambda pair: _score(pair[0], pair[1]))
        item = dict(out[i])
        # One collapse may not be enough for a giant tool dump; shrink until
        # it no longer helps or we've already placed a placeholder.
        content = item.get("content") or ""
        if estimate_tokens(content) <= len(placeholder) // _CHARS_PER_TOKEN + 1:
            break
        total -= estimate_tokens(content)
        item["content"] = placeholder
        total += estimate_tokens(placeholder)
        out[i] = item

    return out

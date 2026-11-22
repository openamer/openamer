"""EpisodeRecall memory plugin — MemoryProvider interface.

Prefetches relevant episodes from the local episodic store
(memory/longterm_episodes.jsonl) before each turn and injects them as
turn context.  Local-only, no network, no external deps beyond the
bundled scripts/embeddings.py.

Privacy canaries (enforced in initialize() and prefetch()):
  * profile-local — reads only OPENAMER_HOME/memory/longterm_episodes.jsonl,
    never another profile's store.
  * unknown-identity-deny — prefetch() returns "" when no user_id is known.
  * shared-channel-deny — prefetch() returns "" in non-private chats
    (chat_type != "private").
  * worker/cron-deny — prefetch() returns "" when agent_context != "primary".

Config via environment variables:
  EPISODE_RECALL_MAX_HITS     — max episodes injected per turn (default 5)
  EPISODE_RECALL_ENABLED      — "0" disables the provider entirely (default "1")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

HOME = Path(
    os.environ.get("OPENAMER_HOME")
    or (Path.home() / "AppData" / "Local" / "openamer-laptop")
)
EPISODES = HOME / "memory" / "longterm_episodes.jsonl"

sys.path.insert(0, str(HOME / "scripts"))
try:
    from embeddings import embed, cosine  # noqa: E402
except Exception:  # pragma: no cover - fallback keeps recall usable
    embed = None
    cosine = None


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Optional[str], default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


class EpisodeRecallProvider(MemoryProvider):
    """Local episodic recall provider."""

    def __init__(self) -> None:
        self._name = "episode_recall"
        self._enabled = _parse_bool(os.environ.get("EPISODE_RECALL_ENABLED"), True)
        self._max_hits = _parse_int(os.environ.get("EPISODE_RECALL_MAX_HITS"), 5)
        self._session_id = ""
        self._user_id = ""
        self._platform = "cli"
        self._agent_context = "primary"
        self._chat_type = ""
        self._initialized = False

    # -- MemoryProvider ABC --------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        """True when enabled, the store exists, and embeddings load."""
        if not self._enabled:
            return False
        if not EPISODES.exists():
            return False
        if embed is None or cosine is None:
            return False
        return True

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = session_id
        self._user_id = kwargs.get("user_id", "") or ""
        self._platform = kwargs.get("platform", "cli") or "cli"
        self._agent_context = kwargs.get("agent_context", "primary") or "primary"
        self._chat_type = kwargs.get("chat_type", "") or ""
        self._initialized = True
        logger.info(
            "EpisodeRecallProvider initialized: session=%s user=%s platform=%s "
            "context=%s chat_type=%s store=%s",
            session_id, self._user_id or "<none>", self._platform,
            self._agent_context, self._chat_type or "<none>", EPISODES,
        )

    def system_prompt_block(self) -> str:
        """Static instruction for the system prompt."""
        return (
            "## Episode recall (local, private)\n"
            "Relevant episodes from your own episodic store are prepended to "
            "this turn when they match your query.  They are private memory — "
            "use them as context, never quote them verbatim to the user.\n"
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall relevant episodes before the turn.

        Canaries:
          * unknown-identity-deny — no user_id → ""
          * shared-channel-deny — non-private chat → ""
          * worker/cron-deny — agent_context != "primary" → ""
        """
        if not self._initialized or not self._enabled:
            return ""

        # unknown-identity-deny
        if not self._user_id:
            logger.debug("EpisodeRecall prefetch skipped: unknown identity (no user_id)")
            return ""

        # shared-channel-deny
        if self._chat_type and self._chat_type != "private":
            logger.debug(
                "EpisodeRecall prefetch skipped: shared channel chat_type=%s",
                self._chat_type,
            )
            return ""

        # worker/cron-deny
        if self._agent_context != "primary":
            logger.debug(
                "EpisodeRecall prefetch skipped: non-primary context=%s",
                self._agent_context,
            )
            return ""

        if not query or not query.strip():
            return ""

        try:
            from episode_recall import rank as _rank  # noqa: E402

            rows = self._load_episodes_local()
            if not rows:
                return ""
            hits = _rank(query, rows, self._max_hits)
            if not hits:
                return ""
            return _render_recall(query, hits)
        except Exception as exc:  # pragma: no cover - never break a turn
            logger.warning("EpisodeRecall prefetch failed: %s", exc)
            return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """No-op — recall is synchronous and cheap enough to run inline."""
        return None

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Episodes are written by the built-in memory tool; nothing to sync."""
        return None

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Context-only provider — no tools exposed."""
        return []

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        raise NotImplementedError(
            f"Provider {self.name} does not handle tool {tool_name}"
        )

    def shutdown(self) -> None:
        self._initialized = False

    # -- Optional hooks ------------------------------------------------------

    def on_turn_start(self, turn_number: int, message: str, **kwargs: Any) -> None:
        """No-op — recall runs in prefetch()."""
        return None

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """No-op — local store, nothing to flush."""
        return None

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes? No — local episodic store is append-only
        via the training loop, not via the memory tool.  Intentional no-op."""
        return None

    # -- internal ------------------------------------------------------------

    def _load_episodes_local(self) -> List[dict]:
        """Load episodes with profile-local scoping."""
        if not EPISODES.exists():
            return []
        rows: List[dict] = []
        with EPISODES.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("text") and row.get("embedding"):
                    rows.append(row)
        return rows


def _render_recall(query: str, hits: List[dict]) -> str:
    lines = [f"# Episode recall for: {query[:160]}", ""]
    for i, hit in enumerate(hits, 1):
        lines.append(
            f"{i}. [{hit.get('ts', '')[:16]}] (sim {hit.get('sim', 0):.2f}) "
            f"{hit.get('text', '')[:400]}"
        )
    return "\n".join(lines) + "\n"


# Plugin register() entry point (discovered by plugins.memory loader)
def register(ctx: Any) -> None:
    try:
        ctx.register_memory_provider(EpisodeRecallProvider())
    except AttributeError:
        # Older plugin contexts without register_memory_provider — the
        # loader falls back to scanning for MemoryProvider subclasses.
        pass


if __name__ == "__main__":  # pragma: no cover - manual smoke test only
    p = EpisodeRecallProvider()
    print("available:", p.is_available())
    print("store:", EPISODES)

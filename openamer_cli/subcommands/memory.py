"""``openamer memory`` subcommand parser.

Extracted from ``openamer_cli/main.py:main()`` (god-file Phase 2 follow-up).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_memory_parser(subparsers, *, cmd_memory: Callable) -> None:
    """Attach the ``memory`` subcommand to ``subparsers``."""
    memory_parser = subparsers.add_parser(
        "memory",
        help="Configure external memory provider + vector memory store",
        description=(
            "Set up and manage external memory provider plugins.\n\n"
            "Available providers: honcho, openviking, mem0, hindsight,\n"
            "holographic, retaindb, byterover.\n\n"
            "Only one external provider can be active at a time.\n"
            "Built-in memory (MEMORY.md/USER.md) is always active.\n\n"
            "Vector subcommands provide unlimited semantic memory with\n"
            "TF-IDF cosine-similarity search."
        ),
    )
    memory_sub = memory_parser.add_subparsers(dest="memory_command")
    _setup_parser = memory_sub.add_parser(
        "setup", help="Interactive provider selection and configuration"
    )
    _setup_parser.add_argument(
        "provider",
        nargs="?",
        default=None,
        help="Provider to configure directly (e.g. honcho), skipping the picker",
    )
    memory_sub.add_parser("status", help="Show current memory provider config")
    memory_sub.add_parser("off", help="Disable external provider (built-in only)")
    _reset_parser = memory_sub.add_parser(
        "reset",
        help="Erase all built-in memory (MEMORY.md and USER.md)",
    )
    _reset_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    _reset_parser.add_argument(
        "--target",
        choices=["all", "memory", "user"],
        default="all",
        help="Which store to reset: 'all' (default), 'memory', or 'user'",
    )

    # Vector memory subcommand group
    _vector_parser = memory_sub.add_parser(
        "vector",
        help="Vector memory store — unlimited semantic memory",
        description="Unlimited semantic memory with TF-IDF cosine-similarity search.  Store and retrieve memories beyond the 2200-char built-in limit.",
    )
    _vector_sub = _vector_parser.add_subparsers(dest="memory_vector_command")

    _vec_store = _vector_sub.add_parser("store", help="Store a memory entry")
    _vec_store.add_argument("key", help="Memory key/identifier")
    _vec_store.add_argument("content", help="Memory content text")

    _vec_search = _vector_sub.add_parser("search", help="Search memory entries")
    _vec_search.add_argument("query", help="Search query")
    _vec_search.add_argument("--top-k", type=int, default=5, help="Number of results (default: 5)")

    _vector_sub.add_parser("stats", help="Show vector store statistics")
    _vector_sub.add_parser("list", help="List all memory entries")

    _vec_compress = _vector_sub.add_parser("compress", help="Compress/compact the store")
    _vec_compress.add_argument("--max-entries", type=int, default=1000, help="Max entries after compression (default: 1000)")

    memory_parser.set_defaults(func=cmd_memory)

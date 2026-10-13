"""``openamer rag`` subcommand parser.

Provides RAG pipeline subcommands.
"""

from __future__ import annotations

from typing import Callable


def build_rag_parser(subparsers, *, cmd_rag: Callable) -> None:
    """Attach the ``rag`` subcommand to ``subparsers``."""
    rag_parser = subparsers.add_parser(
        "rag",
        help="RAG pipeline — ingest documents and query",
        description="Retrieval-Augmented Generation pipeline. Ingest documents and query them.",
    )
    rag_sub = rag_parser.add_subparsers(dest="rag_action")

    # rag ingest
    ingest_parser = rag_sub.add_parser(
        "ingest",
        help="Ingest a file or directory into the RAG index",
    )
    ingest_parser.add_argument(
        "path",
        help="File or directory path to ingest",
    )
    ingest_parser.add_argument(
        "--strategy",
        "-s",
        choices=["fixed_size", "paragraph", "recursive"],
        default="recursive",
        help="Chunking strategy (default: recursive)",
    )
    ingest_parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Max chunk size in characters (default: 500)",
    )
    ingest_parser.add_argument(
        "--index-name",
        default="default",
        help="Name for the saved index (default: default)",
    )

    # rag query
    query_parser = rag_sub.add_parser(
        "query",
        help="Query the RAG index",
    )
    query_parser.add_argument(
        "query",
        help="The question or search query",
    )
    query_parser.add_argument(
        "--index-name",
        default="default",
        help="Name of the saved index to query (default: default)",
    )
    query_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of relevant chunks to retrieve (default: 5)",
    )

    # rag info
    info_parser = rag_sub.add_parser(
        "info",
        help="Show RAG pipeline statistics",
    )

    rag_parser.set_defaults(func=cmd_rag)
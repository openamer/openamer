"""
CLI handlers for Plugin Framework, Evaluation, and RAG Pipeline.

These are the cmd_* functions that implement ``openamer plugins``,
``openamer eval``, and ``openamer rag`` CLI commands.

Import and wire them into ``main.py:main()``::

    from openamer_cli.subcommands.eval import build_eval_parser
    from openamer_cli.subcommands.rag import build_rag_parser
    from openamer_cli.cli_handlers import cmd_eval, cmd_rag

    build_eval_parser(subparsers, cmd_eval=cmd_eval)
    build_rag_parser(subparsers, cmd_rag=cmd_rag)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from openamer_cli.evaluation import (
    BenchmarkRun,
    BenchmarkSuite,
    TestCase,
    compare_runs,
    get_leaderboard,
    print_leaderboard,
)
from openamer_cli.plugin_framework import (
    PluginHost,
    PluginRegistry,
)
from openamer_cli.rag_pipeline import (
    ChunkingStrategy,
    RagPipeline,
)


# ── Plugin Framework CLI ───────────────────────────────────────────────────────


def cmd_plugins_framework(args: Any) -> None:
    """Handle ``openamer plugins list|install|reload``."""
    host = _get_plugin_host()

    action = getattr(args, "plugins_framework_action", None) or "list"

    if action == "list":
        plugins = host.registry.list_plugins(include_disabled=getattr(args, "all", True))
        if not plugins:
            print("No plugins registered.")
            return
        print(f"{'Name':<25} {'State':<12} {'Version'}")
        print("-" * 50)
        for name, state, version in plugins:
            print(f"{name:<25} {state.value:<12} {version}")

    elif action == "install":
        path_str = getattr(args, "path", "")
        if not path_str:
            print("Error: path argument is required.", file=sys.stderr)
            sys.exit(1)
        source = Path(path_str).resolve()
        if not source.exists():
            print(f"Error: path does not exist: {source}", file=sys.stderr)
            sys.exit(1)
        name = host.install(source)
        if name:
            print(f"Plugin '{name}' installed successfully.")
        else:
            print("Failed to install plugin.", file=sys.stderr)
            sys.exit(1)

    elif action == "reload":
        name = getattr(args, "name", None)
        count = host.reload(name=name)
        if count > 0:
            label = name or "all plugins"
            print(f"Reloaded {count} plugin(s): {label}")
        else:
            print(f"No plugins reloaded (name: {name!r})", file=sys.stderr)

    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


# ── Evaluation CLI ────────────────────────────────────────────────────────────


def _make_model_fn(model_name: str = "") -> Optional:
    """Attempt to create a model function from available providers.

    Returns None if no model can be reached (the suite will fail gracefully).
    """
    try:
        # Try the OpenAmer model infrastructure
        from openamer_cli.models import simple_send_prompt
        def model_fn(prompt: str) -> str:
            return simple_send_prompt(prompt, model=model_name or None)
        return model_fn
    except ImportError:
        return None


def cmd_eval(args: Any) -> None:
    """Handle ``openamer eval run|compare|leaderboard``."""
    action = getattr(args, "eval_action", None)

    if action == "run":
        suite_ref = args.suite
        suite_path = Path(suite_ref)

        if suite_path.is_file():
            suite = BenchmarkSuite.from_file(suite_path)
        else:
            suite = BenchmarkSuite(name=suite_ref)

        if not suite.test_cases:
            print(f"Suite '{suite.name}' has no test cases.")
            print("To define cases, create a JSON/YAML file or add cases programmatically.")
            sys.exit(1)

        model_fn = _make_model_fn(model_name=getattr(args, "model", ""))
        run = suite.run(model=getattr(args, "model", suite_ref), model_fn=model_fn)
        path = run.save()

        print(f"\nBenchmark: {run.name}")
        print(f"Model:     {run.model or '(none)'}")
        print(f"Date:      {run.date}")
        print(f"Total:     {run.total}")
        print(f"Passed:    {run.passed}")
        print(f"Pass rate: {run.pass_rate:.1f}%")
        print(f"Avg latency: {run.avg_latency:.1f}ms")
        print(f"Saved to:  {path}")

        if run.results:
            print("\nResults:")
            for r in run.results:
                status = "PASS" if r.passed else "FAIL"
                print(f"  [{status}] {r.test_name} ({r.latency_ms:.0f}ms) — {r.reason}")

    elif action == "compare":
        run1_path = Path(args.run1)
        run2_path = Path(args.run2)

        if not run1_path.is_file():
            print(f"Error: run file not found: {run1_path}", file=sys.stderr)
            sys.exit(1)
        if not run2_path.is_file():
            print(f"Error: run file not found: {run2_path}", file=sys.stderr)
            sys.exit(1)

        run1 = BenchmarkRun.load(run1_path)
        run2 = BenchmarkRun.load(run2_path)
        comparison = compare_runs(run1, run2)

        print("\nComparison:")
        print(f"  Run 1: {comparison['run1']['name']} ({comparison['run1']['model']}) "
              f"— {comparison['run1']['pass_rate']:.1f}% pass @ {comparison['run1']['avg_latency_ms']:.1f}ms")
        print(f"  Run 2: {comparison['run2']['name']} ({comparison['run2']['model']}) "
              f"— {comparison['run2']['pass_rate']:.1f}% pass @ {comparison['run2']['avg_latency_ms']:.1f}ms")
        print(f"  Pass rate diff: {comparison['pass_rate_diff']:+.1f}%")
        print(f"  Latency diff:   {comparison['latency_diff_ms']:+.1f}ms")

        if comparison["regressions"]:
            print(f"\n  Regressions ({len(comparison['regressions'])}):")
            for r in comparison["regressions"]:
                print(f"    ✗ {r['test_name']}: {r['detail']}")
        if comparison["improvements"]:
            print(f"\n  Improvements ({len(comparison['improvements'])}):")
            for r in comparison["improvements"]:
                print(f"    ✓ {r['test_name']}: {r['detail']}")

    elif action == "leaderboard":
        print(print_leaderboard())

    else:
        print(f"Unknown eval action: {action}", file=sys.stderr)
        print("Usage: openamer eval run|compare|leaderboard", file=sys.stderr)
        sys.exit(1)


# ── RAG Pipeline CLI ──────────────────────────────────────────────────────────


def _get_rag_pipeline(args: Any) -> RagPipeline:
    """Create or load a RagPipeline from CLI args."""
    strategy_map = {
        "fixed_size": ChunkingStrategy.FIXED_SIZE,
        "paragraph": ChunkingStrategy.PARAGRAPH,
        "recursive": ChunkingStrategy.RECURSIVE,
    }
    strategy = strategy_map.get(
        getattr(args, "strategy", "recursive"), ChunkingStrategy.RECURSIVE
    )
    pipeline = RagPipeline(chunking_strategy=strategy)
    index_name = getattr(args, "index_name", "default")
    pipeline.load_index(name=index_name)
    return pipeline


def cmd_rag(args: Any) -> None:
    """Handle ``openamer rag ingest|query|info``."""
    action = getattr(args, "rag_action", None)

    if action == "ingest":
        path_str = args.path
        path = Path(path_str).resolve()

        if not path.exists():
            print(f"Error: path does not exist: {path}", file=sys.stderr)
            sys.exit(1)

        pipeline = _get_rag_pipeline(args)
        chunk_size = getattr(args, "chunk_size", 500)

        if path.is_dir():
            n = pipeline.ingest_directory(
                path,
                pattern="**/*",
                recursive=True,
                chunk_size=chunk_size,
            )
            print(f"Ingested {n} chunk(s) from directory: {path}")
        else:
            n = pipeline.ingest_file(path, chunk_size=chunk_size)
            print(f"Ingested {n} chunk(s) from file: {path}")

        index_name = getattr(args, "index_name", "default")
        pipeline.save_index(name=index_name)
        print(f"Index saved as: {index_name}")
        print(f"Pipeline stats: {pipeline.stats}")

    elif action == "query":
        query_text = args.query
        top_k = getattr(args, "top_k", 5)
        pipeline = _get_rag_pipeline(args)

        if pipeline.stats["chunks"] == 0:
            print("No indexed documents. Use `openamer rag ingest` first.")
            return

        # Show retrieved context
        print(f"\nQuery: {query_text}")
        print(f"Retrieving top {top_k} chunks...\n")

        results = pipeline.retrieve(query_text, top_k=top_k)
        if not results:
            print("No relevant results found.")
            return

        for r in results:
            source = f" ({r.chunk.source})" if r.chunk.source else ""
            print(f"  [{r.rank}] score={r.score:.3f}{source}")
            # Show first 200 chars
            preview = r.chunk.text[:200].replace("\n", " ")
            print(f"      {preview}...")
            print()

    elif action == "info":
        pipeline = _get_rag_pipeline(args)
        stats = pipeline.stats
        print("\nRAG Pipeline Status:")
        print(f"  Chunks:           {stats['chunks']}")
        print(f"  Documents:        {stats['documents']}")
        print(f"  Vectorizer ready: {stats['fitted']}")
        print(f"  Chunking:         {stats['chunking_strategy']}")

    else:
        print(f"Unknown rag action: {action}", file=sys.stderr)
        print("Usage: openamer rag ingest|query|info", file=sys.stderr)
        sys.exit(1)


# ── Internal helpers ──────────────────────────────────────────────────────────


_PLUGIN_HOST_CACHE: Optional[PluginHost] = None


def _get_plugin_host() -> PluginHost:
    """Get or create the cached PluginHost singleton."""
    global _PLUGIN_HOST_CACHE
    if _PLUGIN_HOST_CACHE is None:
        _PLUGIN_HOST_CACHE = PluginHost()
        _PLUGIN_HOST_CACHE.load_all()
    return _PLUGIN_HOST_CACHE
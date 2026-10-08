#!/usr/bin/env python3
"""Verify the tool-server WIRING for group_state, without starting the server.

WHY THIS EXISTS
---------------
Importing scripts/training/tool_server.py starts the 2B model and binds :8081,
so the normal import can never be used in a test. That left the integration
uncovered by every gate — and a real defect slipped through as a result:

    the model called group_state with {"group": "moves", ...} because the tool
    had NO example in TOOLS_PROMPT, while the prompt teaches the parameter
    format through EXAMPLES. Four of ten tools had an example; group_state did
    not, so the 2B model guessed.

The fix was one example line. This test makes sure the wiring cannot silently
break again: the tool must be registered AND illustrated, because registration
alone is what the earlier (passing) checks covered.

Run:  python scripts/test_tool_server_wiring.py
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "training", "tool_server.py")

FAIL = []


def check(name, cond, detail=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")
    if not cond:
        FAIL.append(name)


def main():
    src = open(SERVER, encoding="utf-8").read()

    print("=" * 78)
    print("tool_server wiring for the group_state tool (static, no import)")
    print("=" * 78)

    # --- the file parses and the tool is in the TOOLS registry ------------
    try:
        ast.parse(src)
        check("tool_server.py parses", True)
    except SyntaxError as e:
        check("tool_server.py parses", False, str(e))
        sys.exit(1)

    tools_block = re.search(r"TOOLS = \[(.*?)\n\]", src, re.S)
    check("TOOLS registry found", tools_block is not None)
    tools_src = tools_block.group(1) if tools_block else ""
    check("group_state declared in TOOLS", '"group_state"' in tools_src)
    check("group_state declares both params",
          '"group"' in tools_src and '"moves"' in tools_src)

    # --- the executor is wired --------------------------------------------
    check("t_group_state defined", "def t_group_state(params)" in src)
    check("group_state in EXECUTORS", re.search(
        r'EXECUTORS\s*=\s*\{[^}]*"group_state"\s*:\s*t_group_state', src, re.S)
        is not None)

    # --- THE REGRESSION THIS FILE EXISTS FOR ------------------------------
    # The prompt teaches parameters via EXAMPLES, so a tool without one gets
    # called with guessed parameters. Registration alone is not enough.
    ex = re.search(r"EXAMPLES:(.*?)\"\"\"", src, re.S)
    check("EXAMPLES block found", ex is not None)
    examples = ex.group(1) if ex else ""
    check("group_state has a TOOLS_PROMPT example",
          '"tool": "group_state"' in examples,
          "without this the 2B model guesses params, e.g. "
          '{"group": "moves"}')

    # the example must show the real parameter names, not placeholders
    m = re.search(r'\{"tool": "group_state", "params": \{(.*?)\}\}', examples)
    if m:
        body = m.group(1)
        check("example shows both param names",
              '"group"' in body and '"moves"' in body, body[:60])
        # moves must be a LIST in the example: the tool accepts a list, and a
        # string example is what leads the model to emit the wrong shape
        check("example shows moves as a list", "[" in body and "]" in body)
    else:
        check("group_state example parses", False)

    # --- the executor refuses rather than trains --------------------------
    # a request must never trigger training (S6 takes ~161 s). Check the AST,
    # not the text: prose in the docstring mentioning "train(" must not trip a
    # check about code CALLING it, and a text search cannot tell them apart.
    fn = next((n for n in ast.walk(ast.parse(src))
               if isinstance(n, ast.FunctionDef) and n.name == "t_group_state"),
              None)
    check("t_group_state is a function", fn is not None)
    if fn is not None:
        body = fn.body
        called = {c.func.id for c in ast.walk(ast.Module(body=body, type_ignores=[]))
                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        check("a request never calls train()", "train" not in called,
              "requests must only LOAD a persisted model")
        src_of_body = ast.get_source_segment(src, fn) or ""
        check("request refuses when the artifact is missing",
              "no trained model" in src_of_body)
        check("out-of-range indices are validated",
              "out of range" in src_of_body and "0 <= k <" in src_of_body)

    print()
    print("=" * 78)
    if FAIL:
        print(f"WIRING TEST: FAILURES PRESENT ({len(FAIL)}): {FAIL}")
        sys.exit(1)
    print("WIRING TEST: ALL OK")
    print("=" * 78)


if __name__ == "__main__":
    main()

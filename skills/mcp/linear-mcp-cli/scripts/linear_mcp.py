"""Direct MCP streamable-HTTP client for the configured 'linear' MCP server.

Stdlib only. Reads the OAuth token OpenAmer already stored, so it works from the
CLI where the linear::* MCP tools are not loaded.

    python linear_mcp.py workspace
    python linear_mcp.py list-issues [--limit N] [--status S] [--team T]
    python linear_mcp.py tools [needle]
    python linear_mcp.py call <tool> [json-args]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HOME = os.environ.get("OPENAMER_HOME") or r"C:\Users\damir\AppData\Local\openamer-laptop"
TOKEN_FILE = os.path.join(HOME, "mcp-tokens", "linear.json")
URL = "https://mcp.linear.app/mcp"
PROTOCOL = "2025-03-26"


def load_token() -> str:
    with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)["access_token"]


def rpc(token: str, payload: dict, session_id: str | None = None) -> dict:
    """One JSON-RPC round trip. Returns {"_json": …, "_session": …} or {"_http_error": …}."""
    req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("MCP-Protocol-Version", PROTOCOL)
    if session_id:
        req.add_header("MCP-Session-Id", session_id)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw, sid = resp.read().decode("utf-8", "replace"), resp.headers.get("mcp-session-id")
            ctype = resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        return {"_http_error": exc.code, "_body": exc.read().decode("utf-8", "replace")[:2000]}
    if "text/event-stream" in ctype and "data:" in raw:  # SSE framing
        raw = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")][-1]
    try:
        return {"_json": json.loads(raw), "_session": sid}
    except ValueError:
        return {"_raw": raw[:2000], "_session": sid}


def handshake(token: str) -> str | None:
    r = rpc(token, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": PROTOCOL, "capabilities": {},
                               "clientInfo": {"name": "openamer-cli", "version": "1.0"}}})
    sid = r.get("_session")
    rpc(token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session_id=sid)
    return sid


def call(token: str, sid: str | None, name: str, args: dict, rid: int = 2) -> object:
    """Call a tool and return its decoded payload (result.content[0].text is JSON)."""
    r = rpc(token, {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                    "params": {"name": name, "arguments": args}}, session_id=sid)
    if "_http_error" in r:
        raise SystemExit(f"HTTP {r['_http_error']}: {r['_body']}")
    payload = r.get("_json", {})
    if "error" in payload:
        raise SystemExit("MCP error: " + json.dumps(payload["error"])[:800])
    text = payload["result"]["content"][0]["text"]
    try:
        return json.loads(text)
    except ValueError:
        return text


def do_list_issues(token: str, sid: str | None, a) -> int:
    args = {"limit": a.limit, "orderBy": a.order_by}
    for k in ("status", "team"):
        v = getattr(a, k)
        if v:
            args[k] = v
    cursor, total, page = None, 0, 0
    while True:
        page += 1
        if cursor:
            args["cursor"] = cursor
        data = call(token, sid, "list_issues", args, rid=10 + page)
        if isinstance(data, str):
            print(data)
            return total
        for it in data.get("issues", []):
            print(f"{it.get('id')}\t{it.get('title')}")
        total += len(data.get("issues", []))
        print(f"# page {page}: {len(data.get('issues', []))} issues "
              f"(hasNextPage={data.get('hasNextPage')})", file=sys.stderr)
        if not data.get("hasNextPage"):
            break
        cursor = data.get("cursor") or data.get("nextCursor")
        if not cursor:
            print("# no cursor returned, stopping", file=sys.stderr)
            break
    print(f"# total {total} issues in workspace", file=sys.stderr)
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="Linear MCP client")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("workspace", help="connected workspace")
    li = sub.add_parser("list-issues", help="print IDENTIFIER<TAB>TITLE per issue")
    li.add_argument("--limit", type=int, default=250)
    li.add_argument("--order-by", default="updatedAt", choices=["createdAt", "updatedAt"])
    li.add_argument("--status")
    li.add_argument("--team")
    tl = sub.add_parser("tools", help="dump tool schemas")
    tl.add_argument("needle", nargs="?", default="")
    ca = sub.add_parser("call", help="call any Linear MCP tool")
    ca.add_argument("tool")
    ca.add_argument("args", nargs="?", default="{}")
    a = p.parse_args()

    token = load_token()
    sid = handshake(token)

    if a.cmd == "workspace":
        print(json.dumps(call(token, sid, "get_workspace", {}), indent=2))
    elif a.cmd == "list-issues":
        do_list_issues(token, sid, a)
    elif a.cmd == "tools":
        r = rpc(token, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, session_id=sid)
        for t in r.get("_json", {}).get("result", {}).get("tools", []):
            if a.needle.lower() in t["name"].lower():
                print(json.dumps(t, indent=2))
    elif a.cmd == "call":
        print(json.dumps(call(token, sid, a.tool, json.loads(a.args)), indent=2))


if __name__ == "__main__":
    main()

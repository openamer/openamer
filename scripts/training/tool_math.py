#!/usr/bin/env python3
"""Tool-Augmented Math — the 2B model writes code, Python executes it.

This breaks the "2B can't do math" limit: the model doesn't CALCULATE,
it GENERATES a program. Python (the tool) computes the exact result.
The model orchestrates; the tool executes. Verification is built in:
the code either runs and produces a number, or it fails and gets one
retry with the error message.

Also supports SmolVLM local vision if installed (optional, graceful).

CLI:
  python tool_math.py "math word problem"
  python tool_math.py "problem" --show-code
"""
import json, sys, os, re, subprocess, urllib.request

LIVE = "http://localhost:8081"
MAX_RETRIES = 2

def chat(messages, max_tokens=200):
    req = urllib.request.Request(LIVE + "/v1/chat/completions",
        data=json.dumps({"model": "mini-openamer", "messages": messages,
                         "max_tokens": max_tokens}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))[
        "choices"][0]["message"]["content"]

def extract_code(text):
    m = re.search(r"```python\s*(.*?)```", text, re.S)
    return m.group(1).strip() if m else None

def run_code(code, timeout=15):
    try:
        r = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()[:200]
    except subprocess.TimeoutExpired:
        return False, "", "timeout"

def solve_math(problem, show_code=False):
    messages = [
        {"role": "system", "content":
         "Reply ONLY with a python code block that solves the task and prints "
         "the final result. No explanations, no markdown outside the block."},
        {"role": "user", "content": problem}]
    for attempt in range(MAX_RETRIES + 1):
        code_raw = chat(messages)
        code = extract_code(code_raw) or code_raw
        ok, out, err = run_code(code)
        if ok and out:
            result = {"answer": out, "code": code if show_code else None,
                      "attempts": attempt + 1, "method": "python-execution"}
            return result
        # one retry with the error fed back
        messages.append({"role": "assistant", "content": code_raw[:400]})
        messages.append({"role": "user", "content":
                         f"Error: {err or 'no output'}. Fix the code. Reply only with the corrected block."})
    return {"error": "all attempts failed", "last_error": err, "attempts": MAX_RETRIES + 1}

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--show-code"]
    show = "--show-code" in sys.argv
    if not args:
        print(__doc__); sys.exit(1)
    print(json.dumps(solve_math(" ".join(args), show_code=show),
                     ensure_ascii=False, indent=1))

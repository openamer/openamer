import json
import os
import sys

os.environ["OPENAMER_REPO"] = "C:/Users/damir/openamer-repo"
sys.path.insert(0, "C:/Users/damir/openamer-repo")

from openamer_cli.auto_tester import run_cron_entry

logpath = run_cron_entry()
with open(logpath, encoding="utf-8") as f:
    result = json.load(f)

summary = {
    "log": logpath,
    "status": result.get("status"),
    "exit_code": result.get("exit_code"),
    "elapsed_seconds": result.get("elapsed_seconds"),
    "tail": (result.get("stdout") or "")[-400:],
    "stderr": (result.get("stderr") or "")[-300:],
}
print(json.dumps(summary, ensure_ascii=False, indent=2))

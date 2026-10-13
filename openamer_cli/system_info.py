"""openamer_cli.system_info — OpenAmer's self-knowledge of its own system.

One source of truth for "what system am I running on" so OpenAmer can reason
about its own environment: OS, architecture, Python, hardware (CPU/RAM/GPU),
disk, locale, and its own OpenAmer config (home, model, provider, tools,
skills). Returned as a plain dict profile usable by the agent and the CLI.

Every probe is a guarded best-effort so a missing dependency / platform never
crashes the host; imports are lazy.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _openamer_home() -> str:
    return os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")


def _os_info() -> dict:
    return {
        "system": _try(platform.system, "?"),
        "release": _try(platform.release, ""),
        "version": _try(platform.version, ""),
        "machine": _try(platform.machine, ""),
        "processor": _try(platform.processor, ""),
    }


def _ram_mb():
    try:
        import psutil
        return int(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        return None


def _disk_free_gb(path: str):
    try:
        st = shutil.disk_usage(path)
        return round(st.free / (1024 ** 3), 1)
    except Exception:
        return None


def _gpu_info() -> dict:
    try:
        import subprocess
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8)
        if out.returncode == 0 and out.stdout.strip():
            first = out.stdout.strip().splitlines()[0]
            name, mem = first.split(",")[0].strip(), first.split(",")[1].strip()
            return {"name": name, "vram_gb": round(int(mem) / 1024, 1),
                    "cuda_available": True}
    except Exception:
        pass
    return {"cuda_available": False}


def _config_info() -> dict:
    home = _openamer_home()
    info = {"home": home}
    cfg = Path(home) / "config.yaml"
    if not cfg.exists():
        return info
    try:
        import yaml
        with open(cfg, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        llm = d.get("llm") or {}
        info["configured"] = True
        info["model"] = d.get("model") or llm.get("model")
        info["provider"] = d.get("provider") or llm.get("provider")
    except Exception:
        info["configured"] = False
    return info


def _count_tools() -> int:
    tools = Path(__file__).resolve().parent.parent / "tools"
    return len(list(tools.glob("*.py"))) if tools.exists() else 0


def _count_skills() -> int:
    home_skills = Path(_openamer_home()) / "skills"
    if home_skills.exists():
        return len(list(home_skills.rglob("SKILL.md")))
    return 0


def collect() -> dict:
    """Gather the full self-system profile (all probes best-effort)."""
    home = _openamer_home()
    return {
        "os": _os_info(),
        "python": sys.version.split()[0],
        "arch": f"{platform.machine()} ({platform.architecture()[0]})",
        "cpu": platform.machine(),
        "ram_mb": _ram_mb(),
        "disk_free_gb": _disk_free_gb(home),
        "gpu": _gpu_info(),
        "locale": os.environ.get("LANG") or os.environ.get("LC_ALL") or "system-default",
        "openamer": _config_info(),
        "tools_count": _count_tools(),
        "skills_count": _count_skills(),
    }


def describe() -> str:
    """Human-readable single-paragraph selfning about the system."""
    c = collect()
    osi = c["os"]
    gpu = c["gpu"]
    gpu_s = f"{gpu.get('name') or 'unknown'} ({gpu.get('vram_gb')} GB)" if gpu.get("cuda_available") else "no/unknown GPU"
    oa = c["openamer"]
    return (
        f"OpenAmer runs on {osi['system']} {osi['release']} ({osi['machine']}), "
        f"Python {c['python']}, RAM {c['ram_mb']}MB, {c['disk_free_gb']}GB free, "
        f"GPU: {gpu_s}. Home: {oa['home']} | model={oa.get('model','?')} | "
        f"provider={oa.get('provider','?')} | {c['tools_count']} tools, {c['skills_count']} skills, "
        f"locale={c['locale']}."
    )
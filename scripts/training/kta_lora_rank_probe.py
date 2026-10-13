#!/usr/bin/env python3
"""KTA experiment: does a smaller LoRA rank (4-8) match r=16 on the same budget?

Replaces the log-only stub that previously sat in
knowledge_to_action.experiment_lora_rank(): for 184 cycles it wrote a fixed
string ("baseline recorded (r=16 live)") after merely polling /health, and no
baseline was ever recorded anywhere.

Runs on the CPU-only laptop against the locally cached
Qwen2.5-0.5B-Instruct. Fair A/B per arm: same rows, same order, same seed,
same step budget, same init (kaiming A, zero B). Loss = mean cross-entropy
over the last TAIL_STEPS micro-steps.

Artifact: <training dir>/kta_artifacts/lora_rank_result.json
Run:  venv/Scripts/python.exe scripts/training/kta_lora_rank_probe.py
"""
import json
import os
import pathlib
import sys
import time

BASE = "Qwen/Qwen2.5-0.5B-Instruct"
RANKS = [4, 8, 16]
MAXLEN = 256
WARM_STEPS = 4
TAIL_STEPS = 4
MICRO_STEPS = 16
GRAD_ACCUM = 4
LR = 2e-4
SEED = 1234
BUDGET_S = float(os.environ.get("KTA_LORA_BUDGET", "900"))


def _training_dir() -> pathlib.Path:
    """Resolve the live training dir — same chain as knowledge_to_action.

    The probe must write the artifact where experiment_lora_rank() reads it,
    and the reader uses _training_dir(). Resolving to __file__'s own directory
    made the two diverge whenever the probe ran from the repo checkout instead
    of the live install.
    """
    cands = []
    env = os.environ.get("OPENAMER_HOME")
    if env:
        cands.append(os.path.join(env, "scripts", "training"))
    cands.append(str(pathlib.Path.home() / "AppData" / "Local" /
                     "openamer-laptop" / "scripts" / "training"))
    cands.append(str(pathlib.Path(__file__).resolve().parent))
    for c in cands:
        if os.path.isdir(c):
            return pathlib.Path(c)
    return pathlib.Path(__file__).resolve().parent


T = _training_dir()
OUT = T / "kta_artifacts"


def free_gb() -> float:
    try:
        import ctypes

        class M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = M()
        m.dwLength = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullAvailPhys / 1e9, 1)
    except Exception:
        return -1.0


def emit(obj: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lora_rank_result.json").write_text(json.dumps(obj, indent=2),
                                               encoding="utf-8")
    if obj.get("ok"):
        best = min(obj["arms"], key=lambda a: a["final_loss"])
        print(f"[kta-lora] {obj['result']}", flush=True)
        print(f"[kta-lora] best rank={best['rank']} "
              f"final_loss={best['final_loss']}", flush=True)
    else:
        print(f"[kta-lora] {obj.get('error')}", flush=True)


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def main() -> None:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    free = free_gb()
    if 0 <= free < 2.5:
        emit({"ok": False, "ran_at": _stamp(),
              "error": f"skipped: only {free} GB free RAM"})
        return

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token_id is None:
        tok.pad_token_id = tok.eos_token_id

    rows = []
    with open(T / "sft_openamer.jsonl", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line)["messages"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    samples = []
    for msgs in rows:
        ids = tok(tok.apply_chat_template(msgs, tokenize=False,
                                         add_generation_prompt=False),
                  truncation=True, max_length=MAXLEN)["input_ids"]
        if len(ids) >= 8:
            samples.append(torch.tensor(ids, dtype=torch.long))
    if not samples:
        emit({"ok": False, "ran_at": _stamp(), "error": "no usable SFT rows"})
        return

    def fresh_model():
        m = AutoModelForCausalLM.from_pretrained(
            BASE, dtype=torch.float32, low_cpu_mem_usage=True)
        m.config.use_cache = False
        return m

    model = fresh_model()
    arms, timed_out = [], False
    for rank in RANKS:
        if time.time() - t0 > BUDGET_S:
            timed_out = True
            break
        torch.manual_seed(SEED)
        pm = get_peft_model(model, LoraConfig(
            r=rank, lora_alpha=2 * rank, lora_dropout=0.0,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM"))
        params = [p for p in pm.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=LR)
        pm.train()

        losses, step = [], 0
        while step < MICRO_STEPS and time.time() - t0 <= BUDGET_S:
            ids = samples[step % len(samples)].unsqueeze(0)
            loss = pm(input_ids=ids, labels=ids).loss
            (loss / GRAD_ACCUM).backward()
            losses.append(round(float(loss.detach()), 4))
            if (step + 1) % GRAD_ACCUM == 0:
                opt.step()
                opt.zero_grad()
            step += 1

        if len(losses) < WARM_STEPS + TAIL_STEPS:
            emit({"ok": False, "ran_at": _stamp(),
                  "error": f"budget exhausted at r={rank} after "
                           f"{len(losses)} steps (budget={BUDGET_S}s)"})
            return

        init = sum(losses[:WARM_STEPS]) / WARM_STEPS
        fin = sum(losses[-TAIL_STEPS:]) / TAIL_STEPS
        arms.append({"rank": rank,
                     "trainable_params": sum(p.numel() for p in params),
                     "initial_loss": round(init, 4),
                     "final_loss": round(fin, 4),
                     "drop": round(init - fin, 4),
                     "steps": len(losses)})
        model = fresh_model()  # clean base for the next arm

    if len(arms) < 2:
        emit({"ok": False, "ran_at": _stamp(),
              "error": f"only {len(arms)} arm(s) completed "
                       f"(budget={BUDGET_S}s, timed_out={timed_out})"})
        return

    best = min(arms, key=lambda a: a["final_loss"])
    small = [a for a in arms if a["rank"] <= 8]
    small_best = min(small, key=lambda a: a["final_loss"]) if small else best
    base16 = next((a for a in arms if a["rank"] == 16), None)
    if base16:
        verdict = (f"r={small_best['rank']} vs r=16: final loss "
                   f"{small_best['final_loss']} vs {base16['final_loss']} "
                   f"(delta {round(base16['final_loss'] - small_best['final_loss'], 4):+})")
    else:
        verdict = f"best r={small_best['rank']} final loss {small_best['final_loss']}"

    emit({"ok": True, "ran_at": _stamp(), "base_model": BASE,
          "rows": len(samples),
          "protocol": f"{MICRO_STEPS} micro-steps, accum {GRAD_ACCUM}, "
                      f"lr {LR}, maxlen {MAXLEN}, seed {SEED}",
          "arms": arms, "best_rank": best["rank"], "result": verdict,
          "elapsed_s": round(time.time() - t0, 1), "timed_out": timed_out})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        emit({"ok": False, "ran_at": _stamp(),
              "error": f"{type(e).__name__}: {str(e)[:200]}"})
        sys.exit(0)

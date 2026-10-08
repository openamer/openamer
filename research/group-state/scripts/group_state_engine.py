#!/usr/bin/env python3
"""Group-state inference: train, SAVE, LOAD, and answer from a trained model.

WHY THIS FILE EXISTS
--------------------
The group-state work (scripts/group_scaling_lab.py, s5_*_lab.py) trained a model
and immediately evaluated it in the same process. Nothing was ever persisted, so
the architecture could not be USED -- it could only be demonstrated. This module
closes that gap: it trains a group-state tracker on a named group, saves the
weights to JSON, and reloads them to answer state-tracking queries.

This is the smallest honest form of "integrated": a real trained model, on disk,
answering real requests through a stable interface. It is NOT injected into a
language model -- Mini-OpenAmer is a LoRA fine-tune of Qwen served as GGUF, so
there is no nn.Module to attach a layer to. What CAN be delivered is a tool the
agent calls when it needs exact composed state over a long sequence.

HONEST SCOPE
------------
- Trained on synthetic group products. No language data.
- The group and its generators are fixed at train time.
- Parameters: K^2 + K (e.g. 30 for S5). The readout is structural.
- Verified by scripts/test_group_state_engine.py.

Usage:
  python scripts/group_state_engine.py --train S5 --out models/group_state_s5.json
  python scripts/group_state_engine.py --ask S5 --moves "0 1 2"
  python scripts/group_state_engine.py --info
"""
import argparse
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from group_scaling_lab import build_group, GroupState, _attach, task, accuracy

DEFAULT_DIR = os.path.join(
    os.environ.get("OPENAMER_HOME",
                   os.path.join(os.path.expanduser("~"), "AppData", "Local",
                                "openamer-laptop")),
    "models")
DEFAULT_TAU = 0.1
FORMAT = "openamer-group-state-v1"   # written by save(), asserted by load()


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------
def train(group_name, epochs=200, n_train=256, tau=DEFAULT_TAU, seed=7000,
          train_lens=(1, 7)):
    """Train a group-state tracker. Returns (model, group, stats)."""
    g = _attach(build_group(group_name))
    rng = random.Random(seed)
    m = GroupState(g, rng, tau=tau)
    lo, hi = 1, train_lens[1]
    data = [task(g, rng, random.choice(range(lo, hi + 1)))
            for _ in range(n_train)]

    t0 = time.time()
    _adam_step(m, data, epochs, 0.05)
    secs = round(time.time() - t0, 1)

    per = {}
    for L in (4, 6, 12, 24, 48, 96):
        per[str(L)] = accuracy(m, g, L, n=120, seed=11 + L)
    stats = {"group": group_name, "order": g.order,
             "num_generators": g.num_gens,
             "params": sum(p.n for p in m.params()),
             "trained_on": f"lengths {lo}-{hi}",
             "acc": per, "secs": secs, "tau": tau}
    return m, g, stats


def _adam_step(m, data, epochs, lr):
    """Adam over the choice parameters, using the structural dL/dS.

    Kept here rather than in group_scaling_lab so the persisted artifact
    depends only on this module's own code path.
    """
    ps = m.params()
    mo = [[0.0] * p.n for p in ps]
    vo = [[0.0] * p.n for p in ps]
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    for _ in range(epochs):
        random.shuffle(data)
        for xs, t in data:
            for p in ps:
                p.zero()
            m.forward(xs)
            _, gS = m.backward_S(t)
            m.backward(gS)
            step += 1
            bc1, bc2 = 1 - b1 ** step, 1 - b2 ** step
            for i, p in enumerate(ps):
                for j in range(p.n):
                    gj = p.grad[j]
                    mo[i][j] = b1 * mo[i][j] + (1 - b1) * gj
                    vo[i][j] = b2 * vo[i][j] + (1 - b2) * gj * gj
                    p.data[j] -= lr * (mo[i][j] / bc1) / \
                        (math.sqrt(vo[i][j] / bc2) + eps)


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------
def save(model, group, stats, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    payload = {
        "format": FORMAT,
        "group": group.name,
        "order": group.order,
        "num_generators": group.num_gens,
        "point_count": group.n,
        "tau": model.tau,
        "params": [p.data for p in model.params()],
        "param_shapes": [p.n for p in model.params()],
        "stats": stats,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def load(path):
    """Rebuild a trained model from disk. Returns (model, group, payload)."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("format") != FORMAT:
        raise ValueError(f"unknown model format: {d.get('format')}")
    g = _attach(build_group(d["group"]))
    m = GroupState(g, random.Random(0), tau=d.get("tau", DEFAULT_TAU))
    ps = m.params()
    if [p.n for p in ps] != d["param_shapes"]:
        raise ValueError("param shapes do not match the saved model")
    for p, data in zip(ps, d["params"]):
        p.data = list(data)
    return m, g, d


# ---------------------------------------------------------------------------
# answering
# ---------------------------------------------------------------------------
def answer(model, group, moves):
    """Compose the generator sequence and return the exact group element.

    `moves` is a list of generator indices (0..num_generators-1) OR the
    generator permutations themselves as lists. The forward pass composes the
    STATE; the structural readout turns the final state into a group element.
    """
    from group_scaling_lab import compose
    norm = []
    for mv in moves:
        if isinstance(mv, int):
            norm.append(mv)
        else:
            # a permutation was given: find its index among the generators
            t = tuple(mv)
            if t not in group.generators:
                raise ValueError(f"move {mv} is not a generator of {group.name}")
            norm.append(group.generators.index(t))
    logits = model.forward(norm)
    best = max(range(len(logits)), key=lambda i: logits[i])
    # ground truth, computed independently of the network
    st = group.identity
    for k in norm:
        st = compose(st, group.generators[k])
    truth = group.index[st]
    return {"group": group.name,
            "moves": norm,
            "length": len(norm),
            "element_index": best,
            "element": list(group.elements[best]),
            "correct": best == truth,
            "truth_index": truth,
            "generators": [list(x) for x in group.generators]}


def model_path(group_name, directory=None):
    """Where a group's trained artifact lives (one file per group)."""
    return os.path.join(directory or DEFAULT_DIR,
                        f"group_state_{group_name.lower()}.json")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", metavar="GROUP")
    ap.add_argument("--ask", metavar="GROUP")
    ap.add_argument("--moves", default="")
    ap.add_argument("--out", default=None)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--n-train", type=int, default=256)
    ap.add_argument("--tau", type=float, default=DEFAULT_TAU)
    ap.add_argument("--info", action="store_true")
    args = ap.parse_args()

    if args.info:
        d = DEFAULT_DIR
        print(f"model directory: {d}")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.startswith("group_state_") and fn.endswith(".json"):
                    p = os.path.join(d, fn)
                    try:
                        _, _, payload = load(p)
                        s = payload["stats"]
                        print(f"  {fn}: |G|={payload['order']} "
                              f"params={s['params']} trained_on={s['trained_on']}")
                    except Exception as e:
                        print(f"  {fn}: UNREADABLE ({e})")
        return

    if args.train:
        m, g, stats = train(args.train, epochs=args.epochs,
                            n_train=args.n_train, tau=args.tau)
        out = args.out or model_path(args.train)
        save(m, g, stats, out)
        print(f"trained {args.train}: |G|={g.order} params={stats['params']} "
              f"({stats['secs']}s)")
        print("accuracy at unseen lengths:")
        for L, a in stats["acc"].items():
            star = "*" if int(L) > 7 else " "
            print(f"  L={L:>3s}{star} {a:.3f}")
        print(f"saved -> {out}")
        return

    if args.ask:
        moves = [int(x) for x in args.moves.split()] if args.moves else []
        p = model_path(args.ask)
        if not os.path.exists(p):
            print(f"no trained model at {p}; run --train {args.ask} first")
            sys.exit(2)
        m, g, payload = load(p)
        r = answer(m, g, moves)
        print(json.dumps(r, indent=2))
        sys.exit(0 if r["correct"] else 1)

    ap.print_help()


if __name__ == "__main__":
    main()

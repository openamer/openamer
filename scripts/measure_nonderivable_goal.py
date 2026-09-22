"""Bounded experiment: is there a goal whose label does NOT follow from the inputs?

Self-learning's own verdict says: "Aussagekräftig wäre ein Ziel, das NICHT aus den
Eingaben folgt." This measures exactly that.

Goal: predict the role of the NEXT message (assistant vs. not) from the content of
the current message. Temporal split (train on older, test on newer) so the test set
is genuinely held out.

Read-only against state.db.
"""
import math, random, sqlite3
from pathlib import Path

from self_learning import oa_ripple  # same activation as the production net

HOME = Path(r"C:/Users/damir/AppData/Local/openamer-laptop")
N = 6000
LIMIT = 80  # same window the production script sees

FEATS = ["len/500", "has?", "has!", "code```", "python", "role==user"]


def feats(role, content):
    return [
        min(1.0, len(content) / 500),
        1.0 if "?" in content else 0.0,
        1.0 if "!" in content else 0.0,
        min(1.0, content.count("```") / 10),
        1.0 if "python" in content.lower() else 0.0,
        1.0 if role == "user" else 0.0,
    ]


def load(n=N, limit=None):
    con = sqlite3.connect(str(HOME / "state.db"))
    q = "SELECT role, content FROM messages ORDER BY id DESC"
    q += f" LIMIT {limit}" if limit else f" LIMIT {n}"
    rows = [(r, c) for r, c in con.execute(q) if c]
    con.close()
    rows.reverse()  # chronological
    return rows


def build(rows, use_role=True):
    data, keep = [], 6 if use_role else 5
    for k in range(len(rows) - 1):
        role, content = rows[k]
        y = 1.0 if rows[k + 1][0] == "assistant" else 0.0
        data.append((feats(role, content)[:keep], [y]))
    return data


def train(data, epochs=300, lr=0.3, seed=42):
    n_in = len(data[0][0])
    r = random.Random(seed)
    w1 = [[r.gauss(0, 0.5) for _ in range(n_in)] for _ in range(6)]
    b1 = [0.0] * 6
    w2 = [r.gauss(0, 0.5) for _ in range(6)]
    b2 = 0.0
    for _ in range(epochs):
        for x, y in data:
            h = [oa_ripple(b1[i] + sum(w1[i][j] * x[j] for j in range(n_in))) for i in range(6)]
            o = 1.0 / (1.0 + math.exp(-(b2 + sum(w2[i] * h[i] for i in range(6)))))
            dz2 = 2 * (o - y[0]) * o * (1 - o)
            for i in range(6):
                w2[i] -= lr * dz2 * h[i]
            b2 -= lr * dz2
            for i in range(6):
                z1 = b1[i] + sum(w1[i][j] * x[j] for j in range(n_in))
                e = 1e-6
                dz1 = (dz2 * w2[i]) * ((oa_ripple(z1 + e) - oa_ripple(z1 - e)) / (2 * e))
                for j in range(n_in):
                    w1[i][j] -= lr * dz1 * x[j]
                b1[i] -= lr * dz1
    return (w1, b1, w2, b2)


def acc(model, data):
    w1, b1, w2, b2 = model
    n_in = len(data[0][0])
    ok = 0
    for x, y in data:
        h = [oa_ripple(b1[i] + sum(w1[i][j] * x[j] for j in range(n_in))) for i in range(6)]
        o = 1.0 / (1.0 + math.exp(-(b2 + sum(w2[i] * h[i] for i in range(6)))))
        ok += int((1.0 if o >= 0.5 else 0.0) == y[0])
    return ok / len(data)


CONFIGS = [
    ("production window: newest %d msgs (role feature kept)" % LIMIT, LIMIT, True),
    ("full %d-msg window (role feature kept)" % N, None, True),
    ("full %d-msg window (role feature dropped)" % N, None, False),
]

for label, lim, use_role in CONFIGS:
    rows = load(limit=lim) if lim else load()
    data = build(rows, use_role=use_role)
    cut = int(len(data) * 0.7)
    tr, te = data[:cut], data[cut:]
    prior = max(sum(y[0] for _x, y in te) / len(te), 1 - sum(y[0] for _x, y in te) / len(te))
    model = train(tr)
    a_tr, a_te = acc(model, tr), acc(model, te)
    print(f"\n[{label}]  n={len(data)} train={len(tr)} test={len(te)}")
    print(f"  label prior (next msg is assistant): {sum(y[0] for _x, y in data)/len(data):.3f}")
    print(f"  majority-class baseline (test):      {prior:.3f}")
    print(f"  oa_ripple accuracy  train: {a_tr:.3f}   TEST (held out): {a_te:.3f}")
    print(f"  -> edge over trivial baseline:       {a_te - prior:+.3f}")

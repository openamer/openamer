#!/usr/bin/env python3
"""Forschungslauf 2: oa_ripple vs Standard — Benchmark auf 4 Aufgaben."""
import math, random, time

def sigmoid(x): return 1.0 / (1.0 + math.exp(-max(-100, min(100, x))))
def relu(x): return max(0.0, x)
def tanh(x): return math.tanh(x)
def oa_ripple(x): return math.sin(x) * sigmoid(x)

def num_grad(fn, x, eps=1e-6):
    return (fn(x+eps) - fn(x-eps)) / (2*eps)

ACTIVATIONS = {"sigmoid": sigmoid, "relu": relu, "tanh": tanh, "oa_ripple": oa_ripple}

# Datasets
DATASETS = {
    "XOR": [([0,0],[0]), ([0,1],[1]), ([1,0],[1]), ([1,1],[0])],
    "AND": [([0,0],[0]), ([0,1],[0]), ([1,0],[0]), ([1,1],[1])],
    "OR":  [([0,0],[0]), ([0,1],[1]), ([1,0],[1]), ([1,1],[1])],
}

def make_net(activation, seed=42):
    r = random.Random(seed)
    w1 = [[r.gauss(0, 0.5) for _ in range(2)] for _ in range(4)]
    b1 = [0.0]*4
    w2 = [[r.gauss(0, 0.5) for _ in range(4)]]
    b2 = [0.0]
    return w1, b1, w2, b2

def train(dataset, activation, epochs=300, lr=0.5, seed=42):
    w1, b1, w2, b2 = make_net(activation, seed)
    fn = ACTIVATIONS[activation]
    for ep in range(epochs):
        loss = 0.0
        for x, y in dataset:
            h = [fn(b1[i] + sum(w1[i][j]*x[j] for j in range(2))) for i in range(4)]
            o = sigmoid(b2[0] + sum(w2[0][i]*h[i] for i in range(4)))
            loss += (o - y[0])**2
            dz2 = 2*(o - y[0]) * o*(1-o)
            for i in range(4):
                w2[0][i] -= lr * dz2 * h[i]
            b2[0] -= lr * dz2
            for i in range(4):
                z1 = b1[i] + sum(w1[i][j]*x[j] for j in range(2))
                dz1 = (dz2 * w2[0][i]) * num_grad(fn, z1)
                for j in range(2):
                    w1[i][j] -= lr * dz1 * x[j]
                b1[i] -= lr * dz1
    # Test
    correct = 0
    for x, y in dataset:
        h = [fn(b1[i] + sum(w1[i][j]*x[j] for j in range(2))) for i in range(4)]
        o = sigmoid(b2[0] + sum(w2[0][i]*h[i] for i in range(4)))
        if abs(o - y[0]) < 0.5: correct += 1
    return correct, loss/len(dataset)

print("=== Forschungslauf 2: Benchmark ===")
results = []
for dname, data in DATASETS.items():
    for aname in ACTIVATIONS:
        for trial in range(3):
            acc, loss = train(data, aname, epochs=200, lr=0.5, seed=trial)
            results.append((dname, aname, acc, loss))
            print(f"  {dname:5s} {aname:10s} trial {trial}: acc={acc}/4 loss={loss:.4f}")

print("\n=== Zusammenfassung ===")
for dname in DATASETS:
    print(f"\n--- {dname} ---")
    for aname in ACTIVATIONS:
        accs = [r[2] for r in results if r[0]==dname and r[1]==aname]
        avg = sum(accs)/len(accs)
        stars = "⭐" if avg >= 3.5 else "  "
        print(f"  {stars} {aname:10s}: {avg:.1f}/4 avg ({min(accs)}-{max(accs)})")
#!/usr/bin/env python3
"""Forschungslauf 1: OA_Aktivierungen vs Standard — Backprop mit numerischem Gradient."""
import math, random

def sigmoid(x): return 1.0 / (1.0 + math.exp(-max(-100, min(100, x))))

def oa_hexp(x):
    if x >= 0: return 0.5 * x * (1.0 + math.tanh(0.7978845608 * (x + 0.044715 * x**3)))
    return -0.1 * math.exp(-x) * x * x

def oa_ripple(x): return math.sin(x) * sigmoid(x)

def numerical_grad(fn, x, eps=1e-6):
    return (fn(x + eps) - fn(x - eps)) / (2 * eps)

# Gradienten testen
print("=== Gradienten-Check ===")
for name, fn in [("oa_hexp", oa_hexp), ("oa_ripple", oa_ripple)]:
    for x in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]:
        g = numerical_grad(fn, x)
        print(f"  {name}({x:+.1f}) = {fn(x):+.4f}  grad = {g:+.4f}")
print()

# XOR Training mit numerischem Gradient
xor = [([0,0],[0]), ([0,1],[1]), ([1,0],[1]), ([1,1],[0])]
random.seed(42)

w1 = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(4)]
b1 = [0.0]*4
w2 = [[random.gauss(0, 0.5) for _ in range(4)] for _ in range(1)]
b2 = [0.0]

ACT = {"hexp": oa_hexp, "ripple": oa_ripple, "sigmoid": sigmoid}

def forward(x, activation="hexp"):
    fn = ACT[activation]
    h = [fn(b1[i] + sum(w1[i][j]*x[j] for j in range(2))) for i in range(4)]
    o = sigmoid(b2[0] + sum(w2[0][i]*h[i] for i in range(4)))
    return h, o

def train_xor(activation, epochs=500, lr=0.1):
    global w1, b1, w2, b2
    # Reset
    w1[:] = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(4)]
    b1[:] = [0.0]*4
    w2[:] = [[random.gauss(0, 0.5) for _ in range(4)]]
    b2[0] = 0.0
    fn = ACT[activation]
    
    for ep in range(epochs):
        total_loss = 0.0
        for x, y in xor:
            h, o = forward(x, activation)
            loss = (o - y[0])**2
            total_loss += loss
            
            dout = 2 * (o - y[0])
            dsig = o * (1 - o)
            dz2 = dout * dsig
            for i in range(4):
                w2[0][i] -= lr * dz2 * h[i]
            b2[0] -= lr * dz2
            
            dh = [dz2 * w2[0][i] for i in range(4)]
            for i in range(4):
                z1 = b1[i] + sum(w1[i][j]*x[j] for j in range(2))
                dz1 = dh[i] * numerical_grad(fn, z1)
                for j in range(2):
                    w1[i][j] -= lr * dz1 * x[j]
                b1[i] -= lr * dz1
        
        if ep % 100 == 0:
            _, o0 = forward(xor[0][0], activation)
            _, o1 = forward(xor[1][0], activation)
            acc = sum(1 for x,y in xor if abs(forward(x,activation)[1] - y[0]) < 0.5)
            print(f"  {activation:10s} Ep {ep:3d} loss={total_loss/4:.4f} acc={acc}/4")

print("=== Forschungslauf 1: OA-Aktivierungen auf XOR ===")
train_xor("hexp", epochs=500, lr=0.5)
print()
train_xor("ripple", epochs=500, lr=0.5)
print()

# Endergebnis
for name in ["hexp", "ripple"]:
    train_xor(name, epochs=200, lr=0.5)
    print(f"\n--- {name} — Final ---")
    for x, y in xor:
        _, o = forward(x, name)
        print(f"  {x} → {o:.4f} (soll: {y[0]}) ✓" if abs(o-y[0])<0.5 else f"  {x} → {o:.4f} (soll: {y[0]}) ✗")
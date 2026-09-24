#!/usr/bin/env python3
"""Evolutionäre Architektur-Suche: Findet beste Kombination aus Aktivierungen + Topologie."""
import math, random, time, json
from pathlib import Path

ACTIVATIONS = {
    "relu": lambda x: max(0.0, x),
    "sigmoid": lambda x: 1.0/(1.0+math.exp(-max(-100, min(100, x)))),
    "tanh": lambda x: math.tanh(x),
    "gelu": lambda x: 0.5*x*(1+math.tanh(0.7978845608*(x+0.044715*x**3))),
    "oa_ripple": lambda x: math.sin(x)/(1.0+math.exp(-max(-100, min(100, x)))),
}

# XOR + erweiterte Tests
TASKS = {
    "XOR": {
        "data": [([0,0],[0]),([0,1],[1]),([1,0],[1]),([1,1],[0])],
        "input": 2, "output": 1
    },
    "CIRCLE": {  # Nicht-linear trennbar
        "data": [], "input": 2, "output": 1
    }
}
# CIRCLE-Daten generieren
for a in range(-10, 11):
    for b in range(-10, 11):
        x, y = a/10, b/10
        TASKS["CIRCLE"]["data"].append(([x,y], [1 if x*x+y*y < 0.5 else 0]))

def num_grad(fn, x, eps=1e-6):
    return (fn(x+eps)-fn(x-eps))/(2*eps)

def make_random_net(task_name, max_layers=5):
    task = TASKS[task_name]
    config = []
    size = task["input"]
    n_layers = random.randint(1, max_layers)
    for _ in range(n_layers):
        next_size = random.choice([size, max(1,size//2), size*2, 4, 8])
        act = random.choice(list(ACTIVATIONS.keys()))
        config.append((size, next_size, act))
        size = next_size
    config.append((size, task["output"], "sigmoid"))
    return config

def eval_config(config, task_name, trials=2, epochs=100, lr=0.3):
    task = TASKS[task_name]
    total_acc = 0
    for seed in range(trials):
        r = random.Random(seed)
        weights = []
        for inp, out, act in config:
            w = [[r.gauss(0, 0.5/inp**0.5) for _ in range(inp)] for _ in range(out)]
            b = [0.0]*out
            weights.append((w, b))
        
        # Training
        for ep in range(epochs):
            for x, y in task["data"]:
                acts = [x]
                for li, (inp, out, act_name) in enumerate(config):
                    w, b = weights[li]
                    fn = ACTIVATIONS[act_name]
                    z = [b[i] + sum(w[i][j]*acts[-1][j] for j in range(inp)) for i in range(out)]
                    a = [fn(zi) for zi in z]
                    acts.append(a)
                
                loss = sum((acts[-1][i]-y[i])**2 for i in range(out))
                grad = [2*(acts[-1][i]-y[i]) for i in range(out)]
                
                for li in range(len(config)-1, -1, -1):
                    inp, out, act_name = config[li]
                    w, b = weights[li]
                    fn = ACTIVATIONS[act_name]
                    prev_act = acts[li]
                    new_grad = [0.0]*inp
                    
                    for ni in range(out):
                        z = b[ni] + sum(w[ni][j]*prev_act[j] for j in range(inp))
                        dz = grad[ni] * num_grad(fn, z)
                        for ji in range(inp):
                            w[ni][ji] -= lr * dz * prev_act[ji]
                            new_grad[ji] += dz * w[ni][ji]
                        b[ni] -= lr * dz
                    grad = new_grad
        
        # Test
        correct = 0
        for x, y in task["data"]:
            acts = [x]
            for li, (inp, out, act_name) in enumerate(config):
                w, b = weights[li]
                fn = ACTIVATIONS[act_name]
                z = [b[i] + sum(w[i][j]*acts[-1][j] for j in range(inp)) for i in range(out)]
                a = [fn(zi) for zi in z]
                acts.append(a)
            pred = 0 if acts[-1][0] < 0.5 else 1
            if pred == y[0]:
                correct += 1
        total_acc += correct/len(task["data"])
    
    return total_acc/trials

def evolve(task_name, pop_size=20, generations=5):
    pop = [make_random_net(task_name) for _ in range(pop_size)]
    best_overall = None
    best_fitness = -1
    
    for gen in range(generations):
        fitnesses = []
        for config in pop:
            f = eval_config(config, task_name, trials=2, epochs=80, lr=0.3)
            fitnesses.append((f, config))
        
        fitnesses.sort(key=lambda x: -x[0])
        pop = [c for _, c in fitnesses[:5]]
        
        if fitnesses[0][0] > best_fitness:
            best_fitness = fitnesses[0][0]
            best_overall = fitnesses[0][1]
        
        while len(pop) < pop_size:
            parent = random.choice(pop[:3])
            child = list(parent)
            if random.random() < 0.5 and len(child) > 1:
                # Mutation: ändere eine Schicht
                idx = random.randrange(len(child))
                inp, out, act = child[idx]
                child[idx] = (inp, out, random.choice(list(ACTIVATIONS.keys())))
            pop.append(child)
        
        print(f"  Gen {gen+1}: Best = {fitnesses[0][0]:.3f} ({len(fitnesses[0][1])} layers)")
    
    return best_overall, best_fitness

print("=== Evolutionäre Architektur-Suche ===")
for task in ["XOR", "CIRCLE"]:
    print(f"\n--- {task} ---")
    best_config, fitness = evolve(task, pop_size=15, generations=4)
    print(f"\nBeste Konfiguration (fitness={fitness:.3f}):")
    for i, (inp, out, act) in enumerate(best_config):
        print(f"  Layer {i}: {inp}→{out} [{act}]")
    print(f"  Parameter: {sum(inp*out for inp,out,_ in best_config)}")

print("\n=== Baseline: relu-only ===")
for task in ["XOR", "CIRCLE"]:
    base = [(2, 4, "relu"), (4, 1, "sigmoid")]
    f = eval_config(base, task, trials=3, epochs=200, lr=0.3)
    print(f"  {task}: relu-baseline = {f:.3f}")

print("\n=== Baseline: oa_ripple-only ===")
for task in ["XOR", "CIRCLE"]:
    base = [(2, 4, "oa_ripple"), (4, 1, "sigmoid")]
    f = eval_config(base, task, trials=3, epochs=200, lr=0.3)
    print(f"  {task}: oa_ripple-baseline = {f:.3f}")
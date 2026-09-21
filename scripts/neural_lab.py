#!/usr/bin/env python3
"""
neural_lab.py — OpenAmer Neural Architecture Lab
Reines Python, kein PyTorch/TF. Für CPU-Forschung.
Neue Aktivierungen, Architekturen + Backprop.
"""
import math, random, json, time, sys
from dataclasses import dataclass, field
from typing import Callable

# ========= AKTIVIERUNGSFUNKTIONEN =========

def sigmoid(x): return 1.0 / (1.0 + math.exp(-max(-100, min(100, x))))

def relu(x): return max(0.0, x)

def gelu(x):
    return 0.5 * x * (1.0 + math.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x**3)))

# ===== NEU: Erfundene Aktivierungen =====

def oa_swish(x):
    return x * sigmoid(x) * (1.0 + 0.1 * math.sin(x))

def oa_hexp(x):
    if x >= 0: return gelu(x)
    return -0.1 * math.exp(-x) * x * x

def oa_ripple(x):
    return math.sin(x) * sigmoid(x)

ACTIVATIONS = {
    "sigmoid": sigmoid, "relu": relu, "gelu": gelu,
    "oa_swish": oa_swish, "oa_hexp": oa_hexp, "oa_ripple": oa_ripple
}

# ========= LAYER MIT BACKPROP =========

@dataclass
class Layer:
    weights: list
    bias: list
    activation: str = "relu"
    
    @staticmethod
    def create(inputs: int, neurons: int, activation: str = "relu"):
        w = [[random.gauss(0, 1.0/math.sqrt(inputs)) for _ in range(inputs)] for _ in range(neurons)]
        b = [0.0] * neurons
        return Layer(w, b, activation)
    
    def forward(self, inputs: list) -> list:
        act = ACTIVATIONS[self.activation]
        out = []
        for i, (w, b) in enumerate(zip(self.weights, self.bias)):
            z = b + sum(w[j] * inputs[j] for j in range(len(inputs)))
            out.append(act(z))
        return out
    
    def backward(self, inputs: list, grad_output: list, lr: float = 0.01) -> list:
        grad_input = [0.0] * len(inputs)
        for ni, (w, b) in enumerate(zip(self.weights, self.bias)):
            z = b + sum(w[j] * inputs[j] for j in range(len(inputs)))
            if self.activation == "sigmoid":
                s = sigmoid(z); dz = s * (1 - s)
            elif self.activation == "relu":
                dz = 1.0 if z > 0 else 0.0
            elif self.activation == "gelu":
                s2p = math.sqrt(2.0 / math.pi)
                inner = s2p * (z + 0.044715 * z**3)
                th = math.tanh(inner)
                dz = 0.5 * (1 + th) + 0.5 * z * (1 - th**2) * s2p * (1 + 0.134145 * z**2)
            else:
                eps = 1e-6
                fn = ACTIVATIONS[self.activation]
                dz = (fn(z + eps) - fn(z - eps)) / (2 * eps)
            delta = grad_output[ni] * dz
            for ji in range(len(inputs)):
                self.weights[ni][ji] -= lr * delta * inputs[ji]
            self.bias[ni] -= lr * delta
            for ji in range(len(inputs)):
                grad_input[ji] += delta * w[ji]
        return grad_input

# ========= NEURAL NETZ =========

@dataclass
class NeuralNet:
    layers: list[Layer] = field(default_factory=list)
    
    def forward(self, inputs: list) -> list:
        self._cache = [inputs[:]]
        x = inputs
        for layer in self.layers:
            x = layer.forward(x)
            self._cache.append(x[:])
        return x
    
    def train(self, dataset: list, epochs: int = 100, lr: float = 0.1):
        for epoch in range(epochs):
            total_loss = 0.0
            for x, y in dataset:
                pred = self.forward(x)
                loss = sum((pred[i] - y[i])**2 for i in range(len(y)))
                total_loss += loss
                grad = [2 * (pred[i] - y[i]) for i in range(len(y))]
                for li in range(len(self.layers) - 1, -1, -1):
                    grad = self.layers[li].backward(self._cache[li], grad, lr)
            if epoch % 50 == 0:
                print(f"  Epoch {epoch}: loss = {total_loss/len(dataset):.6f}")
    
    def param_count(self) -> int:
        c = 0
        for l in self.layers:
            for w in l.weights:
                c += len(w)
            c += len(l.bias)
        return c

# ========= NEUARTIGE ARCHITEKTUR =========

class OscillatingResNet:
    def __init__(self, dim: int, blocks: int = 3):
        self.blocks = []
        for _ in range(blocks):
            b = [Layer.create(dim, dim, "oa_ripple"), Layer.create(dim, dim, "oa_ripple")]
            self.blocks.append(b)
        self.output = Layer.create(dim, 1, "sigmoid")
    
    def forward(self, x: list) -> list:
        h = x[:]
        for l1, l2 in self.blocks:
            skip = h[:]
            h = l1.forward(h)
            h = l2.forward(h)
            h = [skip[i] + 0.3 * h[i] for i in range(len(x))]
        return self.output.forward(h)

# ========= EVOLUTIONÄRE SUCHE =========

@dataclass
class Genome:
    layers: list[dict]
    fitness: float = 0.0
    
    def build(self) -> NeuralNet:
        net = NeuralNet()
        for cfg in self.layers:
            net.layers.append(Layer.create(cfg["inputs"], cfg["neurons"], cfg["activation"]))
        return net
    
    def mutate(self):
        cfg = random.choice(self.layers)
        if random.random() < 0.3:
            cfg["activation"] = random.choice(list(ACTIVATIONS.keys()))

def random_genome(input_size: int, output_size: int) -> Genome:
    layers = []
    size = input_size
    for _ in range(random.randint(1, 4)):
        next_size = random.choice([size, size*2, size//2+1])
        if next_size < 1: next_size = 1
        layers.append({"inputs": size, "neurons": next_size, "activation": random.choice(list(ACTIVATIONS.keys()))})
        size = next_size
    layers.append({"inputs": size, "neurons": output_size, "activation": "sigmoid"})
    return Genome(layers)

def evaluate(genome: Genome, dataset: list) -> float:
    net = genome.build()
    total_loss = 0.0
    for x, y in dataset:
        p = net.forward(x)
        total_loss += sum((p[i] - y[i])**2 for i in range(len(y)))
    return -total_loss / len(dataset)

def evolve(input_size: int, output_size: int, dataset: list, pop_size: int = 10, gens: int = 3) -> Genome:
    pop = [random_genome(input_size, output_size) for _ in range(pop_size)]
    for gen in range(gens):
        for g in pop:
            g.fitness = evaluate(g, dataset)
        pop.sort(key=lambda g: -g.fitness)
        survivors = pop[:3]
        children = []
        for _ in range(pop_size - 3):
            c = Genome([dict(cfg) for cfg in random.choice(survivors).layers])
            c.mutate()
            children.append(c)
        pop = survivors + children
        print(f"  Gen {gen+1}: Best = {pop[0].fitness:.4f} ({len(pop[0].layers)} layers)")
    return pop[0]

# ========= DEMO =========

if __name__ == "__main__":
    print("=== Neural Lab — Aktivierungen ===")
    for name, fn in ACTIVATIONS.items():
        v = [fn(x) for x in [-2, -1, 0, 1, 2]]
        print(f"  {name:15s}: {[f'{x:.3f}' for x in v]}")
    
    xor = [([0,0],[0]), ([0,1],[1]), ([1,0],[1]), ([1,1],[0])]
    
    print("\n=== XOR mit oa_hexp (neue Aktivierung) ===")
    net = NeuralNet()
    net.layers.append(Layer.create(2, 4, "oa_hexp"))
    net.layers.append(Layer.create(4, 1, "sigmoid"))
    for x, y in xor:
        p = net.forward(x)
        print(f"  Vorher: {x} → {p[0]:.4f}")
    net.train(xor, epochs=300, lr=0.5)
    for x, y in xor:
        p = net.forward(x)
        print(f"  Nachher: {x} → {p[0]:.4f} (soll: {y[0]})")
    
    print("\n=== OscillatingResNet (neue Architektur) ===")
    orn = OscillatingResNet(2, blocks=1)
    for x, y in xor:
        p = orn.forward(x)
        print(f"  {x} → {p[0]:.4f}")
    
    print("\n=== Evolution (2 Gen) ===")
    best = evolve(2, 1, xor, pop_size=5, gens=2)
    net = best.build()
    print(f"Beste Architektur: {len(best.layers)} layers, {net.param_count()} params")
    for x, y in xor:
        p = net.forward(x)
        print(f"  {x} → {p[0]:.4f}")
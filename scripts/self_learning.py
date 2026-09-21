#!/usr/bin/env python3
"""OpenAmer Self-Learning: Trainiert oa_ripple-Netz auf Session-Daten."""
import math, random, json, time
from pathlib import Path

def oa_ripple(x):
    return math.sin(x) / (1.0 + math.exp(-max(-100, min(100, x))))

HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
SESSIONS = HOME / "sessions"
STATE_DB = HOME / "state.db"

# Extrahiere Trainingsdaten aus Session-Dumps
def extract_training_data(limit=50):
    """Extrahiert (topic_vector, model_vector) aus Session-Dumps."""
    import sqlite3, json as j
    data = []
    try:
        con = sqlite3.connect(str(STATE_DB))
        cur = con.cursor()
        # Hole Nachrichten mit Rollen
        cur.execute("SELECT role, content, tool_name FROM messages ORDER BY RANDOM() LIMIT ?", (limit,))
        rows = cur.fetchall()
        for role, content, tool_name in rows:
            if not content: continue
            # Feature: Länge, Fragezeichen, Ausrufezeichen, Code-Blöcke, Tool-Aufrufe
            feats = [
                min(1.0, len(content)/500),  # Länge
                1.0 if "?" in content else 0.0,  # Frage
                1.0 if "!" in content else 0.0,  # Ausruf
                min(1.0, content.count("```")/10),  # Code
                1.0 if "python" in content.lower() else 0.0,  # Python
                1.0 if role == "user" else 0.0,  # Nutzer?
                1.0 if tool_name else 0.0,  # Tool-Call?
            ]
            label = 1.0 if role == "assistant" else 0.0
            data.append((feats, [label]))
        con.close()
    except Exception:
        pass
    return data

def train_self(data, epochs=200, lr=0.3):
    """Trainiert oa_ripple-Netz auf Session-Daten."""
    if len(data) < 4:
        print("  Nicht genug Daten (min 4)")
        return None
    
    input_size = len(data[0][0])
    r = random.Random(42)
    w1 = [[r.gauss(0, 0.5) for _ in range(input_size)] for _ in range(6)]
    b1 = [0.0]*6
    w2 = [[r.gauss(0, 0.5) for _ in range(6)] for _ in range(1)]
    b2 = [0.0]
    
    for ep in range(epochs):
        loss = 0.0
        for x, y in data:
            h = [oa_ripple(b1[i] + sum(w1[i][j]*x[j] for j in range(input_size))) for i in range(6)]
            o = [1.0/(1.0+math.exp(-(b2[0] + sum(w2[0][i]*h[i] for i in range(6)))))]
            loss += (o[0] - y[0])**2
            dz2 = 2*(o[0]-y[0]) * o[0]*(1-o[0])
            for i in range(6):
                w2[0][i] -= lr * dz2 * h[i]
            b2[0] -= lr * dz2
            for i in range(6):
                z1 = b1[i] + sum(w1[i][j]*x[j] for j in range(input_size))
                eps = 1e-6
                dz1 = (dz2 * w2[0][i]) * ((oa_ripple(z1+eps)-oa_ripple(z1-eps))/(2*eps))
                for j in range(input_size):
                    w1[i][j] -= lr * dz1 * x[j]
                b1[i] -= lr * dz1
        if ep % 50 == 0:
            print(f"  Ep {ep:3d}: loss = {loss/len(data):.6f}")
    
    # Forward-Klassifikation
    print("\n  Gelernte Muster:")
    for i, (x, y) in enumerate(data[:5]):
        h = [oa_ripple(b1[i] + sum(w1[i][j]*x[j] for j in range(input_size))) for i in range(6)]
        o = [1.0/(1.0+math.exp(-(b2[0] + sum(w2[0][i]*h[i] for i in range(6)))))]
        print(f"  Sample {i}: pred={o[0]:.3f} true={y[0]} feats={[f'{v:.2f}' for v in x]}")
    
    return (w1, b1, w2, b2)

if __name__ == "__main__":
    print("=== ASI Self-Learning: Session-Daten → Neuronales Netz ===")
    data = extract_training_data(limit=80)
    print(f"Extrahiert: {len(data)} Trainingssamples")
    if len(data) >= 4:
        print(f"Features: {len(data[0][0])} Pro Sample")
        result = train_self(data, epochs=300, lr=0.3)
        if result:
            print("\n✅ Training abgeschlossen — oa_ripple hat gelernt")
    else:
        print("⚠️ Nicht genug Session-Daten")
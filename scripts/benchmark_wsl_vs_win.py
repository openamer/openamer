#!/usr/bin/env python3
"""Vergleicht Python 3.14 (WSL Ubuntu) vs Python 3.11 (Windows) für OpenAmer-Aufgaben."""
import time, json, math, statistics

def benchmark_cpu(seconds=3):
    """CPU-intensive Aufgabe: Primzahlen + SHA256 + Matrix-Multiplikation"""
    start = time.time()
    count = 0
    results = {}
    
    # 1) Primzahlen zählen
    t0 = time.time()
    n = 200000
    sieve = [True] * (n + 1)
    for i in range(2, int(n**0.5) + 1):
        if sieve[i]:
            for j in range(i*i, n + 1, i):
                sieve[j] = False
    primes = [i for i in range(2, n + 1) if sieve[i]]
    results["primes_upto_200k"] = f"{len(primes)} primes in {time.time()-t0:.3f}s"
    
    # 2) SHA256 Hashing
    t0 = time.time()
    import hashlib
    for i in range(50000):
        hashlib.sha256(f"openamer-asi-data-{i}".encode()).hexdigest()
    results["sha256_50k_hashes"] = f"{time.time()-t0:.3f}s"
    
    # 3) JSON parse/generate
    t0 = time.time()
    data = {"items": [{"id": i, "value": math.sin(i), "data": list(range(100))} for i in range(500)]}
    serialized = json.dumps(data)
    for _ in range(50):
        json.loads(serialized)
    results["json_500_items_50x"] = f"{time.time()-t0:.3f}s"
    
    total = time.time() - start
    results["total"] = f"{total:.3f}s"
    return results

if __name__ == "__main__":
    import sys
    py_version = sys.version.split()[0]
    import platform
    system = platform.system()
    
    print(f"🏁 OpenAmer Benchmark — Python {py_version} on {system}")
    print(f"{'='*50}")
    
    results = benchmark_cpu()
    
    for name, val in results.items():
        icon = "⚡" if "total" in name else "📊"
        print(f"  {icon} {name}: {val}")
    
    # Score: normalisiert auf 1.0 = Windows 3.11 Referenz
    total_time = float(results["total"].replace("s", ""))
    print(f"\n{'='*50}")
    print(f"✅ Benchmark abgeschlossen in {total_time:.2f}s")
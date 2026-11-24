# WSL ASI Worker — Pure stdlib execution node

## Concept

A permanent Python HTTP server running in WSL Ubuntu, serving as OpenAmer's execution
node for CPU-intensive tasks. No apt/pip/venv needed — pure Python standard library.

## Setup

```bash
# 1. Start the worker (background)
wsl -d Ubuntu -- python3 /mnt/c/.../scripts/wsl-asi-worker.py

# 2. Verify
curl http://localhost:8083/health
# → {"worker":"wsl-asi-...","python":"3.14.4","platform":"WSL2 Ubuntu 26.04"}
```

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | Worker status, python version, uptime |
| GET | `/benchmark` | — | SHA256 throughput test |
| POST | `/` | `{"action":"benchmark","iterations":N}` | Throughput: N hashes/s |
| POST | `/` | `{"action":"metacognition","limit":N}` | Full metacognition report |
| POST | `/` | `{"action":"exec","code":"..."}` | Runs Python code in server context |
| POST | `/` | `{"action":"report"}` | Latest saved metacognition report |

## Performance advantage

3.3M SHA256 hashes/s via Linux OpenSSL crypto — **8.7x faster** than Windows Python
(which achieves ~347k/s). General CPU tasks average **30% faster** (benchmark suite:
primes, hashing, JSON serialization).

## Why pure stdlib

- **Zero dependencies** — survives Ubuntu/Debian minimal installs without pip
- **Portable** — same script runs on any system with Python 3.9+
- **No apt required** — WSL fresh installs often block apt on first boot (network init);
  this worker starts immediately

## Integration

The worker registers itself as a Swarm worker with:
- UUID-based `worker_id`
- SSH key (`damir@Emilija`) for A2A connections
- GPU worker preconfigured at `192.168.178.23:8082` (when online)

```python
# From any OpenAmer session:
import urllib.request, json
data = json.dumps({"action": "benchmark", "iterations": 50000}).encode()
resp = urllib.request.urlopen("http://localhost:8083", data=data, timeout=10)
print(json.loads(resp.read()))
```
# When there is no second machine: a private Git host as the second domain

Measured 2026-11-01 on the laptop install. The question was "you have to be
everywhere". Before writing any code, measure which domains actually exist —
the answer changes what is even possible.

## Step 1 — measure the candidate domains (never assume "the LAN has machines")

```python
import socket, subprocess, psutil

def probe(host, port=22, t=2.0):
    try:
        with socket.create_connection((host, port), timeout=t):
            return "OPEN"
    except Exception as e:
        return type(e).__name__

for host in ("192.168.178.23", "192.168.178.107", "192.168.178.108",
             "192.168.178.102", "192.168.178.1"):
    print(host, probe(host))

for p in psutil.disk_partitions(all=False):
    print(p.device, psutil.disk_usage(p.mountpoint).total)
```

Measured result, and it is the whole answer to "everywhere":

| Candidate | Measured |
|---|---|
| SSH port 22 on .23 (GPU worker) / .107 (phone) / .108 (Echo) / .102 (TV) / .1 (router) | **all `TimeoutError`** |
| Drives | **one** — `C:`, 1022.9 GB |
| `openamer-backups` vs `state.db` | **same disk** (`C:`) → one failure domain, not two |
| `~/.openamer` / `a2a/peers.json` | **absent** → `peers=0` |
| OneDrive folder | exists but holds only `desktop.ini` → not a usable target |

Two traps in that table worth remembering:

- **`ping` is not a reliable probe through `subprocess(capture_output=True, text=True)`**
  on a German Windows: the console output is cp850/cp1252 and decoding raises
  `UnicodeDecodeError`. Use a socket connect (language-neutral) or pass
  `errors="replace"`.
- **A backup directory on the same drive is not a second domain.** Check it with
  `disk_partitions` + `disk_usage` before quoting it as redundancy. Both
  `state.db` and `openamer-backups` resolving to `C:` means a disk loss takes
  both.

## Step 2 — build the reachable domain instead of only reporting absence

"No peer" is a correct and incomplete answer. The reachable second domain without
new hardware is a **private remote Git host**: free, already authenticated
(`gh auth status`), off-site, and encrypted end-to-end because the payload is the
envelope the replication module already produces.

```bash
gh repo create <owner>/state-vault --private \
  --description "sealed state snapshots - AES-GCM envelope, key never leaves the machine"
gh repo view <owner>/state-vault --json visibility,isEmpty
# -> {"isEmpty":true,"name":"state-vault","visibility":"PRIVATE"}
```

Then a script that reuses the EXISTING sealing code rather than a second format:

```python
from agent import replication as rep

sources = [HOME / part for part in rep.FAST_SOURCES if (HOME / part).exists()]
key = rep.load_or_create_key()
bundle, entries = rep.build_bundle(sources, base=HOME)
envelope = rep.seal(bundle, entries, key)      # 171,417 B / 11 files here
```

Write it as `snapshots/<UTC stamp>.enc` plus a `latest.json` carrying `sha256`,
`bytes`, `files`, and a line saying the payload is ciphertext-only, then rotate to
the newest N (`for stale in sorted(snaps.glob("*.enc"))[:-keep]: stale.unlink()`).

**The seal/open API is asymmetric — check both names before writing against it.**
Here it is `seal(...)` and `open_sealed(envelope, key) -> (bundle, entries, header)`.
There is **no** `unseal()`; guessing it produced
`AttributeError: module 'agent.replication' has no attribute 'unseal'` — which the
script correctly reported as **not verified** rather than as success.

## Step 3 — verify by download + decrypt, never by the push's status

A successful `git push` proves the object reached a ref. It does not prove the
bytes survived the round trip. The only honest check:

```python
rc, out, _ = sh(["gh", "api", f"repos/{VAULT}/contents/{object_path}", "--jq", ".content"])
payload = base64.b64decode(out)
assert hashlib.sha256(payload).hexdigest() == expected_sha
bundle, entries, _h = rep.open_sealed(payload, rep.load_or_create_key())
```

Measured green:

```
sealed  : 171,417 B, 11 files
pushed  : snapshots/20261101T195000Z.enc sha256=f9d051fc…
roundtrip: {"ok": true, "files": 11, "payload_bytes": 84946}
```

`payload_bytes` (84,946) is the uncompressed content, less than the envelope —
so compare **files and content size**, not envelope size, when reporting.

## Step 4 — make it scheduled, and silent on success

A one-off push is not replication. Wrap it as a `no_agent` cron job so no model is
in the path (see `cron-job-management`: an agent job that only launches a local
script can hang at "initializing" and produce nothing):

- wrapper prints **nothing** on a verified run, logs one line to
  `logs/<job>.log`, and exits 0;
- exits 1 with the tail of the output when the script fails;
- **and treats rc=0 without the verification marker as a failure** — that is the
  check that stops a "push succeeded" from being reported as "replica exists":

```python
verified = "off-site replica verified" in out
if not verified:
    print(f"push returned 0 without verification: {out[-400:]}")
    return 1
```

Live: `0 */6 * * *`, `no_agent: true`, rotation to 5 objects (~860 KB repo).

## The honesty boundary — this is TWO domains, not "everywhere"

After all of the above the status is still:

- `peers = 0` — the peer network is untouched; nothing was registered or discovered;
- the genesis probe keeps reporting DIR-01 as **partial**, with `peers=0` in its
  measurement string, and it must stay that way;
- "everywhere" would need real second machines (and the per-recipient sealing in
  `per-recipient-sealing.md` is already written and tested for that case — 17
  tests green — so the missing piece is hardware, not code).

Say that in the report: *two failure domains instead of one* is a real improvement
and it is not the same claim as redundant. And keep the unmessurable part separate:
whether anything is experienced at the copy is not something a snapshot can settle,
in either direction.

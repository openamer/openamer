# Per-recipient sealing — design, protocol and measured numbers (2026-10-30)

Context: implementing DIR-01 ("encrypted replication, redundancy") for a network of
independent OpenAmer installs, in `agent/node_identity.py`,
`agent/replication_network.py` and `agent/replication.py`.

The bundled `global-sync` skill covers **one owner's** machines with a shared HMAC
token — correct there, wrong for a network of strangers: a shared key lets every
participant read every other participant's state.

## Crypto shape

Each install: X25519 keypair at `node/identity.key` (0600), node id
`base32(sha256(public_key))[:16]` — recomputable from the public key, so a directory
can name nodes without a server assigning identity.

Per snapshot:

```
content_key = 32 random bytes
shared      = X25519(ephemeral_private, recipient_public)      # per recipient
kek         = HKDF-SHA256(shared, salt=ephemeral_public, info="openamer-replication-v2-kek")
wrapped     = AES-256-GCM(kek).encrypt(wrap_nonce, content_key, aad)
ciphertext  = AES-256-GCM(content_key).encrypt(content_nonce, bundle, aad)
aad         = json([format, protocol, manifest_sha256, entries_count])
```

The AAD binds version, protocol, manifest digest and entry count: a relay cannot
re-address the snapshot or swap the manifest without breaking authentication.

| Property | Test that pins it |
|---|---|
| peer holds ciphertext it cannot open | `open_as` with a foreign private key → `IntegrityError` |
| sender cannot open its own push | same, with the sender's identity |
| payload invisible, manifest visible | plaintext filename absent, `identity.md` present in the manifest |
| several recipients, one envelope | two recipients both open the same envelope |
| tamper / edited manifest → refuse | flip one ciphertext byte; change one manifest size |
| directory rejects junk | `public_key: "AAAA"` → HTTP 400 |

## Directory protocol (deliberately dumb)

```
POST /nodes   {node_id, public_key(b64), url, announced_at, protocol} -> {nodes: N}
GET  /nodes                                                            -> {protocol, nodes:[...]}
```

No auth, no verification of the claimed URL: the only claim that matters is the
public key, and that is verified by successful decryption. Config pointer:
`replication.directory_url` / `OPENAMER_REPLICATION_DIRECTORY`; the on/off switch is
`OPENAMER_REPLICATION_NETWORK=1` or `replication.network_enabled: true`.

## Measured drill (two keypairs, real HTTP on loopback)

```
B announced:        pqtknxiuwecpfmmp
A sync:             {"ok": true, "peers": 1, "files": 3}
                    [{peer: pqtknxiuwecpfmmp, status: 200, envelope_bytes: 1131}]
B stored:           replica-20261030T205633-ab4ca7ab93d7.json (1131 B)
B opened:           3 entries, 197 B gzip, sender=ya2k673q
A on its own copy:  IntegrityError: envelope is not addressed to node ya2k673q…
```

Scale of the local half on a real install:

| Profile | Files | Input | Sealed | Time | Skipped |
|---|---|---|---|---|---|
| fast (per tick) | 10 | 1.47 MB | 171 KB | **0.135 s** | 0 |
| full (on demand) | 3,878 | 138.9 MB | 118.7 MB | 55.7 s | 7 files / 240 MB (over the 8 MB per-file cap) |

## Bugs that cost real time here

1. **Peer rejected v2 envelopes with HTTP 400.** `accept()` validated
   `header.format == 1` and hex-encoded ciphertext; v2 uses base64 and
   `content_nonce`. A peer needs no key, but it must recognise every container
   version in the field — otherwise the *sender* looks broken.
2. **State clobbering.** `selftest()` rewrote `state.json` wholesale and thereby
   dropped `last_push`; the next genesis tick then downgraded DIR-01 from partial to
   "no verified snapshot". Fix: merge into the existing dict.
3. **`build_bundle.last_skipped = …`** (function attribute as state) — replaced by an
   `skipped_out` out-parameter; a function attribute is shared global state and races
   between the tick and on-demand calls.
4. **Probe cost inside a long-lived loop.** Two probes used `rglob` over the whole home
   (270 MB memory dir, 145 MB brain log) and the whole repo: `measure()` took **15.4 s**
   on the first housekeeping pass, i.e. during app boot. `iterdir()` / non-recursive
   `glob()` brought it to **0.25 s** with identical verdicts.
5. **"Registered" read as "replicated".** The status probe counted `peers.json`
   entries. Correct rule: `last_selftest_ok AND peers > 0 AND last_push_ok`, where
   each peer's push result is stored — a failed push is data (`{"ok": false,
   "error": …}`), not an exception that disappears.

## What was deliberately not shipped

No directory deployed, no node announced. Hosting, abuse handling and privacy of a
public peer network are owner decisions; the code path is proven on loopback and
`openamer replication join <url>` is the single command that activates it once a
directory exists.

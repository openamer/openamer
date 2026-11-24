---
name: encrypted-state-replication
description: "Replicate state between untrusted machines."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [replication, encryption, peers, directory, backup]
    related_skills: [global-sync, agent-mesh, ssh-manager]
---

# Encrypted state replication between machines that do not trust each other

Use when state has to survive more than one machine — snapshots to a peer, a
network of independent installs, or any answer to "can this outlive my laptop?".
The bundled `global-sync` covers **one owner's** machines with a shared token;
this skill covers the harder case: peers that must hold a copy **without being able
to read it**, and the measurement rules that keep "replicated" honest.

Full design, protocol and measured numbers: `references/per-recipient-sealing.md`.

## Two halves, and only one of them is code

DIR-01-style goals ("encrypted replication, existence redundant") split cleanly:

1. **The artifact** — a snapshot that is encrypted, authenticated and *provably
   restorable*. Buildable on one machine, and it must be proven on every tick.
2. **The other machine** — a reachable peer. Not buildable in code; it is an address,
   a credential and a failure domain. Until one exists, the honest status is
   `peers=0`, not "done".

Never let half 1 stand in for half 2, and never let a *registered* peer stand in for
a *delivered* copy.

**When no second machine exists, build the reachable domain — don't stop at
`peers=0`.** Measure first (socket probe on port 22 for every LAN host,
`psutil.disk_partitions` to prove the "backup" sits on the same disk, whether
`a2a/peers.json` exists at all), then use the one off-site domain that needs no
hardware: a **private** Git repo holding the same sealed envelope, verified by
downloading the object back and decrypting it — a push's HTTP 200 is not proof.
That raises the count from one failure domain to two and is still not "everywhere":
`peers` stays 0 and the status probe must keep saying so. Measurement table, the
seal/open API asymmetry, and the silent scheduled wrapper:
`references/offsite-replica-private-git-host.md`.

## The minimum bar for the artifact

- **AEAD, not hand-rolled.** AES-256-GCM from `cryptography`; a missing library is a
  hard error, never a custom cipher. Key = 32 random bytes, 0600, or scrypt-derived
  from a passphrase.
- **Authenticated manifest.** Every file carries its sha256; the manifest digest is
  bound into the associated data, so an edited or truncated envelope fails *before*
  anything is written to disk.
- **Defensive restore.** Reject absolute paths, `..` components and drive letters;
  extract into a staging dir; re-verify every hash before copying out.
- **Bounded by construction** (`bounded-archive` rule): exclude `.env`, `*.key`,
  `*.pem`, the multi-GB state DB and any single file over a cap — and *record* the
  skipped ones so the archive is honestly incomplete instead of silently short.
- **Self-test with a real restore**, not just "it encrypted". The cheap profile must
  stay under a second (~1.5 MB → 0.14 s) so it can run on every tick; the full profile
  (139 MB, ~56 s here) is on demand.

## Replication between strangers: per recipient, not shared

A shared key means every participant can read every other participant. Instead: one
random content key per snapshot, wrapped **individually** for each recipient
(X25519 → HKDF-SHA256 → AES-GCM), with the manifest digest as AAD. Properties worth
testing explicitly:

- the **sender** cannot open the copy it pushed;
- a third install and the relay cannot;
- the peer stores it with **no key at all** — that is what makes the copy useful;
- wrong recipient, tampered ciphertext, edited manifest → refuse.

Discovery is a directory of `{node_id, public_key, url}` behind `POST/GET /nodes`.
It only has to say who exists; the public key is verified by decryption, so the
directory needs no trust. Ship the client and prove it on loopback — deploying a
public directory (hosting, abuse, privacy) is the owner's decision, not a code step.

## Consent and honesty rules

- Networking to strangers is **opt-in** and reports `enabled: false` by default, with
  a test asserting that default.
- Plain HTTP to a non-loopback host is refused, not warned about: the payload is
  encrypted, the metadata (who replicates to whom) is not.
- The probe that feeds a status table must require **both** halves —
  `verified snapshot AND successful push to every registered peer`. Registered but
  unreachable is `partial` with the reason.
- Pushing a snapshot of an install is not a backup strategy on its own: a copy on the
  same disk is not a second failure domain. Say which one exists.

## Pitfalls

- **A peer's validator must accept every envelope version in the field.** A peer that
  only recognised v1 answered 400 to every v2 push; it needs no key, but it does need
  to recognise the container.
- **A function attribute as state is a bug** (`build_bundle.last_skipped = …`) — pass
  an out-parameter instead; concurrent ticks race otherwise.
- **Merge, don't overwrite** the persisted state: a self-test that rewrites
  `state.json` drops the recorded push and silently downgrades the status on the next
  tick.
- **Measure the probe's cost.** A tick runs inside a long-lived process; two probes
  that walked whole trees made it 15.4 s at app start. `measure()` after the fix:
  0.25 s.

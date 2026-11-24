---
name: firmware-artifact-triage
description: "Use when a firmware blob may be encrypted, not packed."
metadata:
  openamer:
    tags: [firmware, entropy, carving, encryption, vendor-container, reverse-engineering]
    category: reverse-engineering
    related_skills: [openamer-reverse-engineer, codebase-inspection]
---

# Firmware / opaque-blob triage

Use this when you hold a vendor image — TV, router, camera, set-top box — and the
question is **"what is in it, and can I read or change it?"** The deliverable is a
verdict backed by measurements, not an attempt to unpack something that cannot be
unpacked.

The failure this skill prevents: sampling a file a few times, seeing ~7.8 bits/byte
everywhere, and writing "encrypted, nothing to see" — while the file actually has
dozens of sections with recoverable boundaries. Six samples are not a survey.

## Order of work

### 0. Try the real analyser first, and read its refusal correctly

Point `openamer re` / REA at it before hand-rolling anything. A vendor container
is not a format it knows, and it says so precisely:

```json
{"error":{"code":"target_unavailable","category":"unsupported_target",
 "message":"Cannot open artifact: unsupported binary format.",
 "details":{"reason":"unsupported binary format","constraint":"file_format_rejected"}}}
```

That is a **format** finding, not a broken tool. Prove the tool works by running it
on a control target in the same session (a `.pyc`, the archive inside the vendor
wrapper) and quote its coverage. Then do the structural work yourself.

### 1. Identify the outer container

Read the first 64 KiB and test magics (the script does this):

| magic | meaning |
|---|---|
| `PK\x03\x04` | ZIP — list members, recurse into each |
| `\x1f\x8b` | gzip stream |
| `hsqs` / `sqsh` | squashfs — extractable |
| `#UBI` / `UBI#` | UBI/UBIFS — extractable |
| `\x45\x3d\xcd\x28` | cramfs |
| `\x53\xef` | ext2/3/4 superblock |
| `\x7fELF` | ELF executable/library |
| `\x27\x05\x19\x56` | uImage (U-Boot) |
| `ANDROID!` | Android boot image |
| `\xd0\x0d\xfe\xed` | device tree blob |

A ZIP wrapper is normal for vendor firmware and is the easy layer: the inner file
is where the work is.

### 2. Entropy — sweep the WHOLE file, never sample it

Compute Shannon entropy per fixed window (64 KiB is a good default) across the
entire payload and report the **transitions**, not a handful of points. On a real
593 MB Philips package, five spread samples all read 7.77–7.78 ("uniform,
encrypted"); the full sweep found **101 transitions — 51 low-entropy gaps and 50
dense sections**. The structure was there the whole time; the sampling hid it.

### 3. Distinguish "packed" from "encrypted"

This decides whether the job is possible at all. Run all of these:

- **Decompressor probes** on deep samples: `zlib.decompressobj()`, `bz2.BZ2Decompressor`,
  `lzma.LZMADecompressor`. If every one fails on every sample, it is not one of the
  common compression formats.
- **Magic census across the entire payload** — count occurrences of `hsqs`, `#UBI`,
  `\x27\x05\x19\x56`, `ANDROID!`, `\x1f\x8b\x08`, `BZh9`, `\xfd7zXZ`, `ustar`.
  Zero filesystem magics in the whole file is the strongest single signal: a real
  filesystem or kernel image would leave at least one header.
- **Block uniqueness**: count distinct 16-byte blocks in a 512 KiB sample. Encrypted
  data is ~all unique (`32767 / 32768`); compressed data also looks unique, so this
  separates you from *trivially* structured data but not from compression — hence
  the probes above.

Call it **encrypted** only with all four agreeing. One high-entropy sample is not a
verdict.

### 4. Parse whatever plaintext exists

Vendor containers usually keep a table of contents in clear even when the payload is
sealed. Look for ASCII runs and parse them: a `START` … `END` block with
newline- or space-separated `name / device / offset` triplets gives you the partition
map (`uenv`, `kerA`, `kerB`, `rfsA`, `rfsB`, `3rdA`…). Report it — it names what the
device runs, even when you cannot read a byte of it.

Also count the readable strings. "11 readable strings in 1.7 MB" is a much stronger
statement about a plaintext head than "looks binary".

### 5. Carve sections from the entropy gaps

Low-entropy gaps between dense regions are boundaries. Verify what they are before
calling them headers:

- A **degenerate repeating pattern** (`df 80 → 6f c0 → 37 e0 → 1b f0 …`, one bit
  right per step) is padding, not metadata.
- Gaps that **differ from each other** are per-section trailers/padding of distinct
  blocks, still not headers unless they parse.

Then report sizes, because sizes carry meaning: repeated identical sizes reveal the
A/B partition scheme (four sections at exactly 25.00 MiB, four at 16.62 MiB = kernel
and rootfs pairs).

### 6. State the verdict in the user's terms

| finding | what to say |
|---|---|
| squashfs/UBI/ELF magics found | "extractable — here are the filesystems" |
| compressed, no encryption | "packed, decompress with X" |
| all four encryption signals | "encrypted; readable structure, unreadable code" |
| signature + per-partition hashes present | add: "a repack is rejected by the device, and flashing a modified image bricks it" |

Never soften this into "the tool can't do it". The honest sentence is: *the payload
is encrypted, the key is the vendor's, and no analyser turns that into source.*

## Pitfalls

- **Sampling instead of sweeping.** The single most expensive mistake in this class.
  Five points said "uniform"; the sweep found 50 sections.
- **`\x53\xef` false positives.** That two-byte pattern occurs ~19 000 times by
  chance in 593 MB. An ext superblock is at a 1024-aligned offset with a plausible
  `s_log_block_size`; a raw byte count proves nothing.
- **High entropy ≠ encrypted.** Compressed and encrypted data both look flat. Run the
  decompressors before you claim crypto.
- **A vendor device's HTTP 200 is not proof of effect.** The same reflex as the blob
  work, one layer up: read state back instead of trusting the acknowledgement.
  Measured on the device whose firmware this skill came from — a volume write answered
  `200 OK` and changed nothing, and a launch endpoint answered `200` while the screen
  never changed. See the recipe below.
- **Do not promise source recovery.** REA and every peer analyser retain bytecode as
  length + hash; none decompile to source. On an encrypted image there is nothing to
  decompile in the first place.
- **Delete the throwaway probes** (scan scripts, temp HTML) before reporting, or the
  change tracker will list files that no longer exist.

## Proving the device acted — and the trap that looks like success

When you need evidence that a remote device (TV, camera, speaker) actually performed
the action, do not read the API's acknowledgement. Two methods, in order:

**1. Read the state back.** Re-query the thing you changed. If it did not move, the call
was a no-op regardless of the 200. Poll for the target value in ~0.5 s steps rather than
sleeping a fixed time — command application on embedded devices lags 1–3 s and is
sometimes dropped entirely.

**2. Make the device call YOU.** For "did it open this URL / fetch this media", serve a
tiny HTTP handler on the LAN and point the device at it. A request in the log proves the
action end-to-end: it resolved the host and fetched. Then read the log line carefully:

```
2026-11-01 17:09:19  192.168.1.104  /selftest   UA=curl/8.19.0
2026-11-01 17:10:26  192.168.1.104  /test.mp4   UA=… Chrome/136.0.0.0 …
```

Both of those came from **the laptop itself** — its own curl, and its own browser hitting
the page during an unrelated step. A log line is not the device until the **source
address AND the User-Agent** both fit it; a TV usually reports an embedded UA
(`Mozilla/5.0 (Linux; Android …) PhilipsTV`), not a desktop browser.

Three prerequisites decide whether this test can work at all:

- **A free port.** Probe it first (`socket.connect_ex`). A server that prints
  `listening on 0.0.0.0:PORT` may not own the port — on Windows `SO_REUSEADDR` lets a
  second bind succeed silently and traffic goes to the other process. Mechanism and the
  `allow_reuse_address = False` fix: `windows-python-service-ops`.
- **The right interpreter path.** Windows Firewall rules are *path*-bound: an `Allow`
  rule for `…\cpython-3.x.y-…\pythonw.exe` does nothing for `…\cpython-3.x-…\` or for
  `python.exe`. Start the listener under the exact path an existing rule covers.
- **Same subnet, no client isolation.** Many routers block device→laptop while
  laptop→device works fine, so "my request reached the TV" proves nothing about the
  reverse direction.

If none of it lands, say so plainly: *the API accepted the command, the device fetched
nothing, and I cannot see the screen — the effect is unverified.* A failed verification
is a measurement, not a licence to claim success.

## Re-runnable

`scripts/blob_triage.py <file>` performs steps 1–5 in one call: container magic,
entropy sweep with transitions, magic census over the whole payload, decompressor
probes, plaintext string count, and a verdict line. Writes `sections.json` beside
the file when gaps are found.

```bash
python scripts/blob_triage.py upgrade_demo.pkg
```

Measured reference case (Philips 58PUS6203 Saphi/MT5802, 593,936,204 bytes):
ZIP → single `.pkg`; 24 partitions in a plaintext TOC; 50 dense sections; payload
entropy 7.777 with 32 767/32 768 unique 16-byte blocks; zero squashfs/UBI/uImage
hits; no decompressor succeeds → **encrypted**.

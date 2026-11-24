# Quality-gate fixture & delta hygiene (live 16.09.26)

Session detail behind the "Classes 17–18" and fixture/CRLF/pre-existing-failure
pitfall entries in SKILL.md. Every string below was **actually stored as an
insight** by a learning cycle unless marked as a counter-case.

Note on numbering: the third shape below (the mid-sentence snippet echo) is
already carried in SKILL.md as **class 13** of the leading-chrome STRIP family.
It is reproduced here because this session re-measured its three-condition form
on a ~4870-row corpus; treat `_strip_clock_fragment` as the guard of record.

## Class 17 — Chinese Q&A / answer-portal chrome (REJECT)

Stored verbatim by `cycle_h_efficiency`:

```
CAD看图王 提供 嗨格式 2019-02-19 · 百度认证:苏州舜心科技有限公司 嗨格式 嗨格式是苏州开心盒子
软件有限公司旗下的独立品牌。苏州开心盒子软件有限公司是一家专注软件研发的互联网科技公司。
向TA提问 关注 展开全部 在Word文档中，如何输入像这样可以打勾打叉的方框呢？有不止一种方法能够
输入这样的方框，一起来学习一下。 已赞过 已踩过 你对这个回答的评价是？ 评论 收起 读书小明白
高粉答主 2020-02-14 · 醉心答题，欢迎关注 知道答主 回答量： 12.
```

A Baidu-Zhidao answer-portal scrape, 242 chars, zero technical prose. Both gates
passed it: the badge dates fed the technical-signal gate, the length cleared the
≥90 long-prose trust.

### Marker measurement (over buffer + junk log, 5013 rows)

| Marker | total hits |
|---|---|
| 百度认证 | 1 |
| 高粉答主 | 1 |
| 已赞过 / 已踩过 | 1 each |
| 向TA提问 | 1 |
| 回答量 | 1 |
| 你对这个回答的评价是 | 1 |
| 展开全部 | 1 |
| 经验内容仅供参考 | 4 |
| 本篇经验系本人 | 4 |
| 展开阅读全部 | 4 |
| 作者声明 | 4 |

**Rows with ≥2 markers: 5, every one chrome. Rows with exactly 1 marker: 0.**
So the two-marker threshold has no false-positive risk in this corpus and no
single-marker row to worry about. Genuine Chinese technical rows carry **zero**
markers.

Counter-cases that MUST survive (asserted in the test):

```
LLM Agent 的记忆系统通常分为短期上下文和长期向量存储两层，向量检索的召回率直接决定了长期记忆
在实际任务中的可用性，而短期上下文则受到窗口长度的硬性限制。
```
(a real technical insight, 81 chars → kept at ≥90 in spirit; it survives because
it carries no marker — a *language-based* rule would have eaten it)

and one carrying exactly ONE marker (`作者声明`) inside otherwise genuine prose,
kept at 102 chars **on purpose**: below 90 the pre-existing short-candidate rule
fires first and looks like the new gate misfiring.

## Class 18 — German SaaS pricing/checkout chrome (REJECT)

Stored verbatim by `cycle_c_github` as a "GitHub agent architecture" learning:

```
Bleib flexibel: Monatlich kündbar Lastschrift Kreditkarte Auf Rechnung Jahrespaket 49,50 € / Jahr ~ 4,12 € pro Nutzer und Monat inkl.
```

133 chars of plan-comparison table. Both gates passed: the prices fed the
technical-signal gate (`_TECH_HINT_RE` starts with `\d+`, so `49` and `4` count)
and the length cleared the ≥90 trust.

### Marker measurement (4855 rows)

Each candidate hit exactly ONE row — the leaking row:

| Marker | hits |
|---|---|
| monatlich kündbar | 1 |
| jahrespaket | 1 |
| lastschrift | 1 |
| auf rechnung | 1 |
| pro nutzer und monat | 1 |
| € / jahr | 1 |

**6 marker hits, all in ONE row, 0 real-prose rows.** English twin already in
`buffer_store._NAV_CHROME`: `"billed annually"`.

Counter-cases that must survive:

```
Serving that model costs about 0,002 € per 1k tokens; annualised that is roughly
12 € per agent per month including the vector store overhead.
```
(real prose citing a price, zero billing markers)

```
Die Rechnung wird monatlich kündbar abgerechnet, und die Quantisierung senkt den
Speicherbedarf des 7B-Modells auf etwa vier Gigabyte bei INT4, was die
Inferenzlatenz deutlich reduziert.
```
(exactly ONE billing marker inside real prose)

## Mid-sentence snippet echo (STRIP) — SKILL.md class 13, re-measured here

Stored verbatim by `cycle_f_multi_domain`:

```
at 11:44 am we asked four ai coding agents to In a recent experiment, four AI coding agents were tasked with recreating the classic game Minesweeper, revealing both the potential and limitations of modern AI in programming.
```

The extractor received Bing's snippet opening **mid-sentence** (`… at 11:44 am we
asked four ai coding agents to …`) and prepended it to the article's real first
sentence. Body = everything from `In a recent experiment`.

`_strip_clock_fragment` fires only when ALL THREE hold:

1. text **starts lowercase** (a sentence starts with a capital ⇒ real prose
   excluded by construction)
2. a `<clock> am/pm` marker (`^(?:(?:at\s+)?\d{1,2}:\d{2}\s*(?:am|pm)\.?\s+)`)
3. the real sentence follows **with a capital**

Measured: 1 row touched (the leaking row), body a clean suffix, 4/4 counter-cases
unmodified. Counter-cases (all untouched, all still learnable):

```
At 11:44 am the retriever returned a stale embedding, and the quantization step then masked the drift for three consecutive batches.
The job starts at 11:44 and finishes before the peak; the quantized model keeps peak VRAM under 6 GB while continuous batching holds throughput steady.
at 11:44 the retriever returned a stale embedding; INT4 quantization masked the drift.
11:44 am The job starts and the quantization keeps peak VRAM at 6 GB under INT4 precision.
```

That last pair is why the rule needs **lowercase start**: `At …` and `11:44 am
The …` are ordinary prose and must be left alone.

## Delta hygiene notes

### Verify the delta's hit is YOUR rule

This session's delta for the clock strip reported `stripped rows: 1` — but on
inspection the touched row was an **OWASP nav-stack** row
(`SECURITY resources Whitepapers/Guides …`), stripped by a *sibling cron's* rule
that was uncommitted in the same working tree. `git diff HEAD --
scripts/training/internet_learner.py` showed hunks I had not written
(`_strip_nav_label_stack`). Before attributing a delta row to your change, diff
against HEAD and look for foreign hunks.

The clean-isolation recipe for YOUR rule (from SKILL.md, reproduced):

```python
NEW = load(working_copy, "il_new")
REF = load(working_copy, "il_ref")           # same file, second module instance
assert REF._clean_insight(leak) != ""        # sanity: the strip is active here
REF._strip_clock_fragment = lambda text: (text or "").strip()
```

### Scrub-vs-rewrite: two different scripts

- `scrub_rejected_buffer.py` **DROPS** rows the current gate rejects.
- A strip class needs a **REWRITE** pass instead, with the strict predicate
  `cleaned and len(cleaned) < len(a) and a.endswith(cleaned)` — never
  `_clean_insight(a) != a`, which fires on the 250-char `max_len` truncation
  alone (54 fake hits, measured in an earlier session).

Run order that worked: delta first (proves the rule), then suites, then sync
repo→HOME, then scrub/rewrite, then ONE real `--once` and read the LAST buffer
row to confirm it is on-topic.

## Fixture/CRLF verification snippets

```python
d = io.open(path, "rb").read()
assert d.count(b"\n") - d.count(b"\r\n") == 0      # no lone LFs in a CRLF file
ast.parse(io.open(path, encoding="utf-8").read())   # syntax OK (does NOT catch
                                                    # implicit string concatenation)
```

Adjacent literals in parentheses concatenate — write fixture lists as
`[( "a" ), ( "b" )]` with explicit commas, then assert
`len(_CLOCK_PROSE) == 2 and _CLOCK_PROSE[0] != _CLOCK_PROSE[1]`.

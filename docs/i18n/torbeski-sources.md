# Torbeški (torbeski) — source dossier

Status: **catalog is a documented base, not a finished translation.** This file
records what the sources actually say, what they do not say, and how the locale
was seeded — so the next person (or the next session) does not have to guess or
re-research it.

## What Torbeški is, per the sources

| Claim | Source | What it literally says |
|---|---|---|
| Torbeši speak Macedonian in regional dialect form | `mk.wikipedia.org/wiki/Торбеши` | „…етнички Македонци со исламска вероисповед кои говорат на македонски јазик… Главна одлика за сите нив е што го зборуваат македонскиот јазик во дијалектна форма според регионот во кој живеат." |
| Language listed as Macedonian | `en.wikipedia.org/wiki/Torbeši` (infobox) | `languages: Macedonian` |
| There is a named „торбешка субгрупа" | `mk.wikipedia.org/wiki/Торбеши` (references) | Цитирана дисертација: Паликрушева, Галаба (1965), *Ислаамизацијата на Торбешите и формирање на торбешката субгрупа*, Скопје |
| The Polog (Tetovo/Gostivar) dialects are the relevant group | `mk.wikipedia.org/wiki/Дијалекти_на_македонскиот_јазик` | Тетовски (Долнополошки), Гостиварски (Горнополошки), Рекански, Дебарски, Дримколско-голобрдски — цитирано по Видоески, *Дијалектите*, том 1 (1998), стр. 149–162 |
| The neighbouring Gora speech is „very similar to the Tetovo dialect" and carries Turkisms | `mk.wikipedia.org/wiki/Горански_дијалект` | „…многу сличен со тетовскиот дијалект. Во дијалектот има присуство на турцизми. Во Косово и Македонија, дијалектот се пишува на кирилица, а во Албанија на латиница." |
| A Qur'an translation into Torbeški exists | `mk.wikipedia.org/wiki/Ислам` (references) | „Кур'ан со превод, Превод на македонски/торбешки: Хасан Џило" |

### Authentic running text in the neighbouring variety

The Gora article carries a folk poem in the dialect — the only piece of real
connected text in the sources above:

```
Што се бели, горе Шар планина?
Да л' је снегче, ил' је бело стадо?
Нит' је снегче, нит' је бело стадо.
Да је снегче, би се растопило,
Да је стадо, би се растурило.
Веч тој беше Милкино чадорче,
Под чадорче болна Милка лега.
Брата и гу Турци заробили,
Заробили, пај га обесили.
```

Observed forms that differ from standard Macedonian: `је` (is), `Нит'`
(neither), `Веч` (but/already), `гу` (her), `пај` (then). **Caveat:** this is
Gora (Gorani/Našinski), a neighbour variety — not Torbeši. It is evidence of
how the Šar-region Slavic speech of Muslim communities looks, not a licence to
copy it into a Torbeški catalog.

## What does NOT exist (checked, not assumed)

- **No ISO 639-3 code** for Torbeški. The registry therefore uses the
  standalone code `torbeski`; `mk-torbeski` would be split at the hyphen by
  `agent/i18n._normalize_lang` and silently resolve to Macedonian.
- **No standard written norm.** Cyrillic where written at all; no orthography
  authority.
- **No MT system produces it.** A model asked for "Torbeški" returns Macedonian
  or Bulgarian approximations. This is why nothing in `locales/torbeski.yaml`
  is claimed as a translation.
- **No Torbeški dictionary found.** Route-by-route result:
  - `archive.org` advanced search (`torbeski`, `торбешки`, `nasinski`) → **0 hits**
  - Google Books API → **HTTP 429, daily quota exceeded** (blocked, not empty)
  - DuckDuckGo lite / Mojeek HTML → challenge pages, no result links
  - `web_extract` → backend is search-only in this install
  - Wikipedia search API (mk) → works; that is where every row above comes from
- **Closest verified lexicographic resource is for a different community:**
  Nazif Dokle, *Rečnik Goransko (Nashinski)–Albanski*, Sofia 2007, Bulgarian
  Academy of Sciences (cited by `en.wikipedia.org/wiki/Gora_dialect`). Gorani,
  not Torbeši — usable as a comparison, never as a source of shipped strings.

## Why the catalog is seeded from Macedonian

Torbeši speech **is** a Macedonian dialect group (table above), so Macedonian is
the documented base language, not a placeholder from convenience. The
differences to standard Macedonian are mostly phonological and morphological
(`је/е`, `гу/ја`, `веч/веќе`, `пај/па`), so most UI words are identical and a
minority differ. Where a source-backed dialect form is known, it belongs in the
catalog; where none is known, standard Macedonian is closer to the target
language than English is.

`locales/torbeski.yaml` states this in its own header. The desktop module is
empty on purpose (falls back to English) because the Macedonian desktop module
is an empty stub as well — shipping Macedonian under a Torbeški label would be
the same problem one level deeper.

## Native review workflow

1. `locales/torbeski.yaml` — replace values in place; keys stay unchanged. The
   generator (`scripts/i18n_fill_cli_locales.py`) preserves anything a human
   writes and only re-derives the approval keys (prompt/label/typed-input
   consistency) and the fixed `o/s/a/d` keys of the normal approval prompt.
2. Validators that will reject a bad edit instead of shipping it: placeholder
   parity (`{name}`), bracketed-key parity, hotkey drift, and the approval-key
   invariant covered by `tests/scripts/test_cli_locale_approval_keys.py`.
3. Desktop: `apps/desktop/src/i18n/torbeski.ts` — same `defineLocale({...})`
   shape as every other locale; keys come from `en.ts`.

## Next research steps (not done yet)

- Obtain the Džilo Qur'an translation — the only known large Torbeški text
  corpus; would give real orthography and vocabulary.
- Видоески, *Дијалектите на македонскиот јазик*, том 1 (1998), pp. 149–162 —
  the Polog dialect chapters, the primary linguistic description.
- Паликрушева (1965) — ethnographic, may contain a lexicon appendix.
- A Torbeši speaker (the owner of this install) reviewing a first batch of
  high-traffic strings beats any of the above for accuracy.

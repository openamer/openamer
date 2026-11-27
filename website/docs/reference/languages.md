---
title: Languages
sidebar_label: Languages
description: >-
  Every language OpenAmer ships: 186 locales, measured from the locale data, not advertised.
---

# Languages

OpenAmer ships **186 locales**. Every one of them has a real
catalog in the repository — this page is generated from those files, so the
numbers below are measurements, not marketing.

| Measured fact | Value |
|---|---|
| Locales with a CLI/gateway catalog | 186 |
| Locales registered in the desktop app | 186 |
| Locales with a desktop catalog file | 186 |
| ISO 639-1 two-letter codes covered | 184 |
| Locales outside ISO 639-1 | `torbeski`, `zh-hant` |
| Right-to-left locales | `ar`, `dv`, `fa`, `he`, `ku`, `ps`, `sd`, `ug`, `ur`, `yi` |
| CLI catalogs at ≥90% translated | 174 of 186 |
| CLI catalogs at ≥50% translated | 185 of 186 |
| Desktop catalogs at ≥50% translated | 184 of 186 |

Translation share means: the fraction of values that differ from the English
catalog. A catalog that exists but was never translated counts as 0% here —
declared is not done.

## How a language is measured

1. `locales/_languages.json` declares the advertised set — one entry per locale.
2. `locales/<code>.yaml` is the CLI/gateway catalog, checked key by key against
   `locales/en.yaml` (the baseline).
3. `apps/desktop/src/i18n/<code>.ts` is the desktop catalog; it counts only if
   `languages.ts` registers the code as well.

Nothing on this page is typed by hand: `scripts/build_language_index.py` reads
the three sources and writes this file plus
[`api/languages.json`](/docs/api/languages.json) (`--check` fails when the page
is stale).

## Add or fix a language

```bash
python scripts/build_language_index.py      # regenerate this page + the JSON
python scripts/i18n_audit.py                 # per-catalog translation share
python scripts/i18n_gap_report.py            # what is still English
```

A new language is done when its catalog differs from English, the desktop
`languages.ts` registers the code, and the generated table above shows it.

## The full list

Generated 2026-11-27 from the repository. RTL = right-to-left script.

| Code | Language | English | CLI | Desktop | Dir |
|---|---|---|---|---|---|
| `ab` | Аҧсуа | Abkhazian | 94% | 97% | LTR |
| `aa` | Afaraf | Afar | 95% | 97% | LTR |
| `af` | Afrikaans | Afrikaans | 95% | 94% | LTR |
| `ak` | Akan | Akan | 93% | 96% | LTR |
| `sq` | Shqip | Albanian | 93% | 97% | LTR |
| `am` | አማርኛ | Amharic | 94% | 97% | LTR |
| `ar` | العربية | Arabic | 96% | 99% | RTL |
| `an` | Aragonés | Aragonese | 91% | 96% | LTR |
| `hy` | Հայերեն | Armenian | 95% | 97% | LTR |
| `as` | অসমীয়া | Assamese | 95% | 97% | LTR |
| `av` | Авар | Avaric | 94% | 91% | LTR |
| `ae` | Avesta | Avestan | 94% | 71% | LTR |
| `ay` | Aymar aru | Aymara | 93% | 96% | LTR |
| `az` | Azərbaycan | Azerbaijani | 93% | 96% | LTR |
| `bm` | Bamanankan | Bambara | 95% | 80% | LTR |
| `ba` | Башҡортса | Bashkir | 94% | 97% | LTR |
| `eu` | Euskara | Basque | 93% | 97% | LTR |
| `be` | Беларуская | Belarusian | 94% | 90% | LTR |
| `bn` | বাংলা | Bengali | 94% | 97% | LTR |
| `bh` | भोजपुरी | Bihari | 94% | 97% | LTR |
| `bi` | Bislama | Bislama | 91% | 67% | LTR |
| `bs` | Bosanski | Bosnian | 93% | 98% | LTR |
| `br` | Brezhoneg | Breton | 94% | 96% | LTR |
| `bg` | Български | Bulgarian | 94% | 99% | LTR |
| `my` | မြန်မာ | Burmese | 95% | 87% | LTR |
| `ca` | Català | Catalan | 89% | 94% | LTR |
| `ch` | Chamoru | Chamorro | 93% | 93% | LTR |
| `ce` | Нохчийн | Chechen | 94% | 88% | LTR |
| `ny` | Chichewa | Chichewa | 95% | 90% | LTR |
| `cu` | Словѣньскъ | Church Slavic | 94% | 62% | LTR |
| `cv` | Чӑвашла | Chuvash | 94% | 96% | LTR |
| `kw` | Cornish | Cornish | 92% | 77% | LTR |
| `co` | Corsu | Corsican | 94% | 95% | LTR |
| `cr` | Cree | Cree | 90% | 97% | LTR |
| `hr` | Hrvatski | Croatian | 93% | 98% | LTR |
| `cs` | Čeština | Czech | 93% | 98% | LTR |
| `da` | Dansk | Danish | 92% | 98% | LTR |
| `dv` | ދިވެހި | Divehi | 94% | 65% | RTL |
| `nl` | Nederlands | Dutch | 91% | 98% | LTR |
| `dz` | རྫོང་ཁ | Dzongkha | 95% | 97% | LTR |
| `en` | English | English | 0% | 0% | LTR |
| `eo` | Esperanto | Esperanto | 95% | 98% | LTR |
| `et` | Eesti | Estonian | 94% | 98% | LTR |
| `ee` | Eʋegbe | Ewe | 95% | 97% | LTR |
| `fo` | Føroyskt | Faroese | 94% | 77% | LTR |
| `fj` | Na Vosa Vakaviti | Fijian | 95% | 97% | LTR |
| `fi` | Suomi | Finnish | 95% | 98% | LTR |
| `fr` | Français | French | 96% | 92% | LTR |
| `ff` | Fulfulde | Fulah | 94% | 97% | LTR |
| `gl` | Galego | Galician | 93% | 96% | LTR |
| `lg` | Luganda | Ganda | 74% | 93% | LTR |
| `ka` | ქართული | Georgian | 95% | 96% | LTR |
| `de` | Deutsch | German | 95% | 97% | LTR |
| `el` | Ελληνικά | Greek | 95% | 99% | LTR |
| `gn` | Avañe\'ẽ | Guarani | 90% | 80% | LTR |
| `gu` | ગુજરાતી | Gujarati | 95% | 72% | LTR |
| `ht` | Kreyòl ayisyen | Haitian Creole | 93% | 97% | LTR |
| `ha` | Hausa | Hausa | 93% | 93% | LTR |
| `he` | עברית | Hebrew | 94% | 96% | RTL |
| `hz` | Otjiherero | Herero | 93% | 75% | LTR |
| `hi` | हिन्दी | Hindi | 95% | 99% | LTR |
| `ho` | Hiri Motu | Hiri Motu | 91% | 63% | LTR |
| `hu` | Magyar | Hungarian | 95% | 98% | LTR |
| `is` | Íslenska | Icelandic | 94% | 96% | LTR |
| `io` | Ido | Ido | 95% | 56% | LTR |
| `ig` | Igbo | Igbo | 95% | 93% | LTR |
| `id` | Bahasa Indonesia | Indonesian | 92% | 97% | LTR |
| `ia` | Interlingua | Interlingua | 93% | 87% | LTR |
| `ie` | Interlingue | Interlingue | 92% | 73% | LTR |
| `iu` | ᐃᓄᒃᑎᑐᑦ | Inuktitut | 90% | 97% | LTR |
| `ik` | Inupiaq | Inupiaq | 92% | 84% | LTR |
| `ga` | Gaeilge | Irish | 95% | 98% | LTR |
| `it` | Italiano | Italian | 92% | 87% | LTR |
| `ja` | 日本語 | Japanese | 96% | 99% | LTR |
| `jv` | Basa Jawa | Javanese | 92% | 95% | LTR |
| `kl` | Kalaallisut | Kalaallisut | 94% | 97% | LTR |
| `kn` | ಕನ್ನಡ | Kannada | 95% | 97% | LTR |
| `kr` | Kanuri | Kanuri | 92% | 79% | LTR |
| `ks` | کٲشُر | Kashmiri | 95% | 97% | LTR |
| `kk` | Қазақша | Kazakh | 94% | 97% | LTR |
| `km` | ខ្មែរ | Khmer | 91% | 88% | LTR |
| `ki` | Gĩkũyũ | Kikuyu | 93% | 67% | LTR |
| `rw` | Ikinyarwanda | Kinyarwanda | 95% | 96% | LTR |
| `rn` | Ikirundi | Kirundi | 94% | 89% | LTR |
| `kv` | Komi | Komi | 92% | 97% | LTR |
| `kg` | Kikongo | Kongo | 95% | 67% | LTR |
| `ko` | 한국어 | Korean | 94% | 99% | LTR |
| `kj` | Kuanyama | Kuanyama | 93% | 97% | LTR |
| `ku` | Kurdî | Kurdish | 94% | 40% | RTL |
| `ky` | Кыргызча | Kyrgyz | 95% | 97% | LTR |
| `lo` | ລາວ | Lao | 94% | 97% | LTR |
| `la` | Latina | Latin | 95% | 96% | LTR |
| `lv` | Latviešu | Latvian | 94% | 98% | LTR |
| `li` | Limburgish | Limburgish | 92% | 80% | LTR |
| `ln` | Lingála | Lingala | 89% | 81% | LTR |
| `lt` | Lietuvių | Lithuanian | 94% | 98% | LTR |
| `lu` | Tshiluba | Luba-Katanga | 80% | 82% | LTR |
| `lb` | Lëtzebuergesch | Luxembourgish | 93% | 82% | LTR |
| `mk` | Македонски | Macedonian | 74% | 97% | LTR |
| `mg` | Malagasy | Malagasy | 94% | 76% | LTR |
| `ms` | Bahasa Melayu | Malay | 92% | 96% | LTR |
| `ml` | മലയാളം | Malayalam | 75% | 95% | LTR |
| `mt` | Malti | Maltese | 95% | 95% | LTR |
| `gv` | Manx | Manx | 93% | 73% | LTR |
| `mi` | Te Reo Māori | Maori | 86% | 97% | LTR |
| `mr` | मराठी | Marathi | 94% | 76% | LTR |
| `mh` | Kajin M̧ajeļ | Marshallese | 79% | 84% | LTR |
| `mn` | Монгол | Mongolian | 95% | 59% | LTR |
| `na` | Dorerin Naoero | Nauru | 85% | 77% | LTR |
| `nv` | Diné bizaad | Navajo | 64% | 94% | LTR |
| `ng` | Ndonga | Ndonga | 94% | 97% | LTR |
| `ne` | नेपाली | Nepali | 94% | 97% | LTR |
| `nd` | isiNdebele | North Ndebele | 70% | 96% | LTR |
| `se` | Davvisámegiella | Northern Sami | 94% | 96% | LTR |
| `no` | Norsk | Norwegian | 95% | 98% | LTR |
| `nb` | Norwegian Bokmal | Norwegian Bokmal | 94% | 95% | LTR |
| `nn` | Norwegian Nynorsk | Norwegian Nynorsk | 93% | 69% | LTR |
| `oc` | Occitan | Occitan | 94% | 70% | LTR |
| `oj` | Anishinaabemowin | Ojibwa | 91% | 95% | LTR |
| `or` | ଓଡ଼ିଆ | Oriya | 94% | 78% | LTR |
| `om` | Afaan Oromoo | Oromo | 94% | 76% | LTR |
| `os` | Ирон | Ossetian | 95% | 79% | LTR |
| `pi` | पालि | Pali | 94% | 64% | LTR |
| `ps` | پښتو | Pashto | 94% | 97% | RTL |
| `fa` | فارسی | Persian | 95% | 99% | RTL |
| `pl` | Polski | Polish | 93% | 98% | LTR |
| `pt` | Português | Portuguese | 95% | 98% | LTR |
| `pa` | ਪੰਜਾਬੀ | Punjabi | 91% | 88% | LTR |
| `qu` | Runa Simi | Quechua | 95% | 96% | LTR |
| `ro` | Română | Romanian | 92% | 98% | LTR |
| `rm` | Rumantsch | Romansh | 92% | 95% | LTR |
| `ru` | Русский | Russian | 95% | 99% | LTR |
| `sm` | Gagana Samoa | Samoan | 94% | 96% | LTR |
| `sg` | Sängö | Sango | 95% | 97% | LTR |
| `sa` | संस्कृतम् | Sanskrit | 95% | 97% | LTR |
| `sc` | Sardu | Sardinian | 95% | 68% | LTR |
| `gd` | Gàidhlig | Scottish Gaelic | 92% | 97% | LTR |
| `sr` | Српски | Serbian | 95% | 96% | LTR |
| `sn` | chiShona | Shona | 92% | 77% | LTR |
| `ii` | Sichuan Yi | Sichuan Yi | 94% | 95% | LTR |
| `zh` | 简体中文 | Simplified Chinese | 96% | 99% | LTR |
| `sd` | سنڌي | Sindhi | 91% | 77% | RTL |
| `si` | සිංහල | Sinhala | 95% | 97% | LTR |
| `sk` | Slovenčina | Slovak | 93% | 98% | LTR |
| `sl` | Slovenščina | Slovenian | 95% | 98% | LTR |
| `so` | Soomaali | Somali | 92% | 81% | LTR |
| `nr` | isiNdebele | South Ndebele | 94% | 71% | LTR |
| `st` | Sesotho | Southern Sotho | 94% | 70% | LTR |
| `es` | Español | Spanish | 94% | 98% | LTR |
| `su` | Basa Sunda | Sundanese | 93% | 77% | LTR |
| `sw` | Kiswahili | Swahili | 94% | 68% | LTR |
| `ss` | siSwati | Swati | 94% | 64% | LTR |
| `sv` | Svenska | Swedish | 94% | 98% | LTR |
| `tl` | Tagalog | Tagalog | 91% | 93% | LTR |
| `ty` | Reo Tahiti | Tahitian | 96% | 97% | LTR |
| `tg` | Тоҷикӣ | Tajik | 94% | 76% | LTR |
| `ta` | தமிழ் | Tamil | 94% | 97% | LTR |
| `tt` | Татарча | Tatar | 95% | 97% | LTR |
| `te` | తెలుగు | Telugu | 95% | 97% | LTR |
| `th` | ไทย | Thai | 95% | 99% | LTR |
| `bo` | བོད་སྐད | Tibetan | 94% | 96% | LTR |
| `ti` | ትግርኛ | Tigrinya | 95% | 97% | LTR |
| `to` | Lea faka-Tonga | Tonga | 94% | 68% | LTR |
| `torbeski` | Torbeški | Torbeški | 95% | 73% | LTR |
| `zh-hant` | 繁體中文 | Traditional Chinese | 96% | 99% | LTR |
| `ts` | Xitsonga | Tsonga | 93% | 94% | LTR |
| `tn` | Setswana | Tswana | 92% | 60% | LTR |
| `tr` | Türkçe | Turkish | 93% | 97% | LTR |
| `tk` | Türkmençe | Turkmen | 94% | 77% | LTR |
| `tw` | Twi | Twi | 96% | 82% | LTR |
| `uk` | Українська | Ukrainian | 95% | 99% | LTR |
| `ur` | اردو | Urdu | 94% | 72% | RTL |
| `ug` | ئۇيغۇرچە | Uyghur | 96% | 92% | RTL |
| `uz` | Oʻzbekcha | Uzbek | 95% | 73% | LTR |
| `ve` | Tshivenḓa | Venda | 96% | 75% | LTR |
| `vi` | Tiếng Việt | Vietnamese | 95% | 98% | LTR |
| `vo` | Volapük | Volapuk | 96% | 97% | LTR |
| `wa` | Walon | Walloon | 96% | 96% | LTR |
| `cy` | Cymraeg | Welsh | 93% | 81% | LTR |
| `fy` | Frysk | Western Frisian | 93% | 77% | LTR |
| `wo` | Wolof | Wolof | 96% | 74% | LTR |
| `xh` | isiXhosa | Xhosa | 95% | 97% | LTR |
| `yi` | ייִדיש | Yiddish | 96% | 97% | RTL |
| `yo` | Yorùbá | Yoruba | 96% | 79% | LTR |
| `za` | Vahcuengh | Zhuang | 96% | 85% | LTR |
| `zu` | isiZulu | Zulu | 95% | 97% | LTR |

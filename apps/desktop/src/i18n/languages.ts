import { normalize } from '@/lib/text'

import type { Locale } from './types'

export const DEFAULT_LOCALE: Locale = 'en'

export const LOCALE_OPTIONS = [
  {
    id: 'aa',
    name: 'Afaraf',
    englishName: 'Afar',
    configValue: 'aa'
  },
  {
    id: 'ab',
    name: 'Аҧсуа',
    englishName: 'Abkhazian',
    configValue: 'ab'
  },
  {
    id: 'ae',
    name: 'Avesta',
    englishName: 'Avestan',
    configValue: 'ae'
  },
  {
    id: 'af',
    name: 'Afrikaans',
    englishName: 'Afrikaans',
    configValue: 'af'
  },
  {
    id: 'ak',
    name: 'Akan',
    englishName: 'Akan',
    configValue: 'ak'
  },
  {
    id: 'am',
    name: 'አማርኛ',
    englishName: 'Amharic',
    configValue: 'am'
  },
  {
    id: 'an',
    name: 'Aragonés',
    englishName: 'Aragonese',
    configValue: 'an'
  },
  {
    id: 'ar',
    name: 'العربية',
    englishName: 'Arabic',
    configValue: 'ar'
  },
  {
    id: 'as',
    name: 'অসমীয়া',
    englishName: 'Assamese',
    configValue: 'as'
  },
  {
    id: 'av',
    name: 'Авар',
    englishName: 'Avaric',
    configValue: 'av'
  },
  {
    id: 'ay',
    name: 'Aymar aru',
    englishName: 'Aymara',
    configValue: 'ay'
  },
  {
    id: 'az',
    name: 'Azərbaycan',
    englishName: 'Azerbaijani',
    configValue: 'az'
  },
  {
    id: 'ba',
    name: 'Башҡортса',
    englishName: 'Bashkir',
    configValue: 'ba'
  },
  {
    id: 'be',
    name: 'Беларуская',
    englishName: 'Belarusian',
    configValue: 'be'
  },
  {
    id: 'bg',
    name: 'Български',
    englishName: 'Bulgarian',
    configValue: 'bg'
  },
  {
    id: 'bh',
    name: 'भोजपुरी',
    englishName: 'Bihari',
    configValue: 'bh'
  },
  {
    id: 'bi',
    name: 'Bislama',
    englishName: 'Bislama',
    configValue: 'bi'
  },
  {
    id: 'bm',
    name: 'Bamanankan',
    englishName: 'Bambara',
    configValue: 'bm'
  },
  {
    id: 'bn',
    name: 'বাংলা',
    englishName: 'Bengali',
    configValue: 'bn'
  },
  {
    id: 'bo',
    name: 'བོད་སྐད',
    englishName: 'Tibetan',
    configValue: 'bo'
  },
  {
    id: 'br',
    name: 'Brezhoneg',
    englishName: 'Breton',
    configValue: 'br'
  },
  {
    id: 'bs',
    name: 'Bosanski',
    englishName: 'Bosnian',
    configValue: 'bs'
  },
  {
    id: 'ca',
    name: 'Català',
    englishName: 'Catalan',
    configValue: 'ca'
  },
  {
    id: 'ce',
    name: 'Нохчийн',
    englishName: 'Chechen',
    configValue: 'ce'
  },
  {
    id: 'ch',
    name: 'Chamoru',
    englishName: 'Chamorro',
    configValue: 'ch'
  },
  {
    id: 'co',
    name: 'Corsu',
    englishName: 'Corsican',
    configValue: 'co'
  },
  {
    id: 'cr',
    name: 'Cree',
    englishName: 'Cree',
    configValue: 'cr'
  },
  {
    id: 'cs',
    name: 'Čeština',
    englishName: 'Czech',
    configValue: 'cs'
  },
  {
    id: 'cu',
    name: 'Словѣньскъ',
    englishName: 'Church Slavic',
    configValue: 'cu'
  },
  {
    id: 'cv',
    name: 'Чӑвашла',
    englishName: 'Chuvash',
    configValue: 'cv'
  },
  {
    id: 'cy',
    name: 'Cymraeg',
    englishName: 'Welsh',
    configValue: 'cy'
  },
  {
    id: 'da',
    name: 'Dansk',
    englishName: 'Danish',
    configValue: 'da'
  },
  {
    id: 'de',
    name: 'Deutsch',
    englishName: 'German',
    configValue: 'de'
  },
  {
    id: 'dv',
    name: 'ދިވެހި',
    englishName: 'Divehi',
    configValue: 'dv'
  },
  {
    id: 'dz',
    name: 'རྫོང་ཁ',
    englishName: 'Dzongkha',
    configValue: 'dz'
  },
  {
    id: 'ee',
    name: 'Eʋegbe',
    englishName: 'Ewe',
    configValue: 'ee'
  },
  {
    id: 'el',
    name: 'Ελληνικά',
    englishName: 'Greek',
    configValue: 'el'
  },
  {
    id: 'en',
    name: 'English',
    englishName: 'English',
    configValue: 'en'
  },
  {
    id: 'eo',
    name: 'Esperanto',
    englishName: 'Esperanto',
    configValue: 'eo'
  },
  {
    id: 'es',
    name: 'Español',
    englishName: 'Spanish',
    configValue: 'es'
  },
  {
    id: 'et',
    name: 'Eesti',
    englishName: 'Estonian',
    configValue: 'et'
  },
  {
    id: 'eu',
    name: 'Euskara',
    englishName: 'Basque',
    configValue: 'eu'
  },
  {
    id: 'fa',
    name: 'فارسی',
    englishName: 'Persian',
    configValue: 'fa'
  },
  {
    id: 'ff',
    name: 'Fulfulde',
    englishName: 'Fulah',
    configValue: 'ff'
  },
  {
    id: 'fi',
    name: 'Suomi',
    englishName: 'Finnish',
    configValue: 'fi'
  },
  {
    id: 'fj',
    name: 'Na Vosa Vakaviti',
    englishName: 'Fijian',
    configValue: 'fj'
  },
  {
    id: 'fo',
    name: 'Føroyskt',
    englishName: 'Faroese',
    configValue: 'fo'
  },
  {
    id: 'fr',
    name: 'Français',
    englishName: 'French',
    configValue: 'fr'
  },
  {
    id: 'fy',
    name: 'Frysk',
    englishName: 'Western Frisian',
    configValue: 'fy'
  },
  {
    id: 'ga',
    name: 'Gaeilge',
    englishName: 'Irish',
    configValue: 'ga'
  },
  {
    id: 'gd',
    name: 'Gàidhlig',
    englishName: 'Scottish Gaelic',
    configValue: 'gd'
  },
  {
    id: 'gl',
    name: 'Galego',
    englishName: 'Galician',
    configValue: 'gl'
  },
  {
    id: 'gn',
    name: 'Avañe\'ẽ',
    englishName: 'Guarani',
    configValue: 'gn'
  },
  {
    id: 'gu',
    name: 'ગુજરાતી',
    englishName: 'Gujarati',
    configValue: 'gu'
  },
  {
    id: 'gv',
    name: 'Manx',
    englishName: 'Manx',
    configValue: 'gv'
  },
  {
    id: 'ha',
    name: 'Hausa',
    englishName: 'Hausa',
    configValue: 'ha'
  },
  {
    id: 'he',
    name: 'עברית',
    englishName: 'Hebrew',
    configValue: 'he'
  },
  {
    id: 'hi',
    name: 'हिन्दी',
    englishName: 'Hindi',
    configValue: 'hi'
  },
  {
    id: 'ho',
    name: 'Hiri Motu',
    englishName: 'Hiri Motu',
    configValue: 'ho'
  },
  {
    id: 'hr',
    name: 'Hrvatski',
    englishName: 'Croatian',
    configValue: 'hr'
  },
  {
    id: 'ht',
    name: 'Kreyòl ayisyen',
    englishName: 'Haitian Creole',
    configValue: 'ht'
  },
  {
    id: 'hu',
    name: 'Magyar',
    englishName: 'Hungarian',
    configValue: 'hu'
  },
  {
    id: 'hy',
    name: 'Հայերեն',
    englishName: 'Armenian',
    configValue: 'hy'
  },
  {
    id: 'hz',
    name: 'Otjiherero',
    englishName: 'Herero',
    configValue: 'hz'
  },
  {
    id: 'ia',
    name: 'Interlingua',
    englishName: 'Interlingua',
    configValue: 'ia'
  },
  {
    id: 'id',
    name: 'Bahasa Indonesia',
    englishName: 'Indonesian',
    configValue: 'id'
  },
  {
    id: 'ie',
    name: 'Interlingue',
    englishName: 'Interlingue',
    configValue: 'ie'
  },
  {
    id: 'ig',
    name: 'Igbo',
    englishName: 'Igbo',
    configValue: 'ig'
  },
  {
    id: 'ii',
    name: 'Sichuan Yi',
    englishName: 'Sichuan Yi',
    configValue: 'ii'
  },
  {
    id: 'ik',
    name: 'Inupiaq',
    englishName: 'Inupiaq',
    configValue: 'ik'
  },
  {
    id: 'io',
    name: 'Ido',
    englishName: 'Ido',
    configValue: 'io'
  },
  {
    id: 'is',
    name: 'Íslenska',
    englishName: 'Icelandic',
    configValue: 'is'
  },
  {
    id: 'it',
    name: 'Italiano',
    englishName: 'Italian',
    configValue: 'it'
  },
  {
    id: 'iu',
    name: 'ᐃᓄᒃᑎᑐᑦ',
    englishName: 'Inuktitut',
    configValue: 'iu'
  },
  {
    id: 'ja',
    name: '日本語',
    englishName: 'Japanese',
    configValue: 'ja'
  },
  {
    id: 'jv',
    name: 'Basa Jawa',
    englishName: 'Javanese',
    configValue: 'jv'
  },
  {
    id: 'ka',
    name: 'ქართული',
    englishName: 'Georgian',
    configValue: 'ka'
  },
  {
    id: 'kg',
    name: 'Kikongo',
    englishName: 'Kongo',
    configValue: 'kg'
  },
  {
    id: 'ki',
    name: 'Gĩkũyũ',
    englishName: 'Kikuyu',
    configValue: 'ki'
  },
  {
    id: 'kj',
    name: 'Kuanyama',
    englishName: 'Kuanyama',
    configValue: 'kj'
  },
  {
    id: 'kk',
    name: 'Қазақша',
    englishName: 'Kazakh',
    configValue: 'kk'
  },
  {
    id: 'kl',
    name: 'Kalaallisut',
    englishName: 'Kalaallisut',
    configValue: 'kl'
  },
  {
    id: 'km',
    name: 'ខ្មែរ',
    englishName: 'Khmer',
    configValue: 'km'
  },
  {
    id: 'kn',
    name: 'ಕನ್ನಡ',
    englishName: 'Kannada',
    configValue: 'kn'
  },
  {
    id: 'ko',
    name: '한국어',
    englishName: 'Korean',
    configValue: 'ko'
  },
  {
    id: 'kr',
    name: 'Kanuri',
    englishName: 'Kanuri',
    configValue: 'kr'
  },
  {
    id: 'ks',
    name: 'کٲشُر',
    englishName: 'Kashmiri',
    configValue: 'ks'
  },
  {
    id: 'ku',
    name: 'Kurdî',
    englishName: 'Kurdish',
    configValue: 'ku'
  },
  {
    id: 'kv',
    name: 'Komi',
    englishName: 'Komi',
    configValue: 'kv'
  },
  {
    id: 'kw',
    name: 'Cornish',
    englishName: 'Cornish',
    configValue: 'kw'
  },
  {
    id: 'ky',
    name: 'Кыргызча',
    englishName: 'Kyrgyz',
    configValue: 'ky'
  },
  {
    id: 'la',
    name: 'Latina',
    englishName: 'Latin',
    configValue: 'la'
  },
  {
    id: 'lb',
    name: 'Lëtzebuergesch',
    englishName: 'Luxembourgish',
    configValue: 'lb'
  },
  {
    id: 'lg',
    name: 'Luganda',
    englishName: 'Ganda',
    configValue: 'lg'
  },
  {
    id: 'li',
    name: 'Limburgish',
    englishName: 'Limburgish',
    configValue: 'li'
  },
  {
    id: 'ln',
    name: 'Lingála',
    englishName: 'Lingala',
    configValue: 'ln'
  },
  {
    id: 'lo',
    name: 'ລາວ',
    englishName: 'Lao',
    configValue: 'lo'
  },
  {
    id: 'lt',
    name: 'Lietuvių',
    englishName: 'Lithuanian',
    configValue: 'lt'
  },
  {
    id: 'lu',
    name: 'Tshiluba',
    englishName: 'Luba-Katanga',
    configValue: 'lu'
  },
  {
    id: 'lv',
    name: 'Latviešu',
    englishName: 'Latvian',
    configValue: 'lv'
  },
  {
    id: 'mg',
    name: 'Malagasy',
    englishName: 'Malagasy',
    configValue: 'mg'
  },
  {
    id: 'mh',
    name: 'Kajin M̧ajeļ',
    englishName: 'Marshallese',
    configValue: 'mh'
  },
  {
    id: 'mi',
    name: 'Te Reo Māori',
    englishName: 'Maori',
    configValue: 'mi'
  },
  {
    id: 'mk',
    name: 'Македонски',
    englishName: 'Macedonian',
    configValue: 'mk'
  },
  {
    id: 'ml',
    name: 'മലയാളം',
    englishName: 'Malayalam',
    configValue: 'ml'
  },
  {
    id: 'mn',
    name: 'Монгол',
    englishName: 'Mongolian',
    configValue: 'mn'
  },
  {
    id: 'mr',
    name: 'मराठी',
    englishName: 'Marathi',
    configValue: 'mr'
  },
  {
    id: 'ms',
    name: 'Bahasa Melayu',
    englishName: 'Malay',
    configValue: 'ms'
  },
  {
    id: 'mt',
    name: 'Malti',
    englishName: 'Maltese',
    configValue: 'mt'
  },
  {
    id: 'my',
    name: 'မြန်မာ',
    englishName: 'Burmese',
    configValue: 'my'
  },
  {
    id: 'na',
    name: 'Dorerin Naoero',
    englishName: 'Nauru',
    configValue: 'na'
  },
  {
    id: 'nb',
    name: 'Norwegian Bokmal',
    englishName: 'Norwegian Bokmal',
    configValue: 'nb'
  },
  {
    id: 'nd',
    name: 'isiNdebele',
    englishName: 'North Ndebele',
    configValue: 'nd'
  },
  {
    id: 'ne',
    name: 'नेपाली',
    englishName: 'Nepali',
    configValue: 'ne'
  },
  {
    id: 'ng',
    name: 'Ndonga',
    englishName: 'Ndonga',
    configValue: 'ng'
  },
  {
    id: 'nl',
    name: 'Nederlands',
    englishName: 'Dutch',
    configValue: 'nl'
  },
  {
    id: 'nn',
    name: 'Norwegian Nynorsk',
    englishName: 'Norwegian Nynorsk',
    configValue: 'nn'
  },
  {
    id: 'no',
    name: 'Norsk',
    englishName: 'Norwegian',
    configValue: 'no'
  },
  {
    id: 'nr',
    name: 'isiNdebele',
    englishName: 'South Ndebele',
    configValue: 'nr'
  },
  {
    id: 'nv',
    name: 'Diné bizaad',
    englishName: 'Navajo',
    configValue: 'nv'
  },
  {
    id: 'ny',
    name: 'Chichewa',
    englishName: 'Chichewa',
    configValue: 'ny'
  },
  {
    id: 'oc',
    name: 'Occitan',
    englishName: 'Occitan',
    configValue: 'oc'
  },
  {
    id: 'oj',
    name: 'Anishinaabemowin',
    englishName: 'Ojibwa',
    configValue: 'oj'
  },
  {
    id: 'om',
    name: 'Afaan Oromoo',
    englishName: 'Oromo',
    configValue: 'om'
  },
  {
    id: 'or',
    name: 'ଓଡ଼ିଆ',
    englishName: 'Oriya',
    configValue: 'or'
  },
  {
    id: 'os',
    name: 'Ирон',
    englishName: 'Ossetian',
    configValue: 'os'
  },
  {
    id: 'pa',
    name: 'ਪੰਜਾਬੀ',
    englishName: 'Punjabi',
    configValue: 'pa'
  },
  {
    id: 'pi',
    name: 'पालि',
    englishName: 'Pali',
    configValue: 'pi'
  },
  {
    id: 'pl',
    name: 'Polski',
    englishName: 'Polish',
    configValue: 'pl'
  },
  {
    id: 'ps',
    name: 'پښتو',
    englishName: 'Pashto',
    configValue: 'ps'
  },
  {
    id: 'pt',
    name: 'Português',
    englishName: 'Portuguese',
    configValue: 'pt'
  },
  {
    id: 'qu',
    name: 'Runa Simi',
    englishName: 'Quechua',
    configValue: 'qu'
  },
  {
    id: 'rm',
    name: 'Rumantsch',
    englishName: 'Romansh',
    configValue: 'rm'
  },
  {
    id: 'rn',
    name: 'Ikirundi',
    englishName: 'Kirundi',
    configValue: 'rn'
  },
  {
    id: 'ro',
    name: 'Română',
    englishName: 'Romanian',
    configValue: 'ro'
  },
  {
    id: 'ru',
    name: 'Русский',
    englishName: 'Russian',
    configValue: 'ru'
  },
  {
    id: 'rw',
    name: 'Ikinyarwanda',
    englishName: 'Kinyarwanda',
    configValue: 'rw'
  },
  {
    id: 'sa',
    name: 'संस्कृतम्',
    englishName: 'Sanskrit',
    configValue: 'sa'
  },
  {
    id: 'sc',
    name: 'Sardu',
    englishName: 'Sardinian',
    configValue: 'sc'
  },
  {
    id: 'sd',
    name: 'سنڌي',
    englishName: 'Sindhi',
    configValue: 'sd'
  },
  {
    id: 'se',
    name: 'Davvisámegiella',
    englishName: 'Northern Sami',
    configValue: 'se'
  },
  {
    id: 'sg',
    name: 'Sängö',
    englishName: 'Sango',
    configValue: 'sg'
  },
  {
    id: 'si',
    name: 'සිංහල',
    englishName: 'Sinhala',
    configValue: 'si'
  },
  {
    id: 'sk',
    name: 'Slovenčina',
    englishName: 'Slovak',
    configValue: 'sk'
  },
  {
    id: 'sl',
    name: 'Slovenščina',
    englishName: 'Slovenian',
    configValue: 'sl'
  },
  {
    id: 'sm',
    name: 'Gagana Samoa',
    englishName: 'Samoan',
    configValue: 'sm'
  },
  {
    id: 'sn',
    name: 'chiShona',
    englishName: 'Shona',
    configValue: 'sn'
  },
  {
    id: 'so',
    name: 'Soomaali',
    englishName: 'Somali',
    configValue: 'so'
  },
  {
    id: 'sq',
    name: 'Shqip',
    englishName: 'Albanian',
    configValue: 'sq'
  },
  {
    id: 'sr',
    name: 'Српски',
    englishName: 'Serbian',
    configValue: 'sr'
  },
  {
    id: 'ss',
    name: 'siSwati',
    englishName: 'Swati',
    configValue: 'ss'
  },
  {
    id: 'st',
    name: 'Sesotho',
    englishName: 'Southern Sotho',
    configValue: 'st'
  },
  {
    id: 'su',
    name: 'Basa Sunda',
    englishName: 'Sundanese',
    configValue: 'su'
  },
  {
    id: 'sv',
    name: 'Svenska',
    englishName: 'Swedish',
    configValue: 'sv'
  },
  {
    id: 'sw',
    name: 'Kiswahili',
    englishName: 'Swahili',
    configValue: 'sw'
  },
  {
    id: 'ta',
    name: 'தமிழ்',
    englishName: 'Tamil',
    configValue: 'ta'
  },
  {
    id: 'te',
    name: 'తెలుగు',
    englishName: 'Telugu',
    configValue: 'te'
  },
  {
    id: 'tg',
    name: 'Тоҷикӣ',
    englishName: 'Tajik',
    configValue: 'tg'
  },
  {
    id: 'th',
    name: 'ไทย',
    englishName: 'Thai',
    configValue: 'th'
  },
  {
    id: 'ti',
    name: 'ትግርኛ',
    englishName: 'Tigrinya',
    configValue: 'ti'
  },
  {
    id: 'tk',
    name: 'Türkmençe',
    englishName: 'Turkmen',
    configValue: 'tk'
  },
  {
    id: 'tl',
    name: 'Tagalog',
    englishName: 'Tagalog',
    configValue: 'tl'
  },
  {
    id: 'tn',
    name: 'Setswana',
    englishName: 'Tswana',
    configValue: 'tn'
  },
  {
    id: 'to',
    name: 'Lea faka-Tonga',
    englishName: 'Tonga',
    configValue: 'to'
  },
  {
    id: 'tr',
    name: 'Türkçe',
    englishName: 'Turkish',
    configValue: 'tr'
  },
  {
    id: 'ts',
    name: 'Xitsonga',
    englishName: 'Tsonga',
    configValue: 'ts'
  },
  {
    id: 'tt',
    name: 'Татарча',
    englishName: 'Tatar',
    configValue: 'tt'
  },
  {
    id: 'tw',
    name: 'Twi',
    englishName: 'Twi',
    configValue: 'tw'
  },
  {
    id: 'ty',
    name: 'Reo Tahiti',
    englishName: 'Tahitian',
    configValue: 'ty'
  },
  {
    id: 'ug',
    name: 'ئۇيغۇرچە',
    englishName: 'Uyghur',
    configValue: 'ug'
  },
  {
    id: 'uk',
    name: 'Українська',
    englishName: 'Ukrainian',
    configValue: 'uk'
  },
  {
    id: 'ur',
    name: 'اردو',
    englishName: 'Urdu',
    configValue: 'ur'
  },
  {
    id: 'uz',
    name: 'Oʻzbekcha',
    englishName: 'Uzbek',
    configValue: 'uz'
  },
  {
    id: 've',
    name: 'Tshivenḓa',
    englishName: 'Venda',
    configValue: 've'
  },
  {
    id: 'vi',
    name: 'Tiếng Việt',
    englishName: 'Vietnamese',
    configValue: 'vi'
  },
  {
    id: 'vo',
    name: 'Volapük',
    englishName: 'Volapuk',
    configValue: 'vo'
  },
  {
    id: 'wa',
    name: 'Walon',
    englishName: 'Walloon',
    configValue: 'wa'
  },
  {
    id: 'wo',
    name: 'Wolof',
    englishName: 'Wolof',
    configValue: 'wo'
  },
  {
    id: 'xh',
    name: 'isiXhosa',
    englishName: 'Xhosa',
    configValue: 'xh'
  },
  {
    id: 'yi',
    name: 'ייִדיש',
    englishName: 'Yiddish',
    configValue: 'yi'
  },
  {
    id: 'yo',
    name: 'Yorùbá',
    englishName: 'Yoruba',
    configValue: 'yo'
  },
  {
    id: 'za',
    name: 'Vahcuengh',
    englishName: 'Zhuang',
    configValue: 'za'
  },
  {
    id: 'zh',
    name: '简体中文',
    englishName: 'Simplified Chinese',
    configValue: 'zh'
  },
  {
    id: 'zh-hant',
    name: '繁體中文',
    englishName: 'Traditional Chinese',
    configValue: 'zh-hant'
  },
  {
    id: 'zu',
    name: 'isiZulu',
    englishName: 'Zulu',
    configValue: 'zu'
  },
  {
    id: 'torbeski',
    name: 'Torbeški',
    englishName: 'Torbeski',
    configValue: 'torbeski'
  }
] as const satisfies readonly { configValue: string; englishName: string; id: Locale; name: string }[];

// `name` is the endonym (native name) shown in the picker so users recognize
// their language regardless of the current UI language. No country flags:
// languages are not countries. `englishName` is search-only (not shown) so an
// English speaker can type "japanese"/"traditional" to filter the list.
export const LOCALE_META: Record<Locale, { name: string; englishName: string }> = Object.fromEntries(
  LOCALE_OPTIONS.map(locale => [locale.id, { name: locale.name, englishName: locale.englishName }])
) as Record<Locale, { name: string; englishName: string }>

const LOCALE_ALIASES: Record<string, Locale> = {
  en: 'en',
  'en-us': 'en',
  en_us: 'en',
  zh: 'zh',
  'zh-cn': 'zh',
  zh_cn: 'zh',
  'zh-hans': 'zh',
  zh_hans: 'zh',
  'zh-hans-cn': 'zh',
  zh_hans_cn: 'zh',
  'zh-tw': 'zh-hant',
  zh_tw: 'zh-hant',
  'zh-hk': 'zh-hant',
  zh_hk: 'zh-hant',
  'zh-mo': 'zh-hant',
  zh_mo: 'zh-hant',
  'zh-hant': 'zh-hant',
  zh_hant: 'zh-hant',
  'zh-hant-tw': 'zh-hant',
  zh_hant_tw: 'zh-hant',
  'zh-hant-hk': 'zh-hant',
  zh_hant_hk: 'zh-hant',
  ja: 'ja',
  'ja-jp': 'ja',
  ja_jp: 'ja',
  ar: 'ar',
  'ar-sa': 'ar',
  ar_sa: 'ar',
  'ar-ae': 'ar',
  ar_ae: 'ar',
  'ar-eg': 'ar',
  ar_eg: 'ar',
  arabic: 'ar',
  العربية: 'ar',
  de: 'de',
  'de-de': 'de',
  de_de: 'de',
  'de-at': 'de',
  de_at: 'de',
  'de-ch': 'de',
  de_ch: 'de',
  german: 'de',
  deutsch: 'de',
  es: 'es',
  'es-es': 'es',
  es_es: 'es',
  'es-mx': 'es',
  es_mx: 'es',
  'es-ar': 'es',
  es_ar: 'es',
  spanish: 'es',
  español: 'es',
  pt: 'pt',
  'pt-pt': 'pt',
  pt_pt: 'pt',
  'pt-br': 'pt',
  pt_br: 'pt',
  portuguese: 'pt',
  português: 'pt',
  sq: 'sq',
  'sq-al': 'sq',
  sq_al: 'sq',
  albanian: 'sq',
  shqip: 'sq',
  bs: 'bs',
  'bs-ba': 'bs',
  bs_ba: 'bs',
  bosnian: 'bs',
  bosanski: 'bs',
  fr: 'fr',
  'fr-fr': 'fr',
  fr_fr: 'fr',
  'fr-ca': 'fr',
  fr_ca: 'fr',
  french: 'fr',
  français: 'fr',
  it: 'it',
  'it-it': 'it',
  it_it: 'it',
  italian: 'it',
  italiano: 'it',
  tr: 'tr',
  'tr-tr': 'tr',
  tr_tr: 'tr',
  turkish: 'tr',
  türkçe: 'tr',
  ru: 'ru',
  'ru-ru': 'ru',
  ru_ru: 'ru',
  russian: 'ru',
  русский: 'ru',
  hi: 'hi',
  'hi-in': 'hi',
  hi_in: 'hi',
  hindi: 'hi',
  हिन्दी: 'hi',
  fa: 'fa',
  'fa-ir': 'fa',
  fa_ir: 'fa',
  persian: 'fa',
  farsi: 'fa',
  فارسی: 'fa',
  he: 'he',
  'he-il': 'he',
  he_il: 'he',
  hebrew: 'he',
  עברית: 'he',
  uk: 'uk',
  'uk-ua': 'uk',
  uk_ua: 'uk',
  ukrainian: 'uk',
  українська: 'uk',
  ko: 'ko',
  'ko-kr': 'ko',
  ko_kr: 'ko',
  korean: 'ko',
  한국어: 'ko',
  id: 'id',
  'id-id': 'id',
  id_id: 'id',
  indonesian: 'id',
  'bahasa indonesia': 'id',
  th: 'th',
  'th-th': 'th',
  th_th: 'th',
  thai: 'th',
  ไทย: 'th',
  vi: 'vi',
  'vi-vn': 'vi',
  vi_vn: 'vi',
  vietnamese: 'vi',
  'tiếng việt': 'vi',
  eo: 'eo',
  esperanto: 'eo',
  pl: 'pl',
  'pl-pl': 'pl',
  pl_pl: 'pl',
  polish: 'pl',
  polski: 'pl',
  nl: 'nl',
  'nl-nl': 'nl',
  nl_nl: 'nl',
  'nl-be': 'nl',
  nl_be: 'nl',
  dutch: 'nl',
  nederlands: 'nl',
  flemish: 'nl',
  ro: 'ro',
  'ro-ro': 'ro',
  ro_ro: 'ro',
  romanian: 'ro',
  română: 'ro',
  el: 'el',
  'el-gr': 'el',
  el_gr: 'el',
  greek: 'el',
  ελληνικά: 'el',
  cs: 'cs',
  'cs-cz': 'cs',
  cs_cz: 'cs',
  czech: 'cs',
  čeština: 'cs',
  sv: 'sv',
  'sv-se': 'sv',
  sv_se: 'sv',
  swedish: 'sv',
  svenska: 'sv',
  hu: 'hu',
  'hu-hu': 'hu',
  hu_hu: 'hu',
  hungarian: 'hu',
  magyar: 'hu',
  bg: 'bg',
  'bg-bg': 'bg',
  bg_bg: 'bg',
  bulgarian: 'bg',
  български: 'bg',
  da: 'da',
  'da-dk': 'da',
  da_dk: 'da',
  danish: 'da',
  dansk: 'da',
  fi: 'fi',
  'fi-fi': 'fi',
  fi_fi: 'fi',
  finnish: 'fi',
  suomi: 'fi',
  sk: 'sk',
  'sk-sk': 'sk',
  sk_sk: 'sk',
  slovak: 'sk',
  slovenčina: 'sk',
  no: 'no',
  'no-no': 'no',
  no_no: 'no',
  nb: 'no',
  'nb-no': 'no',
  norwegian: 'no',
  norsk: 'no',
  ga: 'ga',
  'ga-ie': 'ga',
  ga_ie: 'ga',
  irish: 'ga',
  gaeilge: 'ga',
  sl: 'sl',
  'sl-si': 'sl',
  sl_si: 'sl',
  slovenian: 'sl',
  slovenščina: 'sl',
  hr: 'hr',
  'hr-hr': 'hr',
  hr_hr: 'hr',
  croatian: 'hr',
  hrvatski: 'hr',
  et: 'et',
  'et-ee': 'et',
  et_ee: 'et',
  estonian: 'et',
  'eesti keel': 'et',
  eesti: 'et',
  lv: 'lv',
  'lv-lv': 'lv',
  lv_lv: 'lv',
  latvian: 'lv',
  latviešu: 'lv',
  lt: 'lt',
  'lt-lt': 'lt',
  lt_lt: 'lt',
  lithuanian: 'lt',
  lietuvių: 'lt'
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && LOCALE_OPTIONS.some(locale => locale.id === value)
}

export function normalizeLocale(value: unknown): Locale {
  if (typeof value !== 'string') {
    return DEFAULT_LOCALE
  }

  return LOCALE_ALIASES[normalize(value)] ?? DEFAULT_LOCALE
}

export function isSupportedLocaleValue(value: unknown): boolean {
  return typeof value === 'string' && LOCALE_ALIASES[normalize(value)] != null
}

export function localeConfigValue(locale: Locale): string {
  return LOCALE_OPTIONS.find(item => item.id === locale)?.configValue ?? DEFAULT_LOCALE
}

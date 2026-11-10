"""Lightweight internationalization (i18n) for OpenAmer static user-facing messages.

Scope (thin slice, by design): only the highest-impact static strings shown
to the user by OpenAmer itself -- approval prompts, a handful of gateway slash
command replies, restart-drain notices.  Agent-generated output, log lines,
error tracebacks, tool outputs, and slash-command descriptions all stay in
English.

Catalog files live under ``locales/<lang>.yaml`` at the repo root.  Each
catalog is a flat dict keyed by dotted paths (e.g. ``approval.choose`` or
``gateway.approval_expired``).  Missing keys fall back to English; if English
is missing too, the key path itself is returned so a broken catalog never
crashes the agent.

Usage::

    from agent.i18n import t
    print(t("approval.choose_long"))                       # current lang
    print(t("gateway.draining", count=3))                  # {count} formatted
    print(t("approval.choose_long", lang="zh"))            # explicit override

Language resolution order:
    1. Explicit ``lang=`` argument passed to :func:`t`
    2. ``OPENAMER_LANGUAGE`` environment variable (for tests / quick override)
    3. ``display.language`` from config.yaml
    4. ``"en"`` (baseline)

Supported languages: every code in ``locales/_languages.json`` -- all ISO 639-1
languages plus zh-hant (185 total).  scripts/expand_locale_set.py keeps that
file, this tuple and the on-disk catalogs in lockstep.  Unknown values fall
back to en.
"""

from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "aa", "ab", "ae", "af", "ak",
    "am", "an", "ar", "as", "av",
    "ay", "az", "ba", "be", "bg",
    "bh", "bi", "bm", "bn", "bo",
    "br", "bs", "ca", "ce", "ch",
    "co", "cr", "cs", "cu", "cv",
    "cy", "da", "de", "dv", "dz",
    "ee", "el", "en", "eo", "es",
    "et", "eu", "fa", "ff", "fi",
    "fj", "fo", "fr", "fy", "ga",
    "gd", "gl", "gn", "gu", "gv",
    "ha", "he", "hi", "ho", "hr",
    "ht", "hu", "hy", "hz", "ia",
    "id", "ie", "ig", "ii", "ik",
    "io", "is", "it", "iu", "ja",
    "jv", "ka", "kg", "ki", "kj",
    "kk", "kl", "km", "kn", "ko",
    "kr", "ks", "ku", "kv", "kw",
    "ky", "la", "lb", "lg", "li",
    "ln", "lo", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml",
    "mn", "mr", "ms", "mt", "my",
    "na", "nb", "nd", "ne", "ng",
    "nl", "nn", "no", "nr", "nv",
    "ny", "oc", "oj", "om", "or",
    "os", "pa", "pi", "pl", "ps",
    "pt", "qu", "rm", "rn", "ro",
    "ru", "rw", "sa", "sc", "sd",
    "se", "sg", "si", "sk", "sl",
    "sm", "sn", "so", "sq", "sr",
    "ss", "st", "su", "sv", "sw",
    "ta", "te", "tg", "th", "ti",
    "tk", "tl", "tn", "to", "tr",
    "ts", "tt", "tw", "ty", "ug",
    "uk", "ur", "uz", "ve", "vi",
    "vo", "wa", "wo", "xh", "yi",
    "yo", "za", "zh", "zh-hant", "zu",
    # Not ISO 639-1: Torbeški is the South Slavic variety of the Torbeši
    # community (Polog/Debar, North Macedonia). It has no ISO code of its own and
    # no standard written norm. The code must stand alone -- "mk-torbeski" would
    # be split at the hyphen by _normalize_lang and silently resolve to
    # Macedonian, which is a different language to its speakers.
    "torbeski",
)
DEFAULT_LANGUAGE = "en"

# Accept a few natural aliases so users who type "chinese" / "zh-CN" / "jp"
# get the right catalog instead of silently falling back to English.
_LANGUAGE_ALIASES: dict[str, str] = {
    "english": "en", "en-us": "en", "en-gb": "en",
    # Simplified Chinese — explicit codes route here; bare "chinese" / "mandarin"
    # also default to Simplified since that's the larger user base.
    "chinese": "zh", "mandarin": "zh", "zh-cn": "zh", "zh-hans": "zh", "zh-sg": "zh",
    # Traditional Chinese — distinct catalog.  Cover Taiwan / Hong Kong / Macau
    # locale tags plus the common "traditional" alias.
    "traditional-chinese": "zh-hant", "traditional_chinese": "zh-hant",
    "zh-tw": "zh-hant", "zh-hk": "zh-hant", "zh-mo": "zh-hant",
    "japanese": "ja", "jp": "ja", "ja-jp": "ja",
    "german": "de", "deutsch": "de", "de-de": "de", "de-at": "de", "de-ch": "de",
    "spanish": "es", "español": "es", "espanol": "es", "es-es": "es", "es-mx": "es", "es-ar": "es",
    "french": "fr", "français": "fr", "france": "fr", "fr-fr": "fr", "fr-be": "fr", "fr-ca": "fr", "fr-ch": "fr",
    "ukrainian": "uk", "ukrainisch": "uk", "українська": "uk", "uk-ua": "uk", "ua": "uk",
    "turkish": "tr", "türkçe": "tr", "tr-tr": "tr",
    # Afrikaans — South African Dutch-derived language; "af-ZA" is the common BCP-47 tag.
    "afrikaans": "af", "af-za": "af",
    # Korean
    "korean": "ko", "한국어": "ko", "ko-kr": "ko",
    # Torbeški — the community's own names. The code is not ISO, so the natural
    # spellings have to be listed explicitly; otherwise a user typing their own
    # language name silently lands on English.
    "torbeški": "torbeski", "torbeshki": "torbeski", "torbesh": "torbeski",
    "торбешки": "torbeski", "нашински": "torbeski", "nasinski": "torbeski",
    # Italian
    "italian": "it", "italiano": "it", "it-it": "it", "it-ch": "it",
    # Irish (Gaeilge) — ga is the BCP-47 code
    "irish": "ga", "gaeilge": "ga", "ga-ie": "ga",
    # Portuguese — bare "portuguese" routes to European Portuguese; pt-br
    # is in the same family but rendered identically here (no separate br catalog).
    "portuguese": "pt", "português": "pt", "portugues": "pt",
    "pt-pt": "pt", "pt-br": "pt", "brazilian": "pt", "brasileiro": "pt",
    # Russian
    "russian": "ru", "русский": "ru", "ru-ru": "ru",
    # Hungarian
    "hungarian": "hu", "magyar": "hu", "hu-hu": "hu",
    # Arabic — bare "arabic"/endonym plus the common regional BCP-47 tags.
    "arabic": "ar", "العربية": "ar",
    "ar-sa": "ar", "ar-eg": "ar", "ar-ae": "ar", "ar-ma": "ar", "ar-dz": "ar",
}

_catalog_cache: dict[str, dict[str, str]] = {}
_catalog_lock = threading.Lock()


def _locales_dir() -> Path:
    """Return the directory containing locale YAML files.

    Resolution order, first existing wins:

    1. ``OPENAMER_BUNDLED_LOCALES`` env var -- set by the Nix wrapper (or any
       sealed-packaging system) to point at the installed catalog directory.
    2. ``<repo-root>/locales`` -- source checkouts and editable installs,
       where the working tree sits next to ``agent/``.

    Falling through to the source-style path (even when missing) keeps
    ``_load_catalog`` error messages informative -- it logs the path it
    looked at -- rather than raising.
    """
    override = os.getenv("OPENAMER_BUNDLED_LOCALES", "").strip()
    if override:
        candidate = Path(override)
        if candidate.is_dir():
            return candidate
        logger.warning(
            "OPENAMER_BUNDLED_LOCALES points to a non-directory path (%s); "
            "falling back to bundled/source locale resolution",
            override,
        )

    # agent/i18n.py -> agent/ -> repo root (source checkout, editable install)
    source_dir = Path(__file__).resolve().parent.parent / "locales"
    return source_dir


def _normalize_lang(value: Any) -> str:
    """Normalize a user-supplied language value to a supported code.

    Accepts supported codes directly, common aliases (``chinese`` -> ``zh``),
    and case-insensitive regional tags (``zh-CN`` -> ``zh``).  Returns the
    default language for unknown values.
    """
    if not isinstance(value, str):
        return DEFAULT_LANGUAGE
    key = value.strip().lower()
    if not key:
        return DEFAULT_LANGUAGE
    if key in SUPPORTED_LANGUAGES:
        return key
    if key in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[key]
    # Try stripping a region suffix (e.g. "pt-br" -> "pt" won't be supported,
    # but "zh-CN" -> "zh" will).
    base = key.split("-", 1)[0]
    if base in SUPPORTED_LANGUAGES:
        return base
    return DEFAULT_LANGUAGE


def _load_catalog(lang: str) -> dict[str, str]:
    """Load and flatten one locale YAML file into a dotted-key dict.

    YAML files can be nested for human readability; this produces the flat
    key space :func:`t` expects.  Cached per-language for the process.
    """
    with _catalog_lock:
        cached = _catalog_cache.get(lang)
        if cached is not None:
            return cached

    path = _locales_dir() / f"{lang}.yaml"
    if not path.is_file():
        logger.debug("i18n catalog missing for %s at %s", lang, path)
        with _catalog_lock:
            _catalog_cache[lang] = {}
        return {}

    try:
        import yaml  # PyYAML is already a openamer dependency
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning("Failed to load i18n catalog %s: %s", path, exc)
        with _catalog_lock:
            _catalog_cache[lang] = {}
        return {}

    flat: dict[str, str] = {}
    _flatten_into(raw, "", flat)
    with _catalog_lock:
        _catalog_cache[lang] = flat
    return flat


def _flatten_into(node: Any, prefix: str, out: dict[str, str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            child_key = f"{prefix}.{key}" if prefix else str(key)
            _flatten_into(value, child_key, out)
    elif isinstance(node, str):
        out[prefix] = node
    # Non-string, non-dict leaves are ignored -- catalogs are text-only.


@lru_cache(maxsize=1)
def _config_language_cached() -> str | None:
    """Read ``display.language`` from config.yaml once per process.

    Cached because ``t()`` is called in hot paths (every approval prompt,
    every gateway reply) and re-reading YAML each call would be wasteful.
    ``reset_language_cache()`` clears this when config changes at runtime
    (e.g. after the setup wizard).
    """
    try:
        from openamer_cli.config import load_config
        cfg = load_config()
        lang = (cfg.get("display") or {}).get("language")
        if lang:
            return _normalize_lang(lang)
    except Exception as exc:
        logger.debug("Could not read display.language from config: %s", exc)
    return None


def reset_language_cache() -> None:
    """Invalidate cached language resolution and catalogs.

    Call after :func:`openamer_cli.config.save_config` if a running process
    needs to pick up a changed ``display.language`` without restart.
    """
    _config_language_cached.cache_clear()
    with _catalog_lock:
        _catalog_cache.clear()


def _get_system_locale_language() -> str | None:
    """Best-effort system locale detection as final fallback.

    Reads OS locale via Python's ``locale`` module and environment variables
    (LC_ALL, LC_LANG, LANG), normalizes through ``_normalize_lang``, and
    returns a supported language code or None.
    """
    import locale as _locale

    candidates: list[str | None] = []
    try:
        candidates.append(_locale.getdefaultlocale()[0])
    except Exception:
        pass
    try:
        candidates.append(_locale.getlocale()[0])
    except Exception:
        pass
    for env_var in ("LC_ALL", "LC_LANG", "LANG"):
        candidates.append(os.environ.get(env_var))

    for raw in candidates:
        if not raw or not isinstance(raw, str):
            continue
        normalized = _normalize_lang(raw)
        if normalized and normalized != DEFAULT_LANGUAGE:
            return normalized
    return None


def get_language() -> str:
    """Resolve the active language using env > config > system locale > default order."""
    env_lang = os.environ.get("OPENAMER_LANGUAGE")
    if env_lang:
        return _normalize_lang(env_lang)
    cfg_lang = _config_language_cached()
    if cfg_lang:
        return cfg_lang
    sys_lang = _get_system_locale_language()
    if sys_lang:
        return sys_lang
    return DEFAULT_LANGUAGE


def t(key: str, lang: str | None = None, **format_kwargs: Any) -> str:
    """Translate a dotted key to the active language.

    Parameters
    ----------
    key
        Dotted path into the catalog, e.g. ``"approval.choose_long"``.
    lang
        Explicit language override.  Takes precedence over env + config.
    **format_kwargs
        ``str.format`` substitution arguments (``t("gateway.drain", count=3)``
        expects a catalog entry with a ``{count}`` placeholder).

    Returns
    -------
    The translated string, or the English fallback if the key is missing in
    the target language, or the bare key if English is also missing.
    """
    target = _normalize_lang(lang) if lang else get_language()
    catalog = _load_catalog(target)
    value = catalog.get(key)

    if value is None and target != DEFAULT_LANGUAGE:
        # Fall through to English rather than showing a key path to the user.
        value = _load_catalog(DEFAULT_LANGUAGE).get(key)

    if value is None:
        # Last-ditch: return the key itself.  A broken catalog should not
        # crash anything; it just looks ugly until someone fixes it.
        logger.debug("i18n miss: key=%r lang=%r", key, target)
        value = key

    if format_kwargs:
        try:
            return value.format(**format_kwargs)
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning(
                "i18n format failed for key=%r lang=%r kwargs=%r: %s",
                key, target, format_kwargs, exc,
            )
            return value
    return value


__all__ = [
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
    "t",
    "get_language",
    "reset_language_cache",
]

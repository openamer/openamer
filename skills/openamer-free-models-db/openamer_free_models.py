#!/usr/bin/env python3
"""
OpenAmer Free Provider & Model Database - Query Tool

Usage:
  python openamer_free_models.py list-providers
  python openamer_free_models.py list-models <provider_id>
  python openamer_free_models.py search <query>
  python openamer_free_models.py recommend <use-case>
  python openamer_free_models.py stats
"""

import json
import sys
import os
from typing import List, Dict, Any

DB_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "openamer-laptop",
    "skills", "openamer-free-models-db", "openamer_free_models_db.json"
)


def load_db() -> Dict[str, Any]:
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_providers(db: Dict[str, Any]) -> None:
    """List all free API providers."""
    print("=" * 80)
    print("FREE LLM API PROVIDERS (verified, 2026)")
    print("=" * 80)
    print(f"{'#':<4} {'Provider':<30} {'Modelle':<8} {'Online':<8} {'Card':<6} {'Key':<6} {'OpenAI-kompatibel':<18} {'Rate Limits'}")
    print("-" * 80)
    for i, p in enumerate(db["providers"], 1):
        card = "Nein" if not p["credit_card_required"] else "Ja"
        key = "Nein" if not p["api_key_required"] else "Ja"
        oai = "Ja" if p["openai_compatible"] else "Nein"
        print(f"{i:<4} {p['name']:<30} {str(p['free_models_count']):<8} "
              f"{str(p['online_models_count']):<8} {card:<6} {key:<6} {oai:<18} {p['rate_limits'][:50]}")
    print(f"\nTotal: {len(db['providers'])} providers")
    print(f"Meta: {db['meta'].get('total_free_api_providers_referenced', 'n/a')} providers, {db['meta'].get('total_free_api_models_referenced', 'n/a')} models claimed by directory")


def list_models(db: Dict[str, Any], provider_id: str) -> None:
    """List free models for a specific provider."""
    provider = None
    for p in db["providers"]:
        if p["id"] == provider_id:
            provider = p
            break

    if not provider:
        print(f"Provider '{provider_id}' not found.")
        print("Available providers:", ", ".join(p["id"] for p in db["providers"]))
        return

    print("=" * 80)
    print(f"FREE MODELS - {provider['name']}")
    print("=" * 80)
    print(f"Website: {provider['website']}")
    print(f"Base URL: {provider['base_url']}")
    print(f"OpenAI-kompatibel: {'Ja' if provider['openai_compatible'] else 'Nein'}")
    print(f"API-Key erforderlich: {'Ja' if provider['api_key_required'] else 'Nein (keyless)'}")
    print(f"Kreditkarte erforderlich: {'Ja' if provider['credit_card_required'] else 'Nein'}")
    print(f"Rate Limits: {provider['rate_limits']}")
    print(f"Modalities: {', '.join(provider['modalities'])}")
    print(f"Anzahl Free-Modelle: {provider['free_models_count']} (davon online: {provider['online_models_count']})")
    print("-" * 80)
    for i, m in enumerate(provider["free_models"], 1):
        print(f"  {i:2d}. {m}")
    print(f"\nNotes: {provider['notes']}")


def search(db: Dict[str, Any], query: str) -> None:
    """Search providers and models by query string."""
    q = query.lower()
    print("=" * 80)
    print(f"SEARCH RESULTS FOR: '{query}'")
    print("=" * 80)

    found = False
    for p in db["providers"]:
        # Search in provider name, notes, models
        matches = []
        if q in p["name"].lower() or q in p["notes"].lower():
            matches.append(f"Provider: {p['name']}")
        for m in p.get("free_models", []):
            if q in m.lower():
                matches.append(f"  Modell: {m}")

        if matches:
            found = True
            print(f"\n[{p['id']}] {p['name']}")
            print(f"  Base URL: {p['base_url']}")
            print(f"  Free: {'Ja (keyless)' if not p['api_key_required'] else 'Ja (API-Key)'} | Card: {'Ja' if p['credit_card_required'] else 'Nein'}")
            for match in matches[:5]:
                print(f"  {match}")
            if len(matches) > 5:
                print(f"  ... und {len(matches) - 5} weitere Treffer")

    if not found:
        print("Keine Treffer gefunden.")

    # Also check self-hosted section
    sh = db["self_hosted_open_models"]
    print(f"\n--- Selbst-Hosting (Hugging Face) ---")
    print(f"  {sh['total_models']:,} Open-Weight Modelle verfügbar zum kostenlosen Download")
    print(f"  Top-Familien: {', '.join(sh['top_families'][:5])}")


def recommend(db: Dict[str, Any], use_case: str) -> None:
    """Recommend best free provider for a use case."""
    uc = use_case.lower()
    print("=" * 80)
    print(f"EMPFEHLUNG FÜR: '{use_case}'")
    print("=" * 80)

    recommendations = {
        "allgemein": ["openrouter", "groq", "nvidia_nim"],
        "geschwindigkeit": ["groq", "cerebras"],
        "langes_kontext": ["google_ai_studio", "openrouter"],
        "kein_signup": ["pollinations", "kilo_code", "llm7_io", "opencode_zen"],
        "unbegrenzt": ["self_hosted"],
        "privat": ["self_hosted", "ollama_cloud"],
        "code": ["groq", "openrouter", "github_models"],
        "bild": ["cloudflare_workers_ai", "google_ai_studio", "openrouter"],
        "audio": ["groq", "google_ai_studio", "openrouter"],
    }

    matched = []
    for key, providers in recommendations.items():
        if uc in key or key in uc:
            matched.extend(providers)

    if not matched:
        # Default: show top providers
        matched = ["openrouter", "groq", "google_ai_studio", "nvidia_nim"]

    seen = set()
    for pid in matched:
        if pid in seen:
            continue
        seen.add(pid)
        for p in db["providers"]:
            if p["id"] == pid:
                print(f"\n>>> {p['name']} ({p['website']})")
                print(f"    Base URL: {p['base_url']}")
                print(f"    Free-Modelle: {p['free_models_count']} | Online: {p['online_models_count']}")
                print(f"    API-Key: {'erforderlich' if p['api_key_required'] else 'nein (keyless)'} | "
                      f"Karte: {'erforderlich' if p['credit_card_required'] else 'nein'}")
                print(f"    Rate Limits: {p['rate_limits']}")
                print(f"    Top-Modelle: {', '.join(p['top_models'][:3])}")
                print(f"    OpenAI-kompatibel: {'Ja' if p['openai_compatible'] else 'Nein'}")
                break

    print("\n--- Selbst-Hosting-Alternative ---")
    sh = db["self_hosted_open_models"]
    print(f"  Hugging Face: {sh['total_models']:,} Open-Weight Modelle (kostenloser Download)")
    print(f"  Lokal auf deiner NPU/GPU laufen lassen - keine API-Limits, keine Kosten nach Setup")
    print(f"  Beispiele: {', '.join(sh['example_free_local_models'][:4])}")


def stats(db: Dict[str, Any]) -> None:
    """Show database statistics."""
    print("=" * 80)
    print("OPENAMER FREE MODEL DATABASE - STATISTIKEN")
    print("=" * 80)
    m = db["meta"]
    print(f"Erstellt am: {m['generated_at']}")
    print(f"Verifizierte Free-API-Provider (detailliert): {len(db['providers'])}")
    print(f"Free-API-Provider (referenziert aus Verzeichnis): {m.get('total_free_api_providers_referenced', 'n/a')}")
    print(f"Free-API-Modelle (referenziert): {m.get('total_free_api_models_referenced', 'n/a')}")
    print(f"Free-API-Modelle (freellm.net): {m.get('total_free_api_models_from_freellm_net', 'n/a')}")
    print(f"Selbst-gehostete Open-Weight-Modelle (Hugging Face): {m['total_self_hosted_open_weight_models']:,}")
    print(f"\nAnbieter in dieser DB: {len(db['providers'])}")

    # Count by category
    categories = {}
    for p in db["providers"]:
        cat = p["category"]
        categories[cat] = categories.get(cat, 0) + 1
    print(f"\nNach Kategorien:")
    for cat, count in categories.items():
        print(f"  {cat}: {count}")

    # Count keyless
    keyless = [p for p in db["providers"] if not p["api_key_required"]]
    print(f"\nKeyless (kein API-Key): {len(keyless)}")
    for p in keyless:
        print(f"  - {p['name']}")

    # Count no card
    no_card = [p for p in db["providers"] if not p["credit_card_required"]]
    print(f"\nOhne Kreditkarte: {len(no_card)} Anbieter")

    print(f"\nSelbst-Hosting: {db['self_hosted_open_models']['total_models']:,} Modelle auf Hugging Face")
    print(f"  Datasets: {db['self_hosted_open_models']['total_datasets']:,}")
    print(f"  Spaces: {db['self_hosted_open_models']['total_spaces']:,}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python openamer_free_models.py <command> [args]")
        print("Commands: list-providers, list-models <id>, search <query>, recommend <use-case>, stats")
        sys.exit(1)

    db = load_db()
    cmd = sys.argv[1]

    if cmd == "list-providers":
        list_providers(db)
    elif cmd == "list-models":
        if len(sys.argv) < 3:
            print("Usage: python openamer_free_models.py list-models <provider_id>")
            sys.exit(1)
        list_models(db, sys.argv[2])
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python openamer_free_models.py search <query>")
            sys.exit(1)
        search(db, " ".join(sys.argv[2:]))
    elif cmd == "recommend":
        if len(sys.argv) < 3:
            print("Usage: python openamer_free_models.py recommend <use-case>")
            sys.exit(1)
        recommend(db, " ".join(sys.argv[2:]))
    elif cmd == "stats":
        stats(db)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()

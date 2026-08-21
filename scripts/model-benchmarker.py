#!/usr/bin/env python3
"""
Model Benchmarker — KI-Modell-Performance-Tests

Tests für Provider-Modelle:
  a) Latenz: Zeit bis first token (kleiner Prompt, 10 Runs, Median)
  b) Durchsatz: tokens/sec (großer Prompt ~4K Tokens, 5 Runs)
  c) Qualität: definierte Testfragen + Antwort-Bewertung (Länge, Keywords)

Provider-Konfiguration aus OpenAmer config.yaml
Ergebnisse in ~/.model-benchmarks/results/<provider>-<model>.json

CLI:
  --run <provider/model>      Einmaliger Test
  --compare                    Alle getesteten Modelle vergleichen
  --history <provider>         Trend für einen Provider
  --all                        Alle Provider testen
  --json                       JSON-Ausgabe (für --compare)

Abhängigkeiten: Keine (nur Python-Standardbibliothek: urllib, json, statistics, etc.)
"""

import argparse
import json
import os
import re
import sys
import time
import statistics
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── Konfiguration ──────────────────────────────────────────────────────────────
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "openamer-laptop"),
))
CONFIG_PATH = OPENAMER_HOME / "config.yaml"
ENV_PATH = OPENAMER_HOME / ".env"

RESULTS_DIR = Path.home() / ".model-benchmarks" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_TIMEOUT = 180

# ── Test-Prompts ──────────────────────────────────────────────────────────────
SMALL_PROMPT = "Antworte in einem Satz: Was ist die Hauptstadt von Frankreich?"

LARGE_PROMPT = (
    "Erkläre ausführlich die Ursachen und Folgen des Zweiten Weltkriegs. "
    "Gehe dabei auf folgende Aspekte ein:\n"
    "1. Politische Ursachen (Versailler Vertrag, Aufstieg des Nationalsozialismus, Appeasement-Politik)\n"
    "2. Wirtschaftliche Faktoren (Weltwirtschaftskrise, Aufrüstung)\n"
    "3. Der Kriegsverlauf in Europa und im Pazifik\n"
    "4. Die Rolle der USA und der Sowjetunion\n"
    "5. Der Holocaust\n"
    "6. Folgen: Teilung Deutschlands, Kalter Krieg, Gründung der UNO, Entkolonialisierung\n"
    "7. Langfristige Auswirkungen auf Europa und die Weltordnung\n\n"
    "Bitte gib eine detaillierte und strukturierte Antwort mit mindestens 800 Wörtern."
)

QUALITY_QUESTIONS = [
    {
        "question": "Was ist 7 * 8 + 12? Zeige den Rechenweg.",
        "required_keywords": ["56", "68", "7", "8", "12"],
        "min_length": 20,
    },
    {
        "question": "Erkläre den Unterschied zwischen HTML und CSS in 2-3 Sätzen.",
        "required_keywords": ["HTML", "CSS", "Struktur", "Stil", "Inhalt", "Layout",
                             "Aussehen", "Definition"],
        "min_length": 60,
    },
    {
        "question": "Nenne drei Hauptstädte europäischer Länder und ihre Länder.",
        "required_keywords": ["Paris", "Berlin", "London", "Rom", "Madrid", "Wien",
                             "Frankreich", "Deutschland", "Italien", "Spanien"],
        "min_length": 40,
    },
    {
        "question": "Schreibe einen kurzen Python-Code, der 'Hallo Welt' ausgibt.",
        "required_keywords": ["print", "Hallo", "Python", "Welt"],
        "min_length": 30,
    },
]


# ── Config lesen ───────────────────────────────────────────────────────────────
def read_config():
    """Liest OpenAmer config.yaml und extrahiert Provider-Konfiguration."""
    config = {
        "default_provider": "openrouter",
        "default_model": None,
        "base_url": "https://openrouter.ai/api/v1",
        "providers": {},
    }

    if not CONFIG_PATH.exists():
        config["providers"]["openrouter"] = {
            "name": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "models": [config["default_model"]] if config["default_model"] else [],
        }
        return config

    content = CONFIG_PATH.read_text(encoding="utf-8")

    # ── model: section (top-level) ──────────────────────────────────────────
    # Find lines starting at column 0: model: then read indented sub-keys
    lines = content.splitlines()
    in_model_section = False
    for line in lines:
        # Track section boundaries by indent
        if re.match(r'^\w', line) and not line.startswith(" "):
            in_model_section = False  # new top-level key
        if line.strip() == "model:" or line.rstrip() == "model:":
            in_model_section = True
            continue
        if in_model_section and line.startswith("  "):
            stripped = line.strip()
            if stripped.startswith("default:"):
                val = stripped.split(":", 1)[1].strip().strip("\"'")
                if "/" in val:
                    parts = val.split("/", 1)
                    config["default_provider"] = parts[0].strip().lower()
                    config["default_model"] = parts[1].strip()
            if stripped.startswith("provider:"):
                config["default_provider"] = stripped.split(":", 1)[1].strip().strip("\"'").strip().lower()
            if stripped.startswith("base_url:"):
                raw = stripped.split(":", 1)[1].strip().strip("\"'").strip("'")
                if raw:
                    config["base_url"] = raw
            continue
        if in_model_section and not line.startswith(" "):
            in_model_section = False

    # Parse custom_providers
    in_custom = False
    current_provider = None
    in_models = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped.startswith("custom_providers:"):
            in_custom = True
            continue

        if not in_custom:
            continue

        if stripped.startswith("- name:"):
            if current_provider and current_provider.get("models"):
                config["providers"][current_provider["name"].lower()] = current_provider
            pname = stripped.split(":", 1)[1].strip().strip("\"'")
            current_provider = {"name": pname, "base_url": "", "models": []}
            in_models = False
            continue

        if current_provider is None:
            if stripped.startswith("plugins:") or stripped.startswith("platforms:"):
                break
            continue

        if stripped.startswith("base_url:"):
            current_provider["base_url"] = stripped.split(":", 1)[1].strip().strip("\"'")
            in_models = False
            continue

        if stripped.startswith("models:"):
            in_models = True
            continue

        if in_models and stripped.startswith("- "):
            model_name = stripped[2:].strip().strip("\"'")
            current_provider["models"].append(model_name)
            continue

        if stripped.startswith("plugins:") or stripped.startswith("platforms:"):
            break

        # Non-model line inside provider - reset model flag
        in_models = False

    # Save last provider
    if current_provider and current_provider.get("models"):
        config["providers"][current_provider["name"].lower()] = current_provider

    # Ensure OpenRouter is present
    if "openrouter" not in config["providers"]:
        config["providers"]["openrouter"] = {
            "name": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "models": [config["default_model"]] if config["default_model"] else [],
        }

    if config["providers"]["openrouter"]["models"]:
        pass
    elif config["default_model"]:
        config["providers"]["openrouter"]["models"] = [config["default_model"]]

    return config


def get_api_key(provider_name):
    """Holt API-Key aus .env."""
    try:
        if ENV_PATH.exists():
            text = ENV_PATH.read_text(encoding="utf-8")
            prefix = provider_name.upper().replace(" ", "_") + "_API_KEY"
            for line in text.splitlines():
                ls = line.strip()
                if ls.startswith("OPENROUTER_API_KEY"):
                    return ls.split("=", 1)[1].strip().strip("\"'").strip("'")
                if ls.startswith(prefix):
                    return ls.split("=", 1)[1].strip().strip("\"'").strip("'")
    except Exception:
        pass
    return ""


# ── API-Kommunikation ─────────────────────────────────────────────────────────
def call_api(url, headers, payload, stream=False):
    """Führt API-Call durch. Misst Zeit bis erster Chunk (stream) oder Dauer."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")

    start = time.monotonic()

    if stream:
        resp = urlopen(req, timeout=REQUEST_TIMEOUT)
        first_chunk_time = None
        full_content = []
        total_received = 0

        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            total_received += len(chunk)
            if first_chunk_time is None:
                first_chunk_time = time.monotonic()
            full_content.append(chunk)

        end = time.monotonic()
        full_response = b"".join(full_content).decode("utf-8", errors="replace")
        ttft = first_chunk_time - start if first_chunk_time else end - start
        total_duration = end - start

        return {
            "text": full_response,
            "time_to_first_token": ttft,
            "total_duration": total_duration,
            "total_bytes": total_received,
        }
    else:
        resp = urlopen(req, timeout=REQUEST_TIMEOUT)
        content = resp.read()
        end = time.monotonic()
        text = content.decode("utf-8", errors="replace")
        return {
            "text": text,
            "time_to_first_token": end - start,
            "total_duration": end - start,
            "total_bytes": len(content),
        }


def parse_streamed_text(raw_text):
    """Extrahiert Text aus Server-Sent Events (streaming response)."""
    collected = []
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                continue
            try:
                chunk = json.loads(data_str)
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                content = delta.get("content", "")
                if content:
                    collected.append(content)
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
        elif line.startswith("data:{"):
            # compact SSE
            data_str = line[5:]
            try:
                chunk = json.loads(data_str)
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                content = delta.get("content", "")
                if content:
                    collected.append(content)
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
    return "".join(collected)


def parse_nonstreamed_text(raw_text):
    """Extrahiert Text aus non-streaming JSON-Response."""
    try:
        data = json.loads(raw_text)
        choices = data.get("choices", [])
        if choices:
            choice = choices[0]
            if "message" in choice:
                return choice["message"].get("content", "")
            if "text" in choice:
                return choice["text"]
        # Fallback: raw
        return json.dumps(data, indent=2)
    except (json.JSONDecodeError, TypeError):
        return raw_text


def parse_completion(response_data):
    """Extrahiert Text aus API-Response (streamed oder non-streamed)."""
    raw = response_data["text"] if isinstance(response_data, dict) else str(response_data)
    if not raw:
        return ""
    # Try streamed first
    text = parse_streamed_text(raw)
    if text:
        return text
    # Try non-streamed JSON
    return parse_nonstreamed_text(raw)


# ── Benchmark-Tests ────────────────────────────────────────────────────────────
def test_latency(url, headers, model, runs=10):
    """Testet Latenz (Time-to-first-token) mit kleinem Prompt."""
    latencies = []
    responses = []

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": SMALL_PROMPT}],
        "max_tokens": 50,
        "temperature": 0.0,
        "stream": True,
    }

    for i in range(runs):
        try:
            result = call_api(url, headers, payload, stream=True)
            latency = result["time_to_first_token"]
            text = parse_completion(result)
            latencies.append(latency)
            responses.append(text)
            print(".", end="", flush=True)
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            print(f"\n  ⚠ Latenz Run {i+1}: HTTP {e.code} — {body}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"\n  ⚠ Latenz Run {i+1}: {e}", file=sys.stderr)
            continue

    if not latencies:
        return {"error": "Alle Runs fehlgeschlagen"}

    return {
        "runs": len(latencies),
        "median": round(statistics.median(latencies), 4),
        "mean": round(statistics.mean(latencies), 4),
        "min": round(min(latencies), 4),
        "max": round(max(latencies), 4),
        "stdev": round(statistics.stdev(latencies), 4) if len(latencies) > 1 else 0,
        "all_latencies": [round(l, 4) for l in latencies],
        "sample_response": (responses[0] or "")[:200],
    }


def test_throughput(url, headers, model, runs=5):
    """Testet Durchsatz (tokens/sec) mit großem Prompt."""
    throughputs = []

    for i in range(runs):
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": LARGE_PROMPT}],
                "max_tokens": 1024,
                "temperature": 0.0,
                "stream": True,
            }
            result = call_api(url, headers, payload, stream=True)
            text = parse_completion(result)

            # Token-Schätzung: ~4 Zeichen pro Token (Deutsch/Englisch)
            char_count = len(text)
            estimated_tokens = max(1, char_count // 4)
            duration = result["total_duration"]
            tokens_per_sec = estimated_tokens / duration if duration > 0 else 0

            throughputs.append({
                "tokens_per_sec": round(tokens_per_sec, 2),
                "char_count": char_count,
                "estimated_tokens": estimated_tokens,
                "duration_sec": round(duration, 2),
            })
            print(".", end="", flush=True)
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            print(f"\n  ⚠ Durchsatz Run {i+1}: HTTP {e.code} — {body}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"\n  ⚠ Durchsatz Run {i+1}: {e}", file=sys.stderr)
            continue

    if not throughputs:
        return {"error": "Alle Runs fehlgeschlagen"}

    tps_values = [t["tokens_per_sec"] for t in throughputs]

    return {
        "runs": len(throughputs),
        "median_tps": round(statistics.median(tps_values), 2),
        "mean_tps": round(statistics.mean(tps_values), 2),
        "min_tps": round(min(tps_values), 2),
        "max_tps": round(max(tps_values), 2),
        "all_runs": throughputs,
    }


def test_quality(url, headers, model):
    """Testet Antwortqualität mit definierten Fragen."""
    scores = []
    details = []

    for idx, q in enumerate(QUALITY_QUESTIONS):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": q["question"]}],
            "max_tokens": 512,
            "temperature": 0.0,
            "stream": True,
        }

        try:
            result = call_api(url, headers, payload, stream=True)
            text = parse_completion(result)

            # Längen-Score
            min_len = q.get("min_length", 1)
            length_score = min(100, (len(text) / min_len) * 100)

            # Keyword-Score
            missing_keywords = []
            found_keywords = []
            text_lower = text.lower()
            for kw in q["required_keywords"]:
                kw_clean = kw.strip("\"'")
                if kw_clean.lower() in text_lower:
                    found_keywords.append(kw_clean)
                else:
                    missing_keywords.append(kw_clean)

            keyword_score = (
                (len(found_keywords) / len(q["required_keywords"])) * 100
                if q["required_keywords"]
                else 100
            )

            total_score = round((length_score + keyword_score) / 2, 1)
            scores.append(total_score)

            details.append({
                "question": q["question"],
                "answer_length": len(text),
                "length_score": round(length_score, 1),
                "keyword_score": round(keyword_score, 1),
                "found_keywords": found_keywords,
                "missing_keywords": missing_keywords,
                "total_score": total_score,
                "answer_preview": text[:200],
            })
            print(".", end="", flush=True)
        except Exception as e:
            print(f"\n  ⚠ Qualitätstest Frage {idx+1}: {e}", file=sys.stderr)
            details.append({
                "question": q["question"],
                "error": str(e),
                "total_score": 0,
            })

    overall_score = round(statistics.mean(scores), 1) if scores else 0

    return {
        "overall_quality_score": overall_score,
        "questions_tested": len(QUALITY_QUESTIONS),
        "details": details,
    }


# ── Ergebnisse speichern ───────────────────────────────────────────────────────
def save_result(provider, model, latency, throughput, quality):
    """Speichert Ergebnis mit Historie."""
    timestamp = datetime.now(timezone.utc).isoformat()
    safe_model = model.replace("/", "-").replace(":", "-").replace(" ", "_")
    result_file = RESULTS_DIR / f"{provider}-{safe_model}.json"

    entry = {
        "timestamp": timestamp,
        "provider": provider,
        "model": model,
        "latency": latency,
        "throughput": throughput,
        "quality": quality,
    }

    # Historie laden
    history = []
    if result_file.exists():
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                history = data
            elif isinstance(data, dict):
                if "history" in data:
                    history = data["history"]
                elif "timestamp" in data:
                    history = [data]
        except (json.JSONDecodeError, Exception):
            history = []

    history.append(entry)

    # Max 50 Einträge halten
    if len(history) > 50:
        history = history[-50:]

    output = {"latest": entry, "history": history}
    result_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result_file


def run_benchmark(provider_name, model_name, base_url, api_key):
    """Führt vollständigen Benchmark für ein Modell durch."""
    print(f"\n{'=' * 60}")
    print(f"  Benchmark: {provider_name}/{model_name}")
    print(f"{'=' * 60}")

    # URL zusammenbauen
    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
    }

    if "openrouter" in url:
        headers["HTTP-Referer"] = "https://github.com/openamer"
        headers["X-Title"] = "OpenAmer Model Benchmarker"

    print(f"  URL: {url}")
    print(f"  Modell: {model_name}")

    # 1. Latenztest
    print(f"\n  📊 Latenz (10 Runs): ", end="", flush=True)
    latency = test_latency(url, headers, model_name)
    if "error" in latency:
        print(f"\n  ❌ {latency['error']}")
    else:
        print(
            f"\n  ✅ Median: {latency['median']:.4f}s | "
            f"Mean: {latency['mean']:.4f}s | "
            f"Bereich: {latency['min']:.4f}s – {latency['max']:.4f}s"
        )

    # 2. Durchsatz
    print(f"\n  📊 Durchsatz (5 Runs): ", end="", flush=True)
    throughput = test_throughput(url, headers, model_name)
    if "error" in throughput:
        print(f"\n  ❌ {throughput['error']}")
    else:
        print(
            f"\n  ✅ Median: {throughput['median_tps']} tok/s | "
            f"Bereich: {throughput['min_tps']} – {throughput['max_tps']} tok/s"
        )

    # 3. Qualität
    print(f"\n  📊 Qualität ({len(QUALITY_QUESTIONS)} Fragen): ", end="", flush=True)
    quality = test_quality(url, headers, model_name)
    print(f"\n  ✅ Gesamtqualität: {quality['overall_quality_score']}/100")

    # Ergebnis speichern
    result_path = save_result(provider_name, model_name, latency, throughput, quality)
    print(f"\n  💾 Ergebnis gespeichert: {result_path}")

    return {
        "provider": provider_name,
        "model": model_name,
        "latency": latency,
        "throughput": throughput,
        "quality": quality,
    }


# ── Reports ────────────────────────────────────────────────────────────────────
def generate_comparison(json_output=False):
    """Generiert Vergleichstabelle aller getesteten Modelle."""
    result_files = list(RESULTS_DIR.glob("*.json"))

    if not result_files:
        msg = "❌ Keine Benchmark-Ergebnisse gefunden.\n" \
              f"   Ergebnisverzeichnis: {RESULTS_DIR}\n" \
              "   Führe zuerst 'model-benchmarker.py --run <provider/model>' aus."
        print(msg)
        return

    rows = []
    for rf in sorted(result_files):
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            latest = data.get("latest", {})
            if not latest:
                hist = data.get("history", [])
                if hist:
                    latest = hist[-1]
                elif "timestamp" in data:
                    latest = data

            latency = latest.get("latency", {})
            throughput = latest.get("throughput", {})
            quality = latest.get("quality", {})

            rows.append({
                "provider": latest.get("provider", "?"),
                "model": latest.get("model", "?"),
                "latency_median": latency.get("median"),
                "latency_mean": latency.get("mean"),
                "tps_median": throughput.get("median_tps"),
                "tps_mean": throughput.get("mean_tps"),
                "quality_score": quality.get("overall_quality_score"),
                "timestamp": latest.get("timestamp", ""),
                "runs_latency": latency.get("runs", 0),
                "runs_tps": throughput.get("runs", 0),
            })
        except Exception as e:
            print(f"  ⚠ Fehler beim Lesen von {rf.name}: {e}", file=sys.stderr)

    if not rows:
        print("❌ Keine gültigen Benchmark-Ergebnisse gefunden.")
        return

    if json_output:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    # Tabelle
    print()
    print("=" * 110)
    print("  📋  MODEL VERGLEICH (neueste Ergebnisse)")
    print("=" * 110)
    header = f"  {'Provider':<20} {'Modell':<32} {'Latenz(med)':<12} {'Durchsatz':<14} {'Qualität':<10} {'Runs':<8}"
    sep = f"  {'─' * 20} {'─' * 32} {'─' * 12} {'─' * 14} {'─' * 10} {'─' * 8}"
    print(header)
    print(sep)

    for r in rows:
        lat = (
            f"{r['latency_median']:.3f}s"
            if isinstance(r["latency_median"], (int, float))
            else "N/A"
        )
        tps = (
            f"{r['tps_median']:.1f} tok/s"
            if isinstance(r["tps_median"], (int, float))
            else "N/A"
        )
        qual = (
            f"{r['quality_score']:.0f}/100"
            if isinstance(r["quality_score"], (int, float))
            else "N/A"
        )
        runs = f"{r['runs_latency']}/{r['runs_tps']}" if r.get("runs_latency") else "?"
        print(
            f"  {r['provider']:<20} {r['model'][:32]:<32} {lat:<12} {tps:<14} {qual:<10} {runs:<8}"
        )

    print("=" * 110)

    # Bewertung
    valid = [
        r
        for r in rows
        if isinstance(r["latency_median"], (int, float))
        and isinstance(r["tps_median"], (int, float))
    ]
    if valid:
        best_lat = min(valid, key=lambda x: x["latency_median"])
        best_tps = max(valid, key=lambda x: x["tps_median"])
        print(f"\n  🏆 BESTE WERTE:")
        print(f"     ⚡ Latenz:     {best_lat['provider']}/{best_lat['model']}  —  {best_lat['latency_median']:.3f}s")
        print(f"     🚀 Durchsatz:  {best_tps['provider']}/{best_tps['model']}  —  {best_tps['tps_median']:.1f} tok/s")


def show_history(provider):
    """Zeigt Trend für einen Provider."""
    pattern = f"{provider}-*.json"
    result_files = sorted(RESULTS_DIR.glob(pattern))

    if not result_files:
        print(f"❌ Keine Historie für Provider '{provider}' gefunden.")
        print(f"   Suche in: {RESULTS_DIR}/")
        return

    print(f"\n{'=' * 90}")
    print(f"  📈  TREND: {provider.upper()}")
    print(f"{'=' * 90}")

    for rf in result_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            history = data.get("history", [])
            if not history:
                continue

            model = history[-1].get("model", "?")
            print(f"\n  📊 {model}")
            print(
                f"  {'Datum':<22} {'Latenz(med)':<14} {'Durchsatz':<14} {'Qualität':<10}"
            )
            print(f"  {'─' * 22} {'─' * 14} {'─' * 14} {'─' * 10}")

            for entry in history[-10:]:
                ts = entry.get("timestamp", "")[:19].replace("T", " ")
                lat = entry.get("latency", {}).get("median")
                tps = entry.get("throughput", {}).get("median_tps")
                qual = entry.get("quality", {}).get("overall_quality_score")

                lat_str = f"{lat:.3f}s" if isinstance(lat, (int, float)) else "N/A"
                tps_str = f"{tps:.1f}t/s" if isinstance(tps, (int, float)) else "N/A"
                qual_str = f"{qual:.0f}/100" if isinstance(qual, (int, float)) else "N/A"

                print(f"  {ts:<22} {lat_str:<14} {tps_str:<14} {qual_str:<10}")

            print(f"  ({len(history)} Einträge gesamt)")
        except Exception as e:
            print(f"  ⚠ Fehler: {e}")


# ── Hauptprogramm ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Model Benchmarker — KI-Modell-Performance-Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python model-benchmarker.py --run openrouter/deepseek-v4-flash
  python model-benchmarker.py --run "local/qwen3.5:9b"
  python model-benchmarker.py --compare
  python model-benchmarker.py --history openrouter
  python model-benchmarker.py --all
        """,
    )

    parser.add_argument(
        "--run",
        type=str,
        metavar="PROVIDER/MODEL",
        help="Benchmark für ein Modell ausführen (Format: provider/modell-name)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Alle getesteten Modelle vergleichen",
    )
    parser.add_argument(
        "--history",
        type=str,
        metavar="PROVIDER",
        help="Trend-Historie für einen Provider anzeigen",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Alle konfigurierten Provider testen (Standard-Modell pro Provider)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Ausgabe als JSON (für --compare)",
    )

    args = parser.parse_args()

    if not any([args.run, args.compare, args.history, args.all]):
        parser.print_help()
        sys.exit(0)

    if args.compare:
        generate_comparison(json_output=args.json)
        return

    if args.history:
        show_history(args.history)
        return

    if args.run:
        if "/" in args.run:
            provider_name, model_name = args.run.split("/", 1)
            provider_name = provider_name.strip()
            model_name = model_name.strip()
        else:
            print("❌ Bitte Format provider/modell-name verwenden (z.B. openrouter/deepseek-v4-flash)")
            sys.exit(1)

        config = read_config()
        api_key = get_api_key(provider_name)

        provider_lower = provider_name.lower()
        provider_info = config["providers"].get(provider_lower)

        if not provider_info:
            # Fallback: user gave a manual URL? Just try
            print(f"  ⚠ Provider '{provider_name}' nicht in Config. Verwende OpenRouter-Standard.")
            base_url = "https://openrouter.ai/api/v1"
        else:
            base_url = provider_info.get("base_url", "")

        result = run_benchmark(provider_name, model_name, base_url, api_key)

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.all:
        print(f"\n{'#' * 60}")
        print(f"  # MODEL BENCHMARKER — ALLE PROVIDER")
        print(f"{'#' * 60}")

        config = read_config()
        api_key_default = get_api_key("openrouter")
        results = []

        tested = set()

        # 1. OpenRouter Default-Modell
        if config["default_model"] and "openrouter" not in tested:
            print(f"\n{'#' * 60}")
            print(f"  # OpenRouter: {config['default_model']}")
            print(f"{'#' * 60}")
            result = run_benchmark(
                "openrouter",
                config["default_model"],
                "https://openrouter.ai/api/v1",
                api_key_default,
            )
            results.append(result)
            tested.add("openrouter")

        # 2. Custom Providers
        for pname, pinfo in config["providers"].items():
            if pname in tested:
                continue
            models = pinfo.get("models", [])
            if not models:
                continue

            # Take the first model as default
            model = models[0]
            print(f"\n{'#' * 60}")
            print(f"  # {pname}: {model}")
            print(f"{'#' * 60}")
            result = run_benchmark(pname, model, pinfo.get("base_url", ""), "")
            results.append(result)
            tested.add(pname)

        print(f"\n\n{'=' * 60}")
        print(f"  ✅ ALLE BENCHMARKS ABGESCHLOSSEN ({len(results)} Modelle)")
        print(f"{'=' * 60}")
        generate_comparison()


if __name__ == "__main__":
    main()
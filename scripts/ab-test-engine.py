#!/usr/bin/env python3
"""
A/B Test Engine — Experimente für Skills + Configs
====================================================
CLI:
  --create <name> '<desc>' --variant 'key=value[,key=value]'
  --list
  --status <name>
  --conclude <name>
  --collect
  --analyze

Metriken:
  - Cron-Exit-Codes
  - Test-Dauer
  - RAM-Nutzung vor/nach Config-Change

Statistik:
  - t-Test (unabhängige Stichproben)
  - p-Wert
  - Winner-Empfehlung (Cohen's d + Signifikanz)
"""

import argparse
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Konfiguration ───────────────────────────────────────────────────
AB_TESTS_DIR = Path.home() / ".ab-tests"
EXPERIMENTS_DIR = AB_TESTS_DIR / "experiments"
RESULTS_DIR = AB_TESTS_DIR / "results"
METRICS_DIR = AB_TESTS_DIR / "metrics"

AB_TESTS_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)

OPENAMER_HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData/Local/openamer-laptop")))


# ── Hilfsfunktionen ──────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_exp(name: str) -> dict:
    path = EXPERIMENTS_DIR / f"{name}.json"
    if not path.exists():
        print(f"❌ Experiment '{name}' nicht gefunden.")
        sys.exit(1)
    return json.loads(path.read_text("utf-8"))


def _save_exp(name: str, data: dict):
    path = EXPERIMENTS_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def _load_results(name: str) -> dict:
    path = RESULTS_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text("utf-8"))


def _save_results(name: str, data: dict):
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def _read_cron_log() -> list[dict]:
    """Liest letzte Cron-Exit-Codes aus dem OpenAmer-Cron-Log."""
    cron_log = OPENAMER_HOME / "cron/cron.log"
    entries = []
    if not cron_log.exists():
        return entries
    text = cron_log.read_text("utf-8", errors="replace")
    for line in text.strip().split("\n")[-200:]:
        # Format: 2026-08-21 22:00:00 | skill-collect | exit=0 | duration=12.3s | mem_before=2048 | mem_after=2056
        parts = line.split("|")
        if len(parts) >= 3:
            entry = {
                "timestamp": parts[0].strip(),
                "job": parts[1].strip() if len(parts) > 1 else "?",
                "exit_code": int(parts[2].strip().split("=")[1]) if "exit=" in parts[2] else -1,
            }
            for p in parts[3:]:
                if "duration=" in p:
                    entry["duration_s"] = float(p.strip().split("=")[1].replace("s", ""))
                if "mem_before=" in p:
                    entry["mem_before_mb"] = float(p.strip().split("=")[1])
                if "mem_after=" in p:
                    entry["mem_after_mb"] = float(p.strip().split("=")[1])
            entries.append(entry)
    return entries


def _get_current_ram_mb() -> float:
    """Liefert aktuelle RAM-Nutzung des Python-Prozesses in MB."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback: /proc/self/status (Linux/WSL) oder WMIC (Windows)
        if sys.platform.startswith("win"):
            try:
                out = subprocess.check_output(
                    ["wmic", "OS", "get", "FreePhysicalMemory", "/Value"],
                    stderr=subprocess.DEVNULL, text=True, timeout=5
                )
                for line in out.splitlines():
                    if "FreePhysicalMemory" in line:
                        free_kb = int(line.split("=")[1])
                        total = 16 * 1024  # ~16GB Annahme
                        return float(total * 1024 - free_kb)
            except Exception:
                pass
        return 0.0


def _detect_config():
    """Liest aktuelle OpenAmer-Config als Dict."""
    config_path = OPENAMER_HOME / "config.yaml"
    config = {}
    if config_path.exists():
        try:
            import yaml
            config = yaml.safe_load(config_path.read_text("utf-8")) or {}
        except ImportError:
            lines = config_path.read_text("utf-8").splitlines()
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    config[k.strip()] = v.strip()
    return config


def _apply_config(overrides: dict):
    """Wendet Config-Overrides an und speichert sie."""
    config_path = OPENAMER_HOME / "config.yaml"
    if not config_path.exists():
        config_path.write_text("", "utf-8")
    try:
        import yaml
        config = yaml.safe_load(config_path.read_text("utf-8")) or {}
    except ImportError:
        config = {}
    config.update(overrides)
    try:
        import yaml
        config_path.write_text(yaml.dump(config, default_flow_style=False), "utf-8")
    except ImportError:
        lines = [f"{k}: {v}" for k, v in config.items()]
        config_path.write_text("\n".join(lines) + "\n", "utf-8")


def _restore_config(original: dict):
    """Stellt ursprüngliche Config wieder her (überschreibt nur die Keys)."""
    config_path = OPENAMER_HOME / "config.yaml"
    try:
        import yaml
        current = yaml.safe_load(config_path.read_text("utf-8")) or {}
    except ImportError:
        current = {}
    current.update(original)
    try:
        import yaml
        config_path.write_text(yaml.dump(current, default_flow_style=False), "utf-8")
    except ImportError:
        pass


# ── Statistik ────────────────────────────────────────────────────────
def _t_test(sample_a: list[float], sample_b: list[float]):
    """
    Welch's t-Test (ungleiche Varianzen).
    Gibt (t_stat, p_value, degrees_of_freedom, cohens_d).
    """
    n1, n2 = len(sample_a), len(sample_b)
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0, 0.0, 0.0

    mean1 = statistics.mean(sample_a)
    mean2 = statistics.mean(sample_b)
    var1 = statistics.variance(sample_a)
    var2 = statistics.variance(sample_b)

    # t-Statistik
    se = math.sqrt(var1 / n1 + var2 / n2)
    t_stat = (mean1 - mean2) / se if se > 0 else 0.0

    # Welch-Satterthwaite df
    num = (var1 / n1 + var2 / n2) ** 2
    denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
    df = num / denom if denom > 0 else 0.0

    # p-Wert (zweiseitig) via Student's t-Verteilung (Näherung)
    p = _t_distribution_2tail(abs(t_stat), df)

    # Cohen's d
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    cohens_d = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0.0

    return t_stat, p, df, cohens_d


def _t_distribution_2tail(t: float, df: float) -> float:
    """
    Zweiseitiger p-Wert der Student's t-Verteilung.
    Nutzt regularisierte unvollständige Beta-Funktion via
    modifizierte Lentz's continued fraction (stabil, genau).
    """
    if df <= 0 or t <= 0:
        return 1.0
    # Für große df: Normalapproximation (schnell)
    if df > 200:
        from math import erf
        return 1.0 - erf(t / math.sqrt(2))

    x = df / (df + t * t)
    a = df / 2.0
    b = 0.5
    # P(T <= t) = 0.5 * I_x(a, 0.5)  where x = df/(df+t^2), symmetric
    # Für t > 0: P(T <= t) = 1 - 0.5 * I_x(a, 0.5) where x = df/(df+t^2)
    # Actually: P(T <= t) = I_x(df/2, 0.5) / 2 for the regularized incomplete beta
    # More precisely: P(T > t) = 0.5 * I_x(a, b) where x = df/(df+t^2)

    # Compute regularized incomplete beta I_x(a, b) via continued fraction
    beta_inc = _reg_inc_beta(x, a, b)

    # One-tailed p = 0.5 * beta_inc  (for t > 0)
    # Two-tailed p = beta_inc
    p_one_tail = 0.5 * beta_inc
    p_two_tail = 2.0 * p_one_tail

    # Clamp
    return max(0.0, min(1.0, p_two_tail))


def _reg_inc_beta(x: float, a: float, b: float) -> float:
    """
    Regularisierte unvollständige Beta-Funktion I_x(a, b)
    via modifizierte Lentz's continued fraction.
    """
    if x < 0 or x > 1:
        return 0.0
    if x == 0 or x == 1:
        return 0.0

    # Log-Beta für Normalisierung
    from math import lgamma, exp
    ln_beta = lgamma(a) + lgamma(b) - lgamma(a + b)

    # Vorsicht: Für x > (a+1)/(a+b+2) nutze Symmetrie
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _reg_inc_beta(1.0 - x, b, a)

    # Lentz's modifizierte continued fraction
    # I_x(a,b) = exp(ln(x)*a + ln(1-x)*(b-1) - ln_beta) * CF
    # wobei CF = 1 / (1 + d1/(1 + d2/(1 + ...)))
    front = exp(a * math.log(x) + (b - 1.0) * math.log(1.0 - x) - ln_beta) / a

    # Continued fraction: Lentz's method
    # f = 1 / (1 + d1/(1 + d2/(1 + ...)))
    f = 1.0
    m = 0
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    f = d
    tol = 1e-12
    max_iter = 200

    for m in range(1, max_iter + 1):
        # Even step (2m)
        numerator = - (a + m) * (a + b + m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = c * d
        f *= delta

        # Odd step (2m+1)
        numerator = m * (b - m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = c * d
        f *= delta

        if abs(delta - 1.0) < tol:
            break

    return front * f


# ── CLI-Befehle ─────────────────────────────────────────────────────

def cmd_create(args):
    """Erstellt ein neues Experiment."""
    name = args.create
    desc = args.description or "A/B Test Experiment"
    variant_str = args.variant or ""

    # Control-Config (aktuell)
    control = _detect_config()

    # Variant-Config aus key=value[,key=value]
    variant = deepcopy(control)
    if variant_str:
        for pair in variant_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                variant[k.strip()] = v.strip()

    experiment = {
        "name": name,
        "description": desc,
        "created_at": _now_iso(),
        "control_config": control,
        "variant_config": variant,
        "metric": "composite",  # default
        "duration_hours": 168,
        "status": "running",
        "started_at": _now_iso(),
    }

    # Ergebnis-Datei initialisieren
    results = {
        "name": name,
        "description": desc,
        "control": {
            "samples": [],
            "exit_codes": [],
            "durations_s": [],
            "ram_before_mb": [],
            "ram_after_mb": [],
            "mean": None,
            "std": None,
            "n": 0,
        },
        "variant": {
            "samples": [],
            "exit_codes": [],
            "durations_s": [],
            "ram_before_mb": [],
            "ram_after_mb": [],
            "mean": None,
            "std": None,
            "n": 0,
        },
        "created_at": _now_iso(),
        "concluded": False,
        "winner": None,
    }

    # Prüfen ob schon existiert
    exp_path = EXPERIMENTS_DIR / f"{name}.json"
    if exp_path.exists():
        print(f"⚠️  Experiment '{name}' existiert bereits. Überschreibe nicht.")
        return

    _save_exp(name, experiment)
    _save_results(name, results)

    print(f"✅ Experiment '{name}' erstellt: {desc}")
    print(f"   Control: {len(control)} Config-Keys")
    print(f"   Variant: {len(variant)} Config-Keys")
    if variant_str:
        print(f"   Delta:   {variant_str}")
    print(f"   Speicherort: {exp_path}")


def cmd_list(args):
    """Listet alle Experimente."""
    experiments = sorted(EXPERIMENTS_DIR.glob("*.json"))
    if not experiments:
        print("📭 Keine Experimente vorhanden.")
        return

    print(f"{'Name':30s} {'Status':12s} {'Metric':12s} {'Erstellt':25s} {'N (Ctrl/Var)':15s}")
    print("-" * 94)
    for exp_path in experiments:
        exp = json.loads(exp_path.read_text("utf-8"))
        name = exp["name"][:28]
        status = exp.get("status", "?")
        metric = exp.get("metric", "?")
        created = exp.get("created_at", "?")[:22]
        res = _load_results(name)
        n_ctrl = len(res.get("control", {}).get("samples", []))
        n_var = len(res.get("variant", {}).get("samples", []))
        print(f"{name:30s} {status:12s} {metric:12s} {created:25s} {n_ctrl}/{n_var:<14d}")


def cmd_status(args):
    """Zeigt Status eines Experiments."""
    name = args.status
    exp = _load_exp(name)
    results = _load_results(name)

    print(f"\n{'='*60}")
    print(f"📊 Experiment: {name}")
    print(f"{'='*60}")
    print(f"  Beschreibung:  {exp.get('description', '–')}")
    print(f"  Status:        {exp.get('status', '?')}")
    print(f"  Metric:        {exp.get('metric', '?')}")
    print(f"  Erstellt:      {exp.get('created_at', '?')}")
    print(f"  Läuft seit:    {exp.get('started_at', '?')}")
    if exp.get("duration_hours"):
        end = datetime.fromisoformat(exp["started_at"]) + timedelta(hours=exp["duration_hours"])
        remaining = end - datetime.now(timezone.utc)
        print(f"  Endet:         {end.isoformat()[:19]} (noch {max(0, int(remaining.total_seconds() / 3600))}h)")

    print(f"\n{'─'*60}")
    print(f"  {'Control':>12s} │ {'Variant':>12s} │ {'Delta':>12s}  Metrik")
    print(f"{'─'*60}")
    ctrl = results.get("control", {})
    var = results.get("variant", {})

    c_mean = ctrl.get("mean")
    v_mean = var.get("mean")
    if c_mean is not None and v_mean is not None:
        delta = v_mean - c_mean
        pct = (delta / c_mean * 100) if c_mean != 0 else 0
        print(f"  {c_mean:>12.4f} │ {v_mean:>12.4f} │ {delta:>+11.4f} ({pct:+.2f}%)  Mittelwert")

    c_std = ctrl.get("std")
    v_std = var.get("std")
    if c_std is not None:
        print(f"  σ={c_std:<10.4f} │ σ={v_std:<10.4f} │ {'':>12s}  Std-Abw.")
    print(f"  n={ctrl.get('n', 0):<10d} │ n={var.get('n', 0):<10d} │ {'':>12s}  Stichproben")

    # Samples (letzte 5)
    c_samples = ctrl.get("samples", [])
    v_samples = var.get("samples", [])
    if c_samples or v_samples:
        print(f"\n  Letzte Werte (Control): {c_samples[-5:] if c_samples else '–'}")
        print(f"  Letzte Werte (Variant): {v_samples[-5:] if v_samples else '–'}")

    if results.get("concluded"):
        print(f"\n  🔬 Ergebnis: {results.get('winner', '–')}")
        if results.get("p_value"):
            print(f"     p-Wert: {results['p_value']:.6f}")
        if results.get("cohens_d"):
            print(f"     Cohen's d: {results['cohens_d']:.4f}")
        if results.get("recommendation"):
            print(f"     Empfehlung: {results['recommendation']}")

    print()


def cmd_conclude(args):
    """Statistische Analyse eines Experiments."""
    name = args.conclude
    _load_exp(name)  # existiert es?
    results = _load_results(name)

    ctrl = results.get("control", {})
    var = results.get("variant", {})

    c_samples = ctrl.get("samples", [])
    v_samples = var.get("samples", [])

    if len(c_samples) < 3 or len(v_samples) < 3:
        print(f"⚠️  Zu wenige Datenpunkte für '{name}'.")
        print(f"   Control: {len(c_samples)} Samples, Variant: {len(v_samples)} Samples")
        print(f"   Mindestens 3 pro Gruppe nötig.")
        return

    t_stat, p_value, df, cohens_d = _t_test(c_samples, v_samples)

    # Winner bestimmen
    c_mean = statistics.mean(c_samples)
    v_mean = statistics.mean(v_samples)

    # Niedrigere Werte = besser (bei Zeit/RAM)
    better = "Variant" if v_mean < c_mean else "Control"
    effect = "klein"
    if abs(cohens_d) >= 0.8:
        effect = "groß"
    elif abs(cohens_d) >= 0.5:
        effect = "mittel"

    significant = p_value < 0.05
    if significant:
        winner = better
        if better == "Variant":
            recommendation = f"👉 **Variant** ist signifikant besser (p={p_value:.6f}, d={cohens_d:.3f}, {effect}er Effekt). Config übernehmen?"
        else:
            recommendation = f"👉 **Control** bleibt Sieger (p={p_value:.6f}, d={cohens_d:.3f}, {effect}er Effekt). Variant nicht besser."
    else:
        winner = "Kein signifikanter Unterschied"
        if p_value < 0.1:
            recommendation = f"⚠️  Trend (p={p_value:.6f}), aber nicht signifikant (α=0.05). Mehr Daten sammeln?"
        else:
            recommendation = f"ℹ️  Kein signifikanter Unterschied (p={p_value:.6f}). Beide Versionen statistisch gleich."

    # Ergebnisse speichern
    results["concluded"] = True
    results["winner"] = winner
    results["t_stat"] = round(t_stat, 6)
    results["p_value"] = round(p_value, 6)
    results["df"] = round(df, 2)
    results["cohens_d"] = round(cohens_d, 4)
    results["effect_size"] = effect
    results["significant"] = significant
    results["recommendation"] = recommendation
    results["control_mean"] = round(c_mean, 6)
    results["variant_mean"] = round(v_mean, 6)
    results["concluded_at"] = _now_iso()
    _save_results(name, results)

    # Experiment-Status updaten
    exp = _load_exp(name)
    exp["status"] = "concluded" if significant else "inconclusive"
    _save_exp(name, exp)

    # Ausgabe
    print(f"\n{'='*60}")
    print(f"🔬 A/B-Test Analyse: {name}")
    print(f"{'='*60}")
    print(f"  Control:   n={len(c_samples):>4d}, μ={c_mean:.4f}, σ={statistics.stdev(c_samples):.4f}")
    print(f"  Variant:   n={len(v_samples):>4d}, μ={v_mean:.4f}, σ={statistics.stdev(v_samples):.4f}")
    print(f"  ────────────────────────────────────────────")
    print(f"  Δ Mittelwert: {v_mean - c_mean:+.6f}")
    print(f"  t-Statistik:  {t_stat:.6f}")
    print(f"  df (Welch):   {df:.2f}")
    print(f"  p-Wert:       {p_value:.6f}  {'✅ signifikant' if significant else '❌ nicht signifikant'}")
    print(f"  Cohen's d:    {cohens_d:.4f}  ({effect}er Effekt)")
    print(f"  ────────────────────────────────────────────")
    print(f"  🏆 Winner: {winner}")
    print(f"  💡 {recommendation}")
    print()


def cmd_collect(args):
    """
    Sammelt Metrik-Daten für alle laufenden Experimente.
    Liest Cron-Exit-Codes, misst RAM, duration.
    """
    experiments = sorted(EXPERIMENTS_DIR.glob("*.json"))
    running = [p for p in experiments if json.loads(p.read_text("utf-8")).get("status") == "running"]

    if not running:
        print("📭 Keine laufenden Experimente.")
        return

    now = _now_iso()
    ram_before = _get_current_ram_mb()
    cron_entries = _read_cron_log()

    collected = 0
    for exp_path in running:
        exp = json.loads(exp_path.read_text("utf-8"))
        name = exp["name"]
        results = _load_results(name)

        # Kategorisiere Cron-Einträge nach Config-Änderungen
        # Wir prüfen, ob gerade die Variant- oder Control-Config aktiv ist
        current_config = _detect_config()

        is_variant = False
        for k, v in exp.get("variant_config", {}).items():
            if k in current_config and str(current_config[k]) == str(v):
                # Prüfen ob sich von Control unterscheidet
                control_v = exp.get("control_config", {}).get(k)
                if str(control_v) != str(v):
                    is_variant = True
                    break

        arm = "variant" if is_variant else "control"

        # Metrik-Sample berechnen
        if cron_entries:
            recent = [e for e in cron_entries if arm in e.get("job", "")]
            if not recent:
                recent = cron_entries[-5:]  # Fallback

            exit_codes = [e.get("exit_code", -1) for e in recent]
            durations = [e.get("duration_s", 0) for e in recent if e.get("duration_s") is not None]
            ram_before_samples = [e.get("mem_before_mb", 0) for e in recent if e.get("mem_before_mb") is not None]
            ram_after_samples = [e.get("mem_after_mb", 0) for e in recent if e.get("mem_after_mb") is not None]

            # Composite Score: niedriger = besser
            # Gewichtung: Exit-Code (60%), Dauer (30%), RAM-Delta (10%)
            score = 0.0
            n_metrics = 0
            if exit_codes:
                avg_exit = statistics.mean(exit_codes)  # 0=perfekt
                score += avg_exit * 0.6
                n_metrics += 1
            if durations:
                avg_dur = statistics.mean(durations)
                score += avg_dur * 0.3
                n_metrics += 1
            if ram_before_samples and ram_after_samples:
                avg_ram_delta = statistics.mean(ram_before_samples) - statistics.mean(ram_after_samples)
                score += max(0, avg_ram_delta) * 0.1
                n_metrics += 1

            if n_metrics > 0:
                sample = round(score, 4)
                results[arm]["samples"].append(sample)
                results[arm]["exit_codes"].extend(exit_codes)
                results[arm]["durations_s"].extend(durations)
                if ram_before_samples:
                    results[arm]["ram_before_mb"].extend(ram_before_samples)
                if ram_after_samples:
                    results[arm]["ram_after_mb"].extend(ram_after_samples)

                # Statistik aktualisieren
                samples = results[arm]["samples"]
                results[arm]["n"] = len(samples)
                if len(samples) >= 2:
                    results[arm]["mean"] = round(statistics.mean(samples), 6)
                    results[arm]["std"] = round(statistics.stdev(samples), 6)
                elif len(samples) == 1:
                    results[arm]["mean"] = round(samples[0], 6)
                    results[arm]["std"] = 0.0

                _save_results(name, results)
                collected += 1

                print(f"  ✓ {name} ({arm}): sample={sample:.4f}, n={len(samples)}")

    # Raw-Metrik-Snapshot speichern
    snapshot = {
        "timestamp": now,
        "ram_before_mb": ram_before,
        "ram_after_mb": _get_current_ram_mb(),
        "experiments_collected": collected,
    }
    snapshot_path = METRICS_DIR / f"snapshot_{now[:19].replace(':','-')}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2), "utf-8")

    print(f"\n✅ Metrik-Sammlung abgeschlossen: {collected} Samples erfasst.")
    print(f"   Snapshot: {snapshot_path}")


def cmd_analyze(args):
    """
    Analysiert alle laufenden Experimente automatisch.
    Prüft Laufzeit und führt --conclude durch wenn abgelaufen.
    """
    experiments = sorted(EXPERIMENTS_DIR.glob("*.json"))
    running = [p for p in experiments if json.loads(p.read_text("utf-8")).get("status") == "running"]

    if not running:
        print("📭 Keine laufenden Experimente zu analysieren.")
        return

    now = datetime.now(timezone.utc)
    concluded_count = 0

    for exp_path in running:
        exp = json.loads(exp_path.read_text("utf-8"))
        name = exp["name"]

        # Prüfe Laufzeit
        started = datetime.fromisoformat(exp["started_at"])
        elapsed_h = (now - started).total_seconds() / 3600
        remaining = exp.get("duration_hours", 168) - elapsed_h

        if remaining <= 0:
            print(f"\n🔬 Experiment '{name}' ist abgelaufen ({elapsed_h:.1f}h). Führe Analyse durch...")
            # Simuliere --conclude
            class Args:
                pass
            a = Args()
            a.conclude = name
            cmd_conclude(a)
            concluded_count += 1
        else:
            print(f"  ⏳ '{name}': noch {remaining:.1f}h verbleibend")

    if concluded_count == 0:
        print("\n✅ Keine abgelaufenen Experimente gefunden.")


# ── Weitere Hilfs-Befehle ───────────────────────────────────────────

def cmd_switch(args):
    """Schaltet ein Experiment auf Variant- oder Control-Config um."""
    name = args.switch
    target = args.to

    exp = _load_exp(name)

    if target == "variant":
        config = exp.get("variant_config", {})
        arm = "Variant"
    elif target == "control":
        config = exp.get("control_config", {})
        arm = "Control"
    else:
        print(f"❌ Unbekanntes Ziel '{target}'. Nutze 'control' oder 'variant'.")
        return

    # Nur die Keys anwenden, die sich unterscheiden
    delta = {}
    for k, v in config.items():
        ctrl_v = exp.get("control_config", {}).get(k)
        if str(ctrl_v) != str(v):
            delta[k] = v

    if not delta:
        print(f"⚠️  Keine Unterschiede zwischen Control und {arm}.")
        return

    _apply_config(delta)
    print(f"✅ '{name}' auf {arm} geschaltet ({len(delta)} Keys geändert).")
    for k, v in delta.items():
        print(f"   {k} = {v}")


def cmd_restore(args):
    """Stellt ursprüngliche Config eines Experiments wieder her."""
    name = args.restore
    exp = _load_exp(name)
    _restore_config(exp.get("control_config", {}))
    print(f"✅ Config von '{name}' auf Control-Zustand zurückgesetzt.")


# ── MAIN ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🧪 A/B Test Engine für OpenAmer Skills + Configs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s --create skill-load-v1 "Lazy Loading vs Default" --variant 'skill_loader=lazy,skill_cache_size=512'
  %(prog)s --list
  %(prog)s --status skill-load-v1
  %(prog)s --collect
  %(prog)s --analyze
  %(prog)s --conclude skill-load-v1
  %(prog)s --switch skill-load-v1 --to variant
  %(prog)s --restore skill-load-v1
        """
    )

    parser.add_argument("--create", type=str, help="Experiment erstellen (Name)")
    parser.add_argument("--description", type=str, default="", help="Beschreibung für --create")
    parser.add_argument("--variant", type=str, default="", help="Variant-Konfig: key=value[,key=value]")
    parser.add_argument("--list", action="store_true", help="Alle Experimente auflisten")
    parser.add_argument("--status", type=str, help="Status eines Experiments anzeigen")
    parser.add_argument("--conclude", type=str, help="Statistische Analyse durchführen")
    parser.add_argument("--collect", action="store_true", help="Metrik-Daten sammeln (Cron)")
    parser.add_argument("--analyze", action="store_true", help="Abgelaufene Experimente automatisch analysieren")
    parser.add_argument("--switch", type=str, help="Experiment umschalten auf --to")
    parser.add_argument("--to", type=str, default="variant", choices=["control", "variant"], help="Ziel für --switch")
    parser.add_argument("--restore", type=str, help="Config auf Control-Zustand zurücksetzen")

    args = parser.parse_args()

    try:
        if args.create:
            cmd_create(args)
        elif args.list:
            cmd_list(args)
        elif args.status:
            cmd_status(args)
        elif args.conclude:
            cmd_conclude(args)
        elif args.collect:
            cmd_collect(args)
        elif args.analyze:
            cmd_analyze(args)
        elif args.switch:
            cmd_switch(args)
        elif args.restore:
            cmd_restore(args)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(1)


if __name__ == "__main__":
    main()
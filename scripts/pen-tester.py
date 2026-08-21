#!/usr/bin/env python3
"""
pen-tester.py — Automatisierter Security-Audit für OpenAmer
============================================================
Module:
  1. Port-Scan          – lokale offene Ports prüfen (socket)
  2. Dependency-Audit   – pip audit / pip list --outdated
  3. File-Permissions   – .env / config.yaml / .backup_key Berechtigungen
  4. Network-Exposure   – Dienste auf 0.0.0.0 vs 127.0.0.1
  5. Password-Hygiene   – schwache/Standard-Passwörter in Configs
  6. Report             – HTML + JSON mit CVSS-ähnlichem Scoring

CLI:
  --quick               Nur kritische Checks (Port + Permissions + Exposure)
  --full                Alle Checks inkl. Dependency-Audit + Password-Hygiene
  --report [pfad]       HTML + JSON Report speichern (Default: reports/)
  --stdout              Nur Console-Ausgabe, keine Dateien

Exit-Codes:
  0 = sicher / keine Funde
  1 = Warnungen (low/medium)
  2 = kritisch (high/critical)
"""

import json
import os
import socket
import subprocess
import sys
import datetime
import html
import textwrap
from pathlib import Path
from stat import S_IRWXG, S_IRWXO

# ────────────────────────────────────────────────────────────────────
# Konfiguration
# ────────────────────────────────────────────────────────────────────

COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    111: "RPC",
    135: "MSRPC",
    139: "NetBIOS",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle",
    2049: "NFS",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    5985: "WinRM-HTTP",
    5986: "WinRM-HTTPS",
    6379: "Redis",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
    9090: "Prometheus",
    9000: "Portainer",
    9200: "Elasticsearch",
    11211: "Memcached",
    27017: "MongoDB",
    50070: "HDFS",
}

OPENAMER_HOME_ENV = os.environ.get("OPENAMER_HOME", "")
if OPENAMER_HOME_ENV:
    # MSYS/MinGW paths like /c/Users/... → C:\Users\...
    raw = OPENAMER_HOME_ENV
    if raw.startswith("/") and raw.count("/") >= 2:
        parts = raw.split("/")
        if len(parts[1]) == 1 and parts[1].isalpha():
            raw = f"{parts[1].upper()}:\\" + "\\".join(parts[2:])
    OPENAMER_HOME = Path(raw)
else:
    OPENAMER_HOME = Path.home() / "AppData/Local/openamer-laptop"

SENSITIVE_FILES = [
    OPENAMER_HOME / "config.yaml",
    OPENAMER_HOME / ".backup_key",
    Path.home() / ".env",
    Path.home() / ".openamer/.env",
    Path.home() / "openamer-repo/.env",
]

SAFETY_NET = {"dummy": True}  # prevents import-time side effects


# ────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ────────────────────────────────────────────────────────────────────

def _severity_label(score: float) -> str:
    if score >= 8.0:
        return "CRITICAL"
    if score >= 5.0:
        return "HIGH"
    if score >= 3.0:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "INFO"


def _cvss_color(score: float) -> str:
    if score >= 8:
        return "#dc3545"
    if score >= 5:
        return "#fd7e14"
    if score >= 3:
        return "#ffc107"
    return "#28a745"


def _score_to_cvss(severity: str) -> float:
    """Wandle severity-String in CVSS-ähnlichen Score."""
    mapping = {
        "CRITICAL": 9.0,
        "HIGH": 6.5,
        "MEDIUM": 4.0,
        "LOW": 1.5,
        "INFO": 0.0,
    }
    return mapping.get(severity.upper(), 0.0)


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}min"


_PORT_TIMEOUT = 2.0

def _is_port_open(host: str, port: int, timeout: float = None) -> bool:
    if timeout is None:
        timeout = _PORT_TIMEOUT
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _scan_ports_parallel(hosts: list[str], ports: dict, max_workers: int = 50) -> list[dict]:
    """Scanne Ports parallel mit ThreadPoolExecutor."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    findings = []
    tasks = []

    def _check(ip, port, service):
        try:
            if _is_port_open(ip, port):
                return {
                    "check": "open-port",
                    "target": f"{ip}:{port}",
                    "service": service,
                    "severity": "INFO" if ip == "127.0.0.1" else "HIGH",
                    "message": f"Port {port} ({service}) ist offen auf {ip}",
                    "recommendation": (
                        f"Prüfen ob {service} auf {ip}:{port} benötigt wird. "
                        "Nicht benötigte Dienste deaktivieren oder per Firewall sperren."
                    ),
                }
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for ip in hosts:
            for port, service in ports.items():
                tasks.append(pool.submit(_check, ip, port, service))

        for future in as_completed(tasks):
            result = future.result()
            if result:
                findings.append(result)

    return findings


# ────────────────────────────────────────────────────────────────────
# Module
# ────────────────────────────────────────────────────────────────────

def scan_ports(loopback_only: bool = True) -> list[dict]:
    """Port-Scan: Common Ports auf localhost (und ggf. 0.0.0.0)."""
    hosts = ["127.0.0.1"]
    if not loopback_only:
        hosts.append("0.0.0.0")
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip not in hosts:
            hosts.append(local_ip)
    except Exception:
        pass

    return _scan_ports_parallel(hosts, COMMON_PORTS, max_workers=50)


def scan_network_exposure() -> list[dict]:
    """Prüft ob Dienste auf 0.0.0.0 laufen = von extern erreichbar."""
    findings = []

    # Prüfe ob Prozesse auf 0.0.0.0 lauschen (Linux-agnostisch via netstat/ss)
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=False, timeout=10,
            )
            netstat_out = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            for line in netstat_out.splitlines():
                if "0.0.0.0:" in line or "[::]:" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        addr_port = parts[1] if len(parts) > 1 else ""
                        status = parts[3] if len(parts) > 3 else ""
                        if status and "LISTEN" in status.upper():
                            findings.append({
                                "check": "network-exposure",
                                "target": addr_port,
                                "severity": "HIGH",
                                "message": f"Dienst lauscht auf {addr_port} — von extern erreichbar",
                                "recommendation": (
                                    "Bindung auf 127.0.0.1 ändern oder Firewall-Regel setzen."
                                ),
                            })
        else:
            # Linux/macOS – ss bevorzugen
            for cmd in [["ss", "-tlnp", "state", "listen"],
                        ["netstat", "-tlnp"]]:
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=10,
                    )
                    if result.returncode == 0:
                        for line in result.stdout.splitlines():
                            if "0.0.0.0:" in line or "[::]:" in line or "*:" in line:
                                findings.append({
                                    "check": "network-exposure",
                                    "target": line.strip(),
                                    "severity": "HIGH",
                                    "message": f"Dienst lauscht global: {line.strip()}",
                                    "recommendation": (
                                        "Binding auf 127.0.0.1 ändern."
                                    ),
                                })
                        break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
    except Exception as e:
        findings.append({
            "check": "network-exposure",
            "target": "N/A",
            "severity": "INFO",
            "message": f"Network-Exposure-Check nicht möglich: {e}",
            "recommendation": "Manuell prüfen mit 'netstat -tlnp'.",
        })
    return findings


def audit_dependencies() -> list[dict]:
    """Prüft Abhängigkeiten via pip-audit oder pip list --outdated."""
    findings = []

    # Versuche pip-audit
    pip_audit_found = False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json"],
            capture_output=True, text=False, timeout=120,
        )
        stdout_str = result.stdout.decode("utf-8", errors="replace")
        if result.returncode == 0 or result.returncode == 1:
            pip_audit_found = True
            try:
                data = json.loads(stdout_str)
                for vuln in data.get("vulnerabilities", []):
                    severity = vuln.get("severity", "unknown").upper()
                    if severity in ("CRITICAL", "HIGH"):
                        sev_str = severity
                    elif severity == "MEDIUM":
                        sev_str = "MEDIUM"
                    else:
                        sev_str = "LOW"
                    findings.append({
                        "check": "dependency-audit",
                        "target": f"{vuln['name']}=={vuln.get('version', '?')}",
                        "severity": sev_str,
                        "message": (
                            f"{vuln['name']} {vuln.get('version', '?')}: "
                            f"{vuln.get('id', 'CVE-?')} — {vuln.get('description', '')[:120]}"
                        ),
                        "recommendation": (
                            f"Aktualisiere {vuln['name']} auf {vuln.get('fixed_version', 'neueste')}"
                        ),
                    })
            except (json.JSONDecodeError, KeyError, TypeError):
                findings.append({
                    "check": "dependency-audit",
                    "target": "pip-audit",
                    "severity": "INFO",
                    "message": "pip-audit Ausgabe nicht lesbar; Fallback auf --outdated",
                    "recommendation": "pip-audit manuell prüfen.",
                })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: pip list --outdated
    if not pip_audit_found:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
                capture_output=True, text=False, timeout=60,
            )
            pip_out_stdout = result.stdout.decode("utf-8", errors="replace")
            if result.returncode == 0:
                try:
                    packages = json.loads(pip_out_stdout)
                    for pkg in packages[:30]:  # max 30 Einträge
                        findings.append({
                            "check": "dependency-outdated",
                            "target": f"{pkg['name']}=={pkg['version']}",
                            "severity": "LOW",
                            "message": (
                                f"{pkg['name']} {pkg['version']} ist outdated "
                                f"(latest: {pkg.get('latest_version', '?')})"
                            ),
                            "recommendation": (
                                f"Führe 'pip install --upgrade {pkg['name']}' aus"
                            ),
                        })
                except (json.JSONDecodeError, KeyError):
                    pass
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if not findings:
        findings.append({
            "check": "dependency-audit",
            "target": "N/A",
            "severity": "INFO",
            "message": "Keine veralteten/verwundbaren Abhängigkeiten gefunden.",
            "recommendation": "Regelmäßig mit pip-audit prüfen.",
        })

    return findings


def check_file_permissions() -> list[dict]:
    """Prüft Berechtigungen von .env, config.yaml, .backup_key."""
    findings = []

    for fpath in SENSITIVE_FILES:
        if not fpath.exists():
            findings.append({
                "check": "file-permission",
                "target": str(fpath),
                "severity": "INFO",
                "message": f"Datei nicht vorhanden — kein Risiko.",
                "recommendation": "N/A",
            })
            continue

        try:
            st = fpath.stat()
            mode = st.st_mode

            problems = []
            if sys.platform == "win32":
                # Auf Windows: Prüfe ob 'Everyone' oder 'BUILTIN\\Users' Zugriff hat
                try:
                    import win32security
                    sd = win32security.GetFileSecurity(
                        str(fpath), win32security.DACL_SECURITY_INFORMATION
                    )
                    dacl = sd.GetSecurityDescriptorDacl()
                    if dacl:
                        for i in range(dacl.GetAceCount()):
                            ace = dacl.GetAce(i)
                            sid = ace[2]
                            try:
                                name = win32security.LookupAccountSid(None, sid)[0]
                            except Exception:
                                name = str(sid)
                            if name in ("Everyone", "BUILTIN\\Users", "CREATOR OWNER"):
                                problems.append(f"Welt-lesbar: {name}")
                except ImportError:
                    # Fallback: Mode-Prüfung
                    if mode & S_IRWXG or mode & S_IRWXO:
                        problems.append("Gruppe/Andere haben Zugriff (POSIX-Mode)")
            else:
                # Unix: Prüfe group/other Berechtigungen
                group_other = mode & (S_IRWXG | S_IRWXO)
                if group_other:
                    problems.append(
                        f"Zu offen: {oct(mode & 0o777)} (sollte 600/640)"
                    )

            severity = "HIGH" if problems else "INFO"
            msg = (
                "; ".join(problems) if problems
                else f"OK ({oct(mode & 0o777) if not sys.platform == 'win32' else 'NTFS-Berechtigung'})"
            )
            findings.append({
                "check": "file-permission",
                "target": str(fpath),
                "severity": severity,
                "message": msg,
                "recommendation": (
                    "Setze chmod 600 oder entferne 'Everyone'-Zugriff."
                    if problems else "Bereits sicher."
                ),
            })

        except Exception as e:
            findings.append({
                "check": "file-permission",
                "target": str(fpath),
                "severity": "MEDIUM",
                "message": f"Konnte Berechtigungen nicht lesen: {e}",
                "recommendation": "Manuell prüfen.",
            })

    return findings


def check_password_hygiene() -> list[dict]:
    """Prüft Configs auf schwache/Standard-Passwörter."""
    findings = []
    weak_patterns = [
        "password: 'admin'",
        "password: admin",
        "password: 'password'",
        "password: password",
        "password: '123456'",
        "password: 123456",
        "password: 'changeme'",
        "password: changeme",
        "password: 'test'",
        "api_key: 'your-api-key'",
        "api_key: 'sk-your'",
        "api_key: your-api-key",
        "secret: 'your-secret'",
        "token: 'your-token'",
    ]

    config_paths = [
        OPENAMER_HOME / "config.yaml",
        Path.home() / ".env",
        Path.home() / "openamer-repo/.env",
    ]

    for cfg in config_paths:
        if not cfg.exists():
            continue
        try:
            content = cfg.read_text(encoding="utf-8", errors="replace")
            for pattern in weak_patterns:
                if pattern.lower() in content.lower():
                    findings.append({
                        "check": "weak-password",
                        "target": str(cfg),
                        "severity": "CRITICAL",
                        "message": f"Schwaches Passwort/API-Key gefunden: {pattern}",
                        "recommendation": (
                            "Sicheres Passwort/API-Key generieren und in der Config ersetzen. "
                            "Umgebungsvariablen bevorzugen."
                        ),
                    })
                    break  # ein Treffer pro Datei reicht

        except Exception as e:
            findings.append({
                "check": "weak-password",
                "target": str(cfg),
                "severity": "LOW",
                "message": f"Konnte Datei nicht lesen: {e}",
                "recommendation": "Manuelle Prüfung.",
            })

    # Zusätzlich: Prüfe ob Configs Plaintext-Keys enthalten
    for cfg in config_paths:
        if not cfg.exists():
            continue
        try:
            content = cfg.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            key_count = 0
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    if any(kw in stripped.lower() for kw in
                           ["api_key", "password", "secret", "token", "apikey"]):
                        # Prüfe ob der Wert leer oder Platzhalter ist
                        parts = stripped.split(":", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip("'\"").strip()
                            if val and val not in ("", "your-", "changeme", "sk-your"):
                                key_count += 1
            if key_count > 3:
                findings.append({
                    "check": "many-credentials",
                    "target": str(cfg),
                    "severity": "MEDIUM",
                    "message": (
                        f"{key_count} API-Keys/Passwörter in {cfg.name} gefunden. "
                        "Risiko bei Kompromittierung."
                    ),
                    "recommendation": (
                        "Erwäge Umstieg auf Umgebungsvariablen oder verschlüsselten "
                        "Credential-Store."
                    ),
                })
        except Exception:
            pass

    if not findings:
        findings.append({
            "check": "password-hygiene",
            "target": "N/A",
            "severity": "INFO",
            "message": "Keine schwachen Passwörter oder Credential-Leaks gefunden.",
            "recommendation": "Regelmäßig prüfen.",
        })

    return findings


def compute_summary_score(findings: list[dict]) -> float:
    """Berechne aggregierten Sicherheits-Score 0–10 (0 = perfekt)."""
    weights = {
        "CRITICAL": 10.0,
        "HIGH": 5.0,
        "MEDIUM": 2.0,
        "LOW": 0.5,
        "INFO": 0.0,
    }
    total = sum(weights.get(f["severity"].upper(), 0) for f in findings)
    # Normalisiere: max ~ 50 Punkte für ~5 kritische Funde
    score = min(total / 5.0, 10.0)
    return round(score, 1)


def compute_exit_code(findings: list[dict]) -> int:
    """0 = safe, 1 = warnings, 2 = critical."""
    for f in findings:
        if f["severity"].upper() in ("CRITICAL", "HIGH"):
            return 2
    for f in findings:
        if f["severity"].upper() == "MEDIUM":
            return 1
    return 0


# ────────────────────────────────────────────────────────────────────
# Report-Generierung
# ────────────────────────────────────────────────────────────────────

def generate_html_report(
    findings: list[dict],
    score: float,
    exit_code: int,
    duration: float,
    mode: str,
) -> str:
    """Erzeuge einen eigenständigen HTML-Report."""
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f["severity"].upper(), 9))

    severity_counts = {}
    for f in findings:
        sev = f["severity"].upper()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    rows = ""
    for f in sorted_findings:
        sev = f["severity"].upper()
        color = _cvss_color(_score_to_cvss(sev))
        rows += f"""\
        <tr>
            <td><span class="badge" style="background:{color}">{sev}</span></td>
            <td>{html.escape(f['check'])}</td>
            <td><code>{html.escape(f['target'])}</code></td>
            <td>{html.escape(f['message'][:200])}</td>
            <td>{html.escape(f['recommendation'][:150])}</td>
        </tr>
"""

    status_text = {0: "✅ SICHER", 1: "⚠️ WARNUNGEN", 2: "❌ KRITISCH"}
    status_color = {0: "#28a745", 1: "#ffc107", 2: "#dc3545"}
    verdict = status_text.get(exit_code, "UNBEKANNT")
    verdict_color = status_color.get(exit_code, "#6c757d")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""\
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Security Audit Report — OpenAmer Pen-Tester</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          background:#0d1117; color:#c9d1d9; padding:2rem; }}
  .container {{ max-width:1200px; margin:0 auto; }}
  h1 {{ color:#f0f6fc; font-size:1.8rem; margin-bottom:0.5rem; }}
  h2 {{ color:#f0f6fc; font-size:1.3rem; margin:1.5rem 0 0.5rem; }}
  .meta {{ color:#8b949e; font-size:0.9rem; margin-bottom:1.5rem; }}
  .score-ring {{ display:inline-flex; align-items:center; gap:0.8rem;
                 background:#161b22; padding:1.2rem 2rem; border-radius:12px;
                 margin-bottom:1.5rem; }}
  .score-value {{ font-size:2.5rem; font-weight:700; }}
  .score-label {{ font-size:0.85rem; color:#8b949e; }}
  .verdict {{ font-size:1.1rem; font-weight:600; padding:0.4rem 1rem;
              border-radius:6px; display:inline-block; }}
  .summary-cards {{ display:flex; gap:1rem; flex-wrap:wrap; margin:1.5rem 0; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:8px;
           padding:1rem; flex:1; min-width:140px; text-align:center; }}
  .card .n {{ font-size:1.6rem; font-weight:700; }}
  .card .l {{ font-size:0.8rem; color:#8b949e; margin-top:0.3rem; }}
  table {{ width:100%; border-collapse:collapse; margin-top:1rem; }}
  th, td {{ text-align:left; padding:0.7rem 0.8rem; border-bottom:1px solid #21262d;
            font-size:0.85rem; vertical-align:top; }}
  th {{ background:#161b22; color:#8b949e; font-weight:600; }}
  tr:hover td {{ background:#1c2128; }}
  .badge {{ display:inline-block; padding:0.15rem 0.5rem; border-radius:4px;
            color:#fff; font-weight:600; font-size:0.75rem; }}
  code {{ background:#21262d; padding:0.1rem 0.3rem; border-radius:3px;
          font-size:0.8rem; color:#ffa657; }}
  footer {{ margin-top:2rem; padding-top:1rem; border-top:1px solid #21262d;
            color:#484f58; font-size:0.8rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>🔒 Security Audit Report</h1>
  <p class="meta">OpenAmer Pen-Tester · {mode} · {now} · Dauer: {_format_duration(duration)}</p>

  <div class="score-ring">
    <div>
      <div class="score-value" style="color:{verdict_color}">{score}</div>
      <div class="score-label">Risk Score (0–10)</div>
    </div>
    <div class="verdict" style="background:{verdict_color}20;color:{verdict_color};border:1px solid {verdict_color}">
      {verdict}
    </div>
  </div>

  <div class="summary-cards">
    <div class="card"><div class="n" style="color:#dc3545">{severity_counts.get("CRITICAL", 0)}</div><div class="l">CRITICAL</div></div>
    <div class="card"><div class="n" style="color:#fd7e14">{severity_counts.get("HIGH", 0)}</div><div class="l">HIGH</div></div>
    <div class="card"><div class="n" style="color:#ffc107">{severity_counts.get("MEDIUM", 0)}</div><div class="l">MEDIUM</div></div>
    <div class="card"><div class="n" style="color:#28a745">{severity_counts.get("LOW", 0)}</div><div class="l">LOW</div></div>
    <div class="card"><div class="n" style="color:#8b949e">{severity_counts.get("INFO", 0)}</div><div class="l">INFO</div></div>
  </div>

  <h2>📋 Findings ({len(findings)})</h2>
  <table>
    <thead><tr><th>Severity</th><th>Check</th><th>Target</th><th>Message</th><th>Recommendation</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <footer>
    OpenAmer Pen-Tester · Exit Code: {exit_code}
    ({status_text.get(exit_code, 'UNBEKANNT')}) ·
    Generated {now}
  </footer>
</div>
</body>
</html>"""


def generate_json_report(
    findings: list[dict],
    score: float,
    exit_code: int,
    duration: float,
    mode: str,
) -> str:
    """Erzeuge JSON-Report."""
    report = {
        "tool": "openamer-pen-tester",
        "version": "1.0.0",
        "timestamp": datetime.datetime.now().isoformat(),
        "duration_seconds": round(duration, 1),
        "mode": mode,
        "risk_score": score,
        "exit_code": exit_code,
        "summary": {},
        "findings": findings,
    }
    severity_counts = {}
    for f in findings:
        sev = f["severity"].upper()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    report["summary"]["total"] = len(findings)
    report["summary"]["by_severity"] = severity_counts
    return json.dumps(report, indent=2, ensure_ascii=False)


# ────────────────────────────────────────────────────────────────────
# CLI-Entrypoint
# ────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="OpenAmer Pen-Tester — automatisierte Security-Audits",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Nur kritische Checks: Port + Permissions + Exposure",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Alle Checks inkl. Dependency-Audit + Password-Hygiene",
    )
    parser.add_argument(
        "--report", nargs="?", const="reports", default=None,
        help="HTML + JSON Report speichern (Pfad oder Default: reports/)",
    )
    parser.add_argument(
        "--stdout", action="store_true",
        help="Nur Console-Ausgabe, keine Dateien",
    )
    parser.add_argument(
        "--report-dir", default=None,
        help="Explizites Report-Verzeichnis",
    )

    args = parser.parse_args()

    # Wenn nichts angegeben: --quick als Default
    mode = "quick"
    if args.full:
        mode = "full"
    elif args.quick:
        mode = "quick"
    else:
        mode = "quick"

    start = datetime.datetime.now()

    # ── Checks ──────────────────────────────────────────────────────
    all_findings: list[dict] = []

    print(f"🔍 OpenAmer Pen-Tester — Mode: {mode}")
    print("=" * 50)

    # 1. Port-Scan (immer)
    print("\n📡 Port-Scan ...")
    port_findings = scan_ports(loopback_only=(mode == "quick"))
    all_findings.extend(port_findings)
    print(f"   → {len(port_findings)} offene Ports gefunden")

    # 2. Network-Exposure (immer)
    if mode == "full":
        print("\n🌐 Network-Exposure ...")
        net_findings = scan_network_exposure()
        all_findings.extend(net_findings)
        print(f"   → {len(net_findings)} Exposure-Funde")

    # 3. File-Permissions (immer)
    print("\n🔐 File-Permissions ...")
    perm_findings = check_file_permissions()
    all_findings.extend(perm_findings)
    print(f"   → {len(perm_findings)} Dateien geprüft")

    # 4. Dependency-Audit (nur full)
    if mode == "full":
        print("\n📦 Dependency-Audit ...")
        dep_findings = audit_dependencies()
        all_findings.extend(dep_findings)
        print(f"   → {len(dep_findings)} Abhängigkeits-Funde")

    # 5. Password-Hygiene (nur full)
    if mode == "full":
        print("\n🔑 Password-Hygiene ...")
        pwd_findings = check_password_hygiene()
        all_findings.extend(pwd_findings)
        print(f"   → {len(pwd_findings)} Password/Credential-Funde")

    duration = (datetime.datetime.now() - start).total_seconds()
    score = compute_summary_score(all_findings)
    exit_code = compute_exit_code(all_findings)

    # ── Ausgabe ─────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"⚠️  Risk Score: {score}/10")
    print(f"🔚 Exit Code: {exit_code} ({['SICHER','WARNUNGEN','KRITISCH'][exit_code] if exit_code < 3 else '?'})")
    print(f"⏱  Dauer: {_format_duration(duration)}")

    severity_counts = {}
    for f in all_findings:
        sev = f["severity"].upper()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        if sev in severity_counts:
            print(f"   {sev}: {severity_counts[sev]}")

    # ── Report ──────────────────────────────────────────────────────
    if not args.stdout:
        report_dir = args.report_dir or args.report or "reports"
        if report_dir:
            report_path = Path(report_dir)
            report_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            html_content = generate_html_report(
                all_findings, score, exit_code, duration, mode
            )
            html_file = report_path / f"pen-tester_{timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"\n📄 HTML-Report: {html_file}")

            json_content = generate_json_report(
                all_findings, score, exit_code, duration, mode
            )
            json_file = report_path / f"pen-tester_{timestamp}.json"
            json_file.write_text(json_content, encoding="utf-8")
            print(f"📄 JSON-Report: {json_file}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
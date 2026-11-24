# Ein Dienst, der „alive" meldet und ein FREMDES Modell ausliefert (live 18.11.26)

Der Fall gehört zu den teuersten dieser Klasse, weil **jeder** Health-Check grün ist:
Der Wrapper läuft, der Port ist belegt, `tools` ist da — und trotzdem antwortet ein
anderes Modell als das auf dem Etikett.

## Symptome, in der Reihenfolge, in der sie auftraten

```
curl :8081/health   → {"status":"alive","tools":10,"swaps":29}    ✅ kanonisch
curl :8081/v1/chat  → 503 {"error":"gguf backend: HTTP 500 …"}    ❌
curl :18080/health  → {"model":"qwen2.5-1.5b-directml"}           ⚠️ fremd
```

Der Server meldete `MODEL_READY (GGUF backend on :18080)` — und auf `:18080`
antwortete `qwen2.5-1.5b-directml` mit `DmlExecutionProvider`, nicht das
2B-Hybrid-Modell. `swaps: 29` bewies nur, dass Adapter getauscht wurden, nicht
welches Basismodell sie trug.

## Ursachenkette (drei Schichten, alle nötig)

### 1. `PYTHONPATH` schattet das eigene venv — der Import kommt aus einem FREMDEN venv

```
PYTHONPATH = C:\...\openamer-laptop\openamer-agent;
             C:\...\openamer-laptop\openamer-agent\venv\Lib\site-packages
```

`sys.path` bestätigte: das fremde `site-packages` stand **vor** dem eigenen venv.
Damit galten die Paketversionen des anderen venv — und `transformers 5.x` scheiterte
an einem zu alten `huggingface_hub` (`ImportError: cannot import name
'ResolvedRevision'`). Das Modell konnte nie laden.

**Zwei Folgen, die man getrennt prüfen muss:**

```bash
# a) Wohin installiert pip wirklich?
PYTHONPATH= ./venv/Scripts/python.exe -m pip install -U "<paket>"
#    OHNE das geleerte PYTHONPATH meldet pip "already satisfied" aus dem FREMDEN venv
#    und der Import zeigt danach weiter die ALTE Version.

# b) Aus welchem venv kommt der Import?
./venv/Scripts/python.exe -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
./venv/Scripts/python.exe -c "import sys; [print(p) for p in sys.path if 'site-packages' in p]"
```

Der Beweis, dass es die Ursache war — nicht die Vermutung:

```
# vorher:  huggingface_hub 1.2.3  →  ImportError
# nachher: huggingface_hub 1.31.0 →  "transformers import: OK"
```

### 2. Der Watchdog vererbt den vergifteten `PYTHONPATH` an jeden Neustart

Ein Fix am laufenden Prozess ist wertlos, wenn der Keepalive ihn beim nächsten
Crash wieder mit demselben Umfeld startet. `tool_server_keepalive.py` baute

```python
env = {**os.environ, "OPENAMER_HOME": str(HOME)}
```

und erbte damit `PYTHONPATH` vom Watchdog-Prozess. Fix — Quelle ja, venv-Pakete nein:

```python
env["PYTHONPATH"] = str(HOME / "openamer-agent")
```

Prüfbar ohne Neustart: `grep -n 'env\["PYTHONPATH"\]' scripts/tool_server_keepalive.py`.

### 3. `FATAL: port taken` kommt erst NACH dem Modell-Load

`sys.exit(1)` nach der `FATAL`-Meldung ist korrekt — aber die Bindung passiert am
Dateiende, hinter `MODEL_READY`. Tickt der Watchdog während des Ladefensters,
entstehen kurzzeitig **zwei** `tool_server.py`-Prozesse; einer stirbt am Port.
Gemessen: 2–3 Instanzen gleichzeitig, jede mit Modell-Load-Versuch.

Konsequenz für die Diagnose: **mehrere Instanzen sind während eines
Neustart-Fensters erwartbar** und kein Beweis für einen Watchdog-Bug. Nach dem
Fenster müssen es wieder genau eine sein — und der Port-Halter ist die Autorität:

```bash
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8081 -State Listen | Select -Expand OwningProcess"
```

## Die eigentliche Lehre: `/health` beweist nicht, WELCHES Modell antwortet

Die kanonische Health-Form (`tools`-Schlüssel) beweist, dass der **Wrapper** der
richtige ist. Sie sagt nichts über das Backend. Wenn der Wrapper einen zweiten
Dienst vorschaltet (GGUF, DirectML, llama-server), kann dort ein völlig anderes
Modell laufen.

**Beweis für „richtiges Modell" ist nur die Completion selbst:**

```bash
curl -s -X POST http://127.0.0.1:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mini-openamer","use_tools":false,
       "messages":[{"role":"user","content":"Was ist die Hauptstadt von Spanien?"}],
       "max_tokens":30}'
# -> model-Feld + Antwort lesen.  "Madrid" = Modell tut etwas.
#    Leer / 503 / fremder Modellname = Wrapper lebt, Kern nicht.
```

Zwei Ebenen, zwei Fragen:

| Frage | Beleg |
|---|---|
| Ist der kanonische Wrapper oben? | `/health` **mit** `tools`-Schlüssel (10) |
| Antwortet das Modell, das draufsteht? | `model`-Feld **und** ein bekannter Fakt in der Completion |

## Nach dem Fix verifizieren (Reihenfolge)

1. `:18080` darf **nicht** mehr antworten (der Fremd-Backend-Port ist tot).
2. `/health` → `tools: 10`.
3. Completion mit `use_tools: false` → korrekte Sachantwort (`Spanien → Madrid`).
4. **Crash-Test:** Server killen, Keepalive-Script direkt starten, 15 s warten,
   dann 1–3 wiederholen. Das ist der einzige Beweis, dass der Fix den Neustart
   überlebt (`cognition-core-keepalive: core was down — started on :8081`).
5. Genau **eine** Instanz nach dem Ladefenster.

Punkt 4 ist der, den man gern überspringt — und ohne ihn kehrt das 503 beim
nächsten Crash zurück.

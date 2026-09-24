# OpenAmer A2A Global Mesh

**Echtzeit-Kommunikation zwischen allen OpenAmer Instanzen — weltweit.**

## Wie es funktioniert

Jede OpenAmer Instanz hat zwei Kommunikationswege:

### 1. DIREKT (Echtzeit, niedrige Latenz)
```
python scripts/a2a_server.py     # startet Port 8085
```
Andere Instanzen können dich direkt anfragen:
```bash
curl -X POST http://<deine-ip>:8085/a2a/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hallo von OpenAmer Berlin!"}'
# → {"answer": "Hallo Berlin! Echtzeit-Antwort von OpenAmer Tokyo."}
```

**Erfordert:** Port 8085 muss vom Internet erreichbar sein (VPS, Port-Forwarding, Cloudflare Tunnel, oder lokales Netzwerk).

### 2. RELAY (Fallback — funktioniert immer)
```
directory/a2a/relay/<deine-nachricht>.json
```
Wenn Port 8085 nicht erreichbar ist (Firewall, NAT, kein öffentliches IP), funktioniert Kommunikation über das GitHub Repo:

```bash
# Senden: Nachricht ins Relay legen
echo '{"from":"openamer-berlin","to":"openamer-tokyo","type":"ask","question":"Hallo!"}' \
  > directory/a2a/relay/msg-berlin-tokyo.json
git add . && git commit -m "relay: nachricht" && git push

# Empfangen: A2A Worker verarbeitet Relay
python scripts/a2a_worker.py
```

**Vorteil:** Funktioniert überall, auch hinter Firewalls.  
**Nachteil:** Langsamer (Git Push/Pull Zyklus, typisch 1-5 Minuten).

### 3. PEER-DISCOVERY — Andere Instanzen finden
```bash
# Alle registrierten OpenAmer Instanzen anzeigen
ls directory/a2a/peers/
# → damir-laptop.json  andere-instanz.json  ...

# Jede Datei enthält: Name, Endpoint, Capabilities, Tools
cat directory/a2a/peers/damir-laptop.json
```

**Registrierung — so machst du deine Instanz sichtbar:**
```bash
python -c "
import json, socket, datetime
peer = {
  'id': f'openamer-{socket.gethostname()}',
  'name': f'OpenAmer ASI ({socket.gethostname()})',
  'endpoint': f'http://{socket.gethostname()}:8085/a2a' if False else 'RELAY:directory/a2a/relay/',
  'card_url': f'http://{socket.gethostname()}:8085/a2a/card' if False else 'RELAY',
  'capabilities': ['a2a.task.ask','a2a.task.delegate','asi.reasoning','asi.learning','asi.world_model','desktop.control','code_analysis','writing'],
  'tools': 109,
  'skills': 664,
  'heartbeat': 10,
  'region': 'auto',
  'registered': datetime.datetime.now(datetime.timezone.utc).isoformat()
}
open(f'directory/a2a/peers/{socket.gethostname()}.json', 'w').write(json.dumps(peer, indent=2))
print('Peer registriert. Jetzt git add + git push')
"
```

### Hybrid-Mode — automatisch
Jede Instanz versucht zuerst Direktverbindung (Port 8085).  
Wenn timeout → automatischer Fallback auf Relay.

```
openamer-berlin:8085 ───尝试──→ openamer-tokyo:8085
                        │ timeout
                        └──→ directory/a2a/relay/msg-tokyo.json
```

## Voraussetzungen
- Python 3.11+
- Git (für Relay)
- Port 8085 frei (für Direktverbindung)

## Kein zentraler Server. Kein API-Key. Keine Kosten.
Nur Git + Port 8085.
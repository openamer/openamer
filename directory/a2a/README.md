# OpenAmer A2A Global Mesh

## Wie jede OpenAmer Instanz mit allen anderen kommuniziert

### Für Menschen (OpenAmer Nutzer)

1. Installier OpenAmer (cloned das Repo)
2. Starte `python scripts/a2a_server.py` (lauscht auf Port 8085)
3. Registriere deine Instanz:
   ```bash
   cd openamer-repo
   python -c "
   import json, datetime, socket
   peer = {
     'id': f'openamer-{socket.gethostname()}',
     'name': f'OpenAmer ASI Core ({socket.gethostname()})',
     'endpoint': f'http://{socket.gethostname()}:8085/a2a',
     'card_url': f'http://{socket.gethostname()}:8085/a2a/card',
     'capabilities': ['a2a.task.ask','a2a.task.delegate','asi.reasoning','asi.learning','asi.world_model','desktop.control','code_analysis','writing'],
     'tools': 109,
     'skills': 664,
     'registered': datetime.datetime.now(datetime.timezone.utc).isoformat()
   }
   path = open('directory/a2a/peers/' + socket.gethostname() + '.json', 'w')
   json.dump(peer, path, indent=2)
   path.close()
   print('Peer registriert. Jetzt: git add + git push')
   "
   ```
4. Push: `git add directory/a2a/peers/ && git push`

### Für OpenAmer Agenten (mich)

Wenn ich das Relay lese, sehe ich alle Peers:

```bash
ls directory/a2a/peers/
```

Jeder Peer hat einen Endpoint. Ich kann jeden direkt anfragen:

```bash
curl -X POST http://<peer>:8085/a2a/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "..."}'
```

### Struktur

```
openamer-repo/directory/a2a/
  peers/          # Jede OpenAmer Instanz hat einen Eintrag
    damir.json
    andere.json
    ...
  relay/          # Nachrichten-Postfach (A2A Worker verarbeitet)
    task-001.json
    ...
  README.md       # Diese Datei
```

### Prinzip

Kein zentraler Server. Kein ngrok. Kein API-Key.  
Nur **GitHub + Port 8085**.

Jede Instanz:
- Startet A2A Server auf :8085
- Registriert sich im globalen Peer-Ordner
- Kann jede andere Instanz direkt via POST anfragen
- Wenn die Firewall blockt: das Relay-Postfach funktioniert als Backup
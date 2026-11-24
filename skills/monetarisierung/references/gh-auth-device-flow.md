# GitHub Device Code Auth (gh auth --web)

## Why
Git-Token aus `.git-credentials` (ghp_...) funktioniert nur für Git-Operationen (push/pull).  
Für REST API (PRs, Issues, Releases, Checks) → 401 Bad credentials.  
`gh auth login --web` → Device Code Flow → GH_TOKEN mit API-Zugriff.

## How
```bash
gh auth login --web
```
Output:
```
First copy your one-time code: XXXX-XXXX
Open this URL to continue in your web browser: https://github.com/login/device
```
User öffnet URL, gibt Code ein, klickt "Authorize GitHub CLI".  
Danach: `gh auth status` → "Logged in"  
`gh pr list` etc. funktionieren.

## Automatisierung
`gh auth login --web` muss im Vordergrund laufen (kein timeout!).  
Background + timeout killt den Prozess vor der Authorization.  
`gh auth status` checkt den Zustand.

## Ergebnis
Nach erfolgreichem Auth:
```bash
export GH_TOKEN=$(gh auth token)  # Token in env var
gh pr merge openamer/openamer#67  # PR mergen
gh release create v0.2.0 --title "..." --notes "..."  # Release
```

## Pitfalls
- `gh auth login --web` + timeout = abgebrochen → neuer Code nötig
- Token aus .git-credentials gibt 401 für API — kein Workaround
- Token aus device-code flow hat volle `repo` + `public_repo` Scopes
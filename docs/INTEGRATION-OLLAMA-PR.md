# OpenAmer `ollama launch`-Integration in ollama/ollama (PR)

## Was

OpenAmer wurde als offizielle Integration in [ollama/ollama](https://github.com/ollama/ollama) eingereicht: `ollama launch openamer` startet OpenAmer direkt mit lokalen/cloud Ollama-Modellen.

## PR

- **PR:** https://github.com/ollama/ollama/pull/18141 (state: open)
- **Branch:** `openamer:launch-add-openamer` → `ollama:main`
- **Commit:** `launch: add OpenAmer integration` (9 Dateien, +632 Zeilen)

## Inhalt

- `cmd/launch/openamer.go` — OpenAmer-Runner (LookPath `openamer`, EnsureInstalled via pip/Installer-Prompt, Configure/ConfigureWithModels schreibt `~/.ollama/launch/openamer/settings.yaml`, Env-Upsert `OLLAMA_LAUNCH_OPENAMER_API_KEY=ollama`, Windows .cmd-Shim-Handling via Python-Entry-point)
- `cmd/launch/openamer_test.go` + registry- und integrations-Tests
- `cmd/launch/registry.go` — Registrierung + `launcherIntegrationOrder`
- UI: `app/ui/app/src/lib/launchCommands.ts` + SVG-Icons (`docs/images/launch-icons/openamer.svg`, `app/ui/app/public/launch-icons/openamer.svg`)
- Docs: `docs/integrations/openamer.mdx` + Card in `docs/integrations/index.mdx`

## Nutzen

Nach Merge: `ollama launch openamer` installiert (pip) und startet OpenAmer mit gewähltem Modell; Ollama verwaltet Provider-Settings isoliert unter `~/.ollama/launch/openamer/` — Nutzer-Config unangetastet.

## Status

- Hinweis im PR-Body: `go test` wurde lokal nicht ausgeführt (Go-Toolchain nicht installiert); CI übernimmt die Verifikation.
- PR wurde per GitHub-API verifiziert: `state=open`.

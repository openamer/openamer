# awesome-openrouter submission — OpenAmer Agent

Merge-ready package for a PR against **https://github.com/OpenRouterTeam/awesome-openrouter**
(publishes to https://openrouter.ai/awesome).

Files in `apps/openamer-agent/`:
- `app.yaml` — schema-validated against `schema/app.schema.json`
- `logo.png` — 256×256 square PNG (RGBA)

Real schema followed exactly (`required`: name, description, url, docs, tags, date_added;
optional: open_source; `additionalProperties: false`). No invented fields.

---

## PR Title

```
Add OpenAmer Agent — self-improving AI agent (7.7B+ OpenRouter tokens, listed on OpenRouter)
```

---

## PR Body

```markdown
## OpenAmer Agent

Open-source, self-improving AI agent (Python, Windows/macOS/Linux). One agent core across
CLI, TUI, messaging gateway and Electron desktop — with a built-in learning loop, reusable
skills, episodic + world-model memory, background computer-use, and A2A swarm delegation.
Users bring their own OpenRouter key and pick any model.

### Evidence of traction

- **Already listed on OpenRouter itself** — appears in OpenRouter's own directory:
  - `cli-agent` category: **rank #38 of 50**
  - `ide-extension` category: **rank #7 of 9**
- **7.7+ billion tokens routed through OpenRouter** to date.
- Live homepage: https://openamer.github.io/openamer/
- Public source: https://github.com/openamer/openamer (open source).

### Bring-your-own-key OpenRouter setup

Users configure their own OpenRouter API key; OpenAmer routes model calls to any model on
OpenRouter. Setup docs: https://github.com/openamer/openamer#bring-your-own-keys

### Checklist

- [x] Uses OpenRouter for AI model access
- [x] Users bring their own OpenRouter API key
- [x] Public landing page (https://openamer.github.io/openamer/)
- [x] Logo image included (`logo.png`, 256×256 square PNG)
- [x] `app.yaml` matches `schema/app.schema.json` (validated)
- [x] Signal of traction provided above
```

---

## Commands the maintainer of THIS repo runs

Replace `<GHUSER>` with the fork owner's GitHub username. Run from a scratch dir.

```bash
# 0) Locate the package inside the OpenAmer repo
PKG="C:/Users/damir/openamer-repo/docs/awesome-openrouter-submission"

# 1) Fork upstream (no local clone yet)
gh repo fork OpenRouterTeam/awesome-openrouter --clone=false

# 2) Clone the fork and branch
gh repo clone <GHUSER>/awesome-openrouter
cd awesome-openrouter
git checkout -b add-openamer-agent

# 3) Add the submission exactly as apps/<name>/app.yaml + logo.png
mkdir -p apps/openamer-agent
cp "$PKG/app.yaml"   apps/openamer-agent/app.yaml
cp "$PKG/logo.png"   apps/openamer-agent/logo.png

# 4) Validate locally with the repo's own validator
#    NOTE: pass the bare dir NAME, not a path — validate.js prepends apps/ itself
#    ("npm run validate apps/openamer-agent" FAILS: the "/" breaks the name pattern)
npm install
npm run validate openamer-agent           # expect: "✅ Valid"

# 5) Commit (do NOT edit README.md — it is auto-generated after merge)
git add apps/openamer-agent/app.yaml apps/openamer-agent/logo.png
git commit -m "Add OpenAmer Agent"

# 6) Push + open the PR
git push -u origin add-openamer-agent
gh pr create \
  --repo OpenRouterTeam/awesome-openrouter \
  --title "Add OpenAmer Agent — self-improving AI agent (7.7B+ OpenRouter tokens, listed on OpenRouter)" \
  --body-file "$PKG/PR.md"

# --- Alternative without gh (git + curl) ---
# git push https://github.com/<GHUSER>/awesome-openrouter add-openamer-agent
# Then open: https://github.com/OpenRouterTeam/awesome-openrouter/compare/main...<GHUSER>:awesome-openrouter:add-openamer-agent
```

---

## Validation recorded (2026-09-14)

- **Upstream validator**: `npm run validate openamer-agent` against the real
  `scripts/validate.js` → `✅ Valid` / `All validations passed`.
- `app.yaml` — parsed with Python `yaml.safe_load`, validated PASS against the upstream
  `schema/app.schema.json` (`required` present, `additionalProperties:false` satisfied).
  `description` = 215 chars (limit 300); `tags` = chat, coding, productivity (valid enum).
- `logo.png` — `file` reports `PNG image data, 256 x 256, 8-bit/color RGBA, non-interlaced`.
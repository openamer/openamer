# Porting Session — 2026-09-15

Complete upstream port from NousResearch/hermes-agent. All files branded (hermes→openamer), AST-validated, committed on main.

## Summary

| Wave | Subsystem | Files | Lines | Commit |
|------|-----------|-------|-------|--------|
| 1 | Free Tier | 3 | 1,464 | rebased to `bb72e3595` |
| 2 | Credential Pools | 4 | 3,277 | rebased |
| 3 | ACP (IDE protocol) | 14 | 4,165 | rebased |
| 4 | HA + ImageGen + Video + Spotify + Feishu | 21 | 8,848 | rebased |
| 5 | Kanban System | 17 | 6,750 | rebased |
| 6 | README/VISION cleanup | 2 | 3 | `40a09a91a` |
| 7 | Branding fix CLI dir | 33 renamed | — | `bb72e3595` |
| **Total** | **~50 files** | **~25,000 lines** | — | — |

## Key Commands Used

### File Discovery
```bash
curl -sL "https://api.github.com/repos/NousResearch/hermes-agent/git/trees/main?recursive=1" | python -c "import json,sys; d=json.load(sys.stdin); [print(i['path']) for i in d['tree'] if 'kanban' in i['path'].lower() and i['type']=='blob']"
```

### Download + Brand
```bash
for f in file1.py file2.py; do
  curl -sL "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/path/$f" | sed 's/hermes/openamer/g; s/Hermes/OpenAmer/g; s/HERMES/OPENAMER/g; s/NousResearch/openamer/g' > "target/$f"
done
```

### AST Validation
```bash
python -c "import ast; ast.parse(open('path').read()); print('AST OK')"
```

### Commit Message Fix
After initial commit with "hermes" in message, fixed via:
```bash
git commit --amend -m "docs: clean README and VISION upstream references"
git push --force-with-lease
```

### Rebase a specific commit message
```bash
GIT_EDITOR="sed -i 's/OLD/NEW/'" GIT_SEQUENCE_EDITOR="sed -i 's/^pick HASH/reword HASH/'" git rebase -i HEAD~N
```

## Key Lessons
1. **Batch curls** in a single shell loop for efficiency
2. **Validate ALL files** (AST) before committing
3. **One commit per system**, not per file
4. **Check for remaining branding** before push: exclude node_modules/.venv/website
5. **Zero "hermes" in commit messages** — even "remove hermes" contains it. Reword to "upstream"
6. **Force-push is acceptable** on a single-developer repo for branding fixes
7. **mv to existing dir** = MOVES INSIDE, not rename. Check target existence first

## Tools Used
- GitHub REST API (Trees + raw content via `raw.githubusercontent.com`)
- `sed` for multi-string branding replacement
- `curl` for file download
- `python -c "import ast"` for syntax validation
- `git rebase -i` + `git commit --amend` for history cleanup
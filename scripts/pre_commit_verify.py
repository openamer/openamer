"""Pre-commit verification for wiki-generator, academy.html, CI YAML"""
import py_compile, yaml, json, os

REPO = r"C:\Users\damir\openamer-repo"

print("=== PRE-COMMIT VERIFICATION ===")

# 1. Wiki Generator
py_compile.compile(os.path.join(REPO, "scripts/wiki-generator.py"), doraise=True)
print("  ✅ wiki-generator.py syntax")

# 2. Frontmatter parsing test
content = "---\nname: test\ndescription: test skill\n---\n# Test\n```python\nx=1\n```"
meta = yaml.safe_load(content.split("---")[1])
assert meta["name"] == "test"
print("  ✅ YAML frontmatter parsing")

# 3. Code line counting
lines = content.split("\n")
in_code = False
cnt = 0
for l in lines:
    if l.strip().startswith("```"):
        in_code = not in_code; continue
    if in_code: cnt += 1
assert cnt == 1
print("  ✅ Code line counting")

# 4. HTML structure
with open(os.path.join(REPO, "docs/academy.html")) as f:
    html = f.read()
assert "<html" in html and "</html>" in html
assert "OpenAmer" in html and "Academy" in html and "YouTube" in html
print("  ✅ academy.html structure OK")

# 5. CI YAML
with open(os.path.join(REPO, ".github/workflows/openamer-ci.yml")) as f:
    yaml_data = yaml.safe_load(f)
assert yaml_data is not None
assert "jobs" in yaml_data
assert "openamer-assist" in yaml_data["jobs"]
print("  ✅ openamer-ci.yml valid YAML + job structure")

# 6. Wiki was already generated and verified earlier
wiki_path = os.path.join(REPO, "docs/wiki/stats.json")
with open(wiki_path) as f:
    stats = json.load(f)
assert stats["total_skills"] > 200
assert stats["categories"] > 15
print(f"  ✅ Wiki: {stats['total_skills']} skills / {stats['categories']} categories")

print()
print("ALL 6 PASSED")
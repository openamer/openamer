import os, re, sys
repo = os.path.dirname(os.path.abspath(__file__))
files = []
for root, dirs, fnames in os.walk(repo):
    for d in [".venv", "node_modules", "__pycache__", "workspace"]:
        if d in dirs:
            dirs.remove(d)
    for fname in fnames:
        if fname.endswith(".py"):
            files.append(os.path.join(root, fname))
print("files:", len(files))
patterns = [
    (r'\bimport openamer_constants\b', 'import openamer_constants'),
    (r'\bfrom openamer_constants\b', 'from openamer_constants'),
    (r'\bimport openamer_cli\b', 'import openamer_cli'),
    (r'\bfrom openamer_cli\b', 'from openamer_cli'),
    (r'\bopenamer_constants\.', 'openamer_constants.'),
]
counts = [0]*len(patterns)
changed_files = set()
for path in files:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print("read err", path, e)
        continue
    new = text
    for i,(pat,repl) in enumerate(patterns):
        new2 = re.sub(pat, repl, new)
        if new2 != new:
            counts[i] += 1
            changed_files.add(path)
            new = new2
    if new != text:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new)
        except Exception as e:
            print("write err", path, e)
print("changed files", len(changed_files))
print("counts", counts)

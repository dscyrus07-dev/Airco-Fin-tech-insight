import re, glob, os
os.chdir(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
paths = set()
for f in glob.glob("app/api/**/route.ts", recursive=True):
    src = open(f, encoding="utf-8").read()
    for m in re.finditer(r"['\"`](/?[a-zA-Z0-9_/${}.-]{5,})['\"`]", src):
        p = m.group(1)
        if p.startswith("/api/") or p.startswith("/statements") or p.startswith("/jobs") or p.startswith("/upload") or p.startswith("/profile") or p.startswith("/sync") or p.startswith("/api-keys"):
            paths.add((f.replace("app/api/", "").replace("/route.ts", ""), p))
for a, b in sorted(paths):
    print(f"{a:52s} {b}")

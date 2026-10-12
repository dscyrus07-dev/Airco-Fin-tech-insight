# Python import graph: entries = app.main, routers, scripts; resolves app.*, relative, importlib strings
import ast, os, json, sys

BACKEND = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
entries = ["app/main.py"]
for dp, dn, fn in os.walk(os.path.join(BACKEND, "app", "api")):
    for f in fn:
        if f.endswith(".py"): entries.append(os.path.relpath(os.path.join(dp, f), BACKEND).replace(os.sep, "/"))
for dp, dn, fn in os.walk(os.path.join(BACKEND, "tests")):
    for f in fn:
        if f.startswith("test") and f.endswith(".py"): entries.append(os.path.relpath(os.path.join(dp, f), BACKEND).replace(os.sep, "/"))

def mod_to_path(m):
    return m.replace(".", "/") + ".py"

def deps(path):
    out = set()
    fp = os.path.join(BACKEND, path)
    try: tree = ast.parse(open(fp, encoding="utf-8", errors="replace").read())
    except Exception: return out
    pkg = path[:-3].replace("/", ".").split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("app"): out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[:len(pkg) - node.level + 1] if node.level <= len(pkg) else pkg
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            if mod.startswith("app"): out.add(mod)
            elif node.level and mod: out.add(mod)
        elif isinstance(node, ast.Call):
            fn_ = node.func
            name = getattr(fn_, "attr", getattr(fn_, "id", ""))
            if name in ("import_module", "__import__") and node.args:
                a0 = node.args[0]
                if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value.startswith("app"):
                    out.add(a0.value)
    return out

seen = set(); edges = {}
queue = [e.replace(os.sep, "/") for e in entries]
while queue:
    p = queue.pop()
    if p in seen or not p.endswith(".py"): continue
    seen.add(p)
    for m in deps(p):
        tp = mod_to_path(m)
        edges.setdefault(p, []).append(tp)
        if os.path.exists(os.path.join(BACKEND, tp)):
            queue.append(tp)
        else:
            ip = m.replace(".", "/") + "/__init__.py"
            if os.path.exists(os.path.join(BACKEND, ip)):
                edges[p].append(ip); queue.append(ip)
json.dump({"entries": entries, "reachable": sorted(seen), "edges": edges},
          open(os.path.join(os.path.dirname(__file__), "pygraph.json"), "w"), indent=0)
print("entries:", len(entries), "reachable:", len(seen))

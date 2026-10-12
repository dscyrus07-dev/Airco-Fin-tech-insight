# endpoints.py — public endpoint contract inventory + caller map.
import re, os, subprocess, json, csv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROUTES = os.path.join(ROOT, "backend", "app", "api", "routes")

def git(*a, cwd=None):
    return subprocess.run(["git", "-C", cwd or ROOT, *a], capture_output=True, text=True).stdout

# 1. extract decorators
eps = []  # (file, method, path)
for fn in os.listdir(ROUTES):
    if not fn.endswith(".py") or fn.startswith("__"): continue
    src = open(os.path.join(ROUTES, fn), encoding="utf-8").read()
    prefix = ""
    m = re.search(r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)", src)
    if m: prefix = m.group(1)
    for dm in re.finditer(r"@router\.(get|post|put|delete|patch)\(\s*[\"']([^\"']*)", src):
        eps.append((fn, dm.group(1).upper(), prefix + dm.group(2)))

# 2. caller evidence: frontend fetch/url, docs, scripts, e2e
search_dirs = {
    "frontend": ["frontend/app", "frontend/lib", "frontend/e2e", "e2e"],
    "docs": ["docs"],
    "scripts": ["scripts", "backend/scripts", "backend/tools"],
    "readme": ["README.md", "START.bat"],
}
def callers(path):
    # match path tail (strip leading /api or router-specific prefix variants)
    tails = {path, path.lstrip("/")}
    if "/api/" in path: tails.add(path.split("/api/",1)[1])
    if len(path) > 3: tails.add(path.rstrip("/"))
    found = set()
    for frag in list(tails):
        if len(frag) < 5: continue
        for area, dirs in search_dirs.items():
            for d in dirs:
                p = os.path.join(ROOT, d)
                if not os.path.exists(p): continue
                r = subprocess.run(["grep", "-rl", "--include=*.*", "-F", frag, p],
                                   capture_output=True, text=True)
                if r.stdout.strip(): found.add(area)
    return ",".join(sorted(found)) or "-"

out = os.path.join(ROOT, "docs", "cleanup", "ENDPOINTS.csv")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["file","method","path","callers"])
    for fn, m, p in eps: w.writerow([fn, m, p, callers(p)])
print(len(eps), "endpoints")

# INVENTORY.csv: every tracked file (+ untracked dirs), area, size, last-commit, owner-group
import subprocess, os, csv, sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
def git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout

# last commit date per path: one pass over history
last = {}
for line in git("log", "--format=|%ci", "--name-only", "--diff-filter=AM").splitlines():
    if line.startswith("|"):
        cur = line[1:].strip()
    elif line.strip() and line.strip() not in last:
        last[line.strip()] = cur

CLAUDE_OWNED = ("backend/app/services/statement_engine/", "backend/app/services/banks/",
                "backend/app/services/checks.py", "process_statement")

def area(p):
    if p.startswith("frontend/app/api/"): return "frontend-api-routes"
    if p.startswith("frontend/"): return "frontend"
    if p.startswith("backend/app/api/"): return "backend-api"
    if p.startswith("backend/app/services/banks/"): return "backend-parser"
    if p.startswith("backend/app/services/statement_engine/"): return "engine"
    if p.startswith("backend/app/services/"): return "backend-service"
    if p.startswith("backend/tests/"): return "tests"
    if p.startswith("backend/app/"): return "backend-api"
    if p.startswith("backend/"): return "backend-misc"
    if p.startswith("infra/"): return "infra-docker"
    if p.startswith("docs/"): return "docs"
    if p.startswith(("e2e/", "e2e_pdfs/")): return "e2e"
    if p.startswith("tools/"): return "scripts"
    if p.startswith(("database/", "auth/")): return "infra-misc"
    return "misc"

def owner(p):
    if p.startswith(CLAUDE_OWNED[0]) or p.startswith(CLAUDE_OWNED[1]) or p.endswith("checks.py") or "process_statement" in p:
        return "claude-owned"
    return "general"

rows = []
for p in git("ls-files").splitlines():
    fp = os.path.join(ROOT, p)
    try: size = os.path.getsize(fp)
    except OSError: size = -1
    rows.append([p, area(p), size, last.get(p, "?"), owner(p)])

# untracked entries
for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
    if line.startswith("??"):
        p = line[3:].strip()
        fp = os.path.join(ROOT, p)
        size = os.path.getsize(fp) if os.path.isfile(fp) else -2
        rows.append([p + (" [untracked]" if size == -2 else " [untracked]"), "untracked", size, "n/a", "general"])

out = os.path.join(ROOT, "docs/cleanup/INVENTORY.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["path", "area", "size_bytes", "last_commit", "owner_group"]); w.writerows(rows)
print(len(rows), "rows ->", out)

# classify.py — merge all evidence into VERDICTS.csv.
# Evidence codes: A=static import graph, B=string/dynamic refs, C=runtime coverage,
# D=external contract, E=test dependency, F=docs/hygiene.
import json, csv, os, subprocess, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOOLS = os.path.dirname(__file__)

def git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout

tracked = git("ls-files").splitlines()

# ---- evidence sets ----
py = json.load(open(os.path.join(TOOLS, "pygraph.json")))
PY_REACH = set(py["reachable"])                       # 'app/...' backend-relative
ts = json.load(open(os.path.join(TOOLS, "tsgraph.json")))
TS_REACH = set(ts["reachable"])                       # 'app/...' frontend-relative
TS_ENTRIES = set(ts["entries"])

# lazy-import processor tree: every bank package module reachable via _PROCESSOR_IMPORTS packages
LAZY = set()
for p in tracked:
    if re.match(r"backend/app/services/banks/[^/]+/", p):
        LAZY.add(p.replace("backend/", ""))
# pipeline package pulled lazily by base_processor
for p in tracked:
    if p.startswith("backend/app/services/pipeline/"):
        LAZY.add(p.replace("backend/", ""))
# engine extractor package __init__ pulls extractor.py via __init__ imports
for p in tracked:
    if "/extractors/" in p and p.endswith("extractor.py"):
        LAZY.add(p.replace("backend/", ""))

# test coverage (modules with >0 executed lines)
cov = json.load(open(os.path.join(TOOLS, "cov_tests.json")))
COV_HIT = {f.replace("\\", "/") for f, d in cov["files"].items() if d["summary"]["covered_lines"] > 0}
COV_SEEN = {f.replace("\\", "/") for f in cov["files"]}

# corpus coverage (if present)
CORP_HIT = set()
cf = os.path.join(TOOLS, "cov_corpus.json")
if os.path.exists(cf):
    cc = json.load(open(cf))
    CORP_HIT = {f.replace("\\", "/") for f, d in cc["files"].items() if d["summary"]["covered_lines"] > 0}

def bmod(path):  # repo path -> backend module path used in evidence sets
    return path.replace("backend/", "")

KEEP_CONTRACT_ROUTES = set()  # all app/api/routes/*.py + frontend app/api/**
KEEP_CORE_FRONT = {  # rendered in at least one supported mode
    "app/components/Dashboard.tsx", "app/components/layout/Header.tsx", "app/page.tsx",
    "app/layout.tsx", "app/dashboard/page.tsx", "app/dashboard/api-keys/page.tsx",
    "app/auth/callback/page.tsx", "app/globals.css",
}
AFTER_SOAK = {
    "app/components/layout/StepForm.tsx": "legacy details step; only Dashboard(flag-off) + page.tsx dead-import + own test",
    "app/components/upload/UploadStep.tsx": "legacy upload step; same reach pattern as StepForm",
    "app/components/upload/ModeSelection.tsx": "mode step; skipped in unified mode",
    "app/components/analyze/AnalyzeFlow.tsx": "analyze page body; page redirects to /dashboard when flag on",
    "app/analyze/page.tsx": "redirects to /dashboard when flag on; after soak remove page entirely",
    "lib/flags.ts": "the flag gate itself; remove with the gate",
}
SAFE_DELETE = {
    "lib/api.ts": "0 importers; Dashboard defines its own uploadStatement; exports unused anywhere",
}
MANUAL = {  # path -> (verdict, evidence, note)
    # build/config at backend root
    "backend/Dockerfile": ("KEEP-CORE", "D", "image build"),
    "backend/requirements.txt": ("KEEP-CORE", "D", "deps manifest"),
    "backend/alembic.ini": ("KEEP-CORE", "D", "migrations config"),
    "backend/README.md": ("KEEP-CORE", "F", "backend docs"),
    "backend/words.json": ("KEEP-CORE", "B", "loaded by bank classifiers"),
    "backend/data/parser_metrics.json": ("KEEP-CORE", "C", "runtime metrics store path"),
    "backend/data/unsupported_formats/queue.json": ("KEEP-CORE", "C", "runtime queue store"),
    # dead backend modules (A:0 importers, B:0 refs, C:0% coverage, D/E/F: none)
    "backend/app/core/security.py": ("SAFE-DELETE", "ABCEF", "0 importers; auth is Keycloak; 0% cov; no doc/test refs"),
    "backend/app/services/monitoring/error_logger.py": ("SAFE-DELETE", "ABCEF", "0 importers (init imports health_monitor only); 0% cov; no refs"),
    # one-off audit probe at backend root — named in archive/ops docs only
    "backend/_probe_audit.py": ("UNSURE", "BF", "referenced by PII_REMEDIATION/ARCH_INVENTORY/CODE_HYGIENE docs; one-off audit script"),
    # package inits that carry the tree
    "backend/app/__init__.py": ("KEEP-CORE", "A", "package root"),
    "backend/app/core/__init__.py": ("KEEP-CORE", "A", "package init for core.config"),
    "backend/app/utils/__init__.py": ("KEEP-CORE", "A", "package init"),
    # dev/bench tooling — referenced only in archive docs + AGENT_STATE
    "backend/tools/propose_layouts.py": ("KEEP-CONTRACT", "BF", "layout-proposal tool; named in ARCHITECTURE/REPO_INVENTORY docs"),
    "backend/tools/regression_gate.py": ("KEEP-CONTRACT", "BF", "regression gate tool; named in docs"),
    "backend/tools/u3_measure.py": ("KEEP-CONTRACT", "BF", "universal-tier measurement tool; named in UNIVERSAL_RESULTS"),
    "backend/tools/u3_remeasure.py": ("KEEP-CONTRACT", "BF", "universal-tier measurement tool; named in UNIVERSAL_RESULTS"),
    "backend/tools/u3c_crosscheck.py": ("KEEP-CONTRACT", "BF", "u3 crosscheck tool; named in ENGINE_OBSERVABILITY"),
    # repo-root ops scripts
    "scripts/frontend-app-client.json": ("KEEP-CONTRACT", "D", "keycloak client config used by setup scripts"),
    "scripts/pkce-clear.json": ("KEEP-CONTRACT", "D", "keycloak pkce config used by setup scripts"),
}

def classify(p):
    ev = set()
    note = []
    if p in MANUAL:
        return MANUAL[p]
    if p.startswith("frontend/"):
        rel = p[len("frontend/"):]
        if rel in TS_REACH: ev.add("A")
        if rel in TS_ENTRIES: ev.add("E")
        if rel in AFTER_SOAK:
            return "DELETE-AFTER-SOAK", "AE", AFTER_SOAK[rel]
        if rel in SAFE_DELETE:
            ev2 = ev | {"B?"}
            return "SAFE-DELETE", "".join(sorted(ev2)) or "B", SAFE_DELETE[rel]
        if rel.startswith("app/api/"): ev.add("D")
        if rel in KEEP_CORE_FRONT: ev.add("C")
        if "/__tests__/" in rel or re.search(r"\.(test|spec)\.", rel): ev.add("E")
        if rel.startswith("public/"): return "KEEP-CORE", "D", "static asset"
        if rel in ("package.json", "package-lock.json", "tsconfig.json", "next.config.ts",
                   "next.config.mjs", "postcss.config.mjs", "tailwind.config.ts", "vitest.config.ts",
                   "Dockerfile", "middleware.ts") or rel.endswith((".json", ".ts", ".mjs")) and "/" not in rel:
            return "KEEP-CORE", "D", "build/config"
        return "KEEP-CORE" if "A" in ev else "KEEP-CORE", "".join(sorted(ev)) or "D", ""
    if p.startswith("backend/"):
        m = bmod(p)
        if m in PY_REACH: ev.add("A")
        if m in LAZY: ev.add("B")
        if m in COV_HIT: ev.add("C")
        if m in CORP_HIT: ev.add("C")
        if p.startswith("backend/app/api/routes/"): ev.add("D")
        if p.startswith("backend/tests/"): ev.add("E")
        if p.startswith("backend/app/services/statement_engine/") or p.startswith("backend/app/services/banks/"):
            cls = "KEEP-FALLBACK" if "/banks/" in p else "KEEP-CORE"
            return cls, "".join(sorted(ev)) or "B", "engine/parser cohort"
        if not ev:
            return "UNSURE", "-", "no static/dynamic/runtime/contract/test evidence"
        return "KEEP-CORE", "".join(sorted(ev)), ""
    if p.startswith("docs/"):
        return "KEEP-CORE", "F", "documentation"
    if p.startswith(("e2e/", "e2e_pdfs/")):
        return "KEEP-TEST", "E", "synthetic E2E fixtures/scripts"
    if p.startswith("infra/"):
        return "KEEP-CORE", "D", "infra"
    if p.startswith("auth/"):
        return "KEEP-CORE", "D", "auth service"
    if p.startswith("database/"):
        return "KEEP-CONTRACT", "D", "migrations"
    if p.startswith("scripts/"):
        return "UNSURE", "B?", "ops script — reference check needed"
    if p.startswith("comparison/"):
        return "UNSURE", "F", "historical analysis artifact"
    return "KEEP-CORE", "D", "repo root file"

with open(os.path.join(ROOT, "docs/cleanup/VERDICTS.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["path", "verdict", "evidence", "notes"])
    counts = {}
    for p in tracked:
        v, e, n = classify(p)
        w.writerow([p, v, e, n])
        counts[v] = counts.get(v, 0) + 1
print(counts)

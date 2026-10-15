"""N8 secrets scan: regex rules over working tree and `git log -p` history.
Reports sha-commit, path, rule type ONLY — never the value.
Usage: python secret_scan.py [--tree] [--history] [--since=<ref>]"""
import re, os, sys, subprocess, json

RULES = [
    ("aws_access_key",     re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_key",     re.compile(r"(?i)(aws_secret|secret_access_key)\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{35,}")),
    ("private_key_block",  re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY")),
    ("generic_secret",     re.compile(r"(?i)\b(secret|api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]")),
    ("password_assign",    re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*['\"][^'\"\s]{6,}['\"]")),
    ("url_with_creds",     re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
    ("bearer_jwt",         re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("supabase_service",   re.compile(r"(?i)(service_role|supabase[_-]?(service|secret|key))\s*[:=]\s*['\"][^'\"]{20,}")),
    ("slack_token",        re.compile(r"\bxox[baprs]-[0-9a-zA-Z-]{10,}")),
    ("stripe_key",         re.compile(r"\b(sk|pk|rk)_(live|test)_[0-9a-zA-Z]{16,}\b")),
    ("github_token",       re.compile(r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[0-9a-zA-Z_]{20,}\b")),
    ("google_api_key",     re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("sendgrid_key",       re.compile(r"\bSG\.[0-9A-Za-z_-]{20,}\.[0-9A-Za-z_-]{20,}\b")),
    ("pem_block",          re.compile(r"-----BEGIN CERTIFICATE-----")),
    ("db_conn_string",     re.compile(r"(?i)(postgres|postgresql|mysql|mongodb|redis)://[^/\s:@]+:[^/\s@]+@")),
    ("env_file_assignment",re.compile(r"(?i)^[A-Z_]*(SECRET|TOKEN|KEY|PASSWORD|PASS)[A-Z_]*\s*=\s*[^\s#]{8,}")),
]
SKIP_DIRS = {".git", "node_modules", ".next", "dist", "build", "__pycache__", ".local", "venv", ".venv"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".xlsx", ".zip", ".pyc", ".woff", ".woff2", ".ico", ".lock", ".mp4"}
# allowlist: obvious placeholders / public values
ALLOW = re.compile(r"(?i)(your-|changeme|example|placeholder|xxx|<.*>|\$\{|\{\{|test123|dummy|fake|TODO|sample)")


def scan_line(line):
    hits = []
    for name, rgx in RULES:
        if rgx.search(line):
            hits.append(name)
    return hits


def scan_tree(root):
    findings = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            p = os.path.join(dirpath, fn)
            if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                continue
            rel = os.path.relpath(p, root)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        for rule in scan_line(line):
                            if not ALLOW.search(line):
                                findings.append({"scope": "tree", "path": rel, "line": i, "rule": rule})
            except OSError:
                pass
            if fn.startswith(".env") or fn.endswith(".env") or ".env." in fn:
                findings.append({"scope": "tree", "path": rel, "line": 0, "rule": "env_file_present"})
    return findings


def scan_history():
    """git log -p --all: attribute secret-looking added lines to commit+path."""
    findings = []
    proc = subprocess.Popen(
        ["git", "log", "--all", "-p", "--no-color", "--pretty=format:@@COMMIT@@%H",
         "--diff-filter=AM"],
        stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    commit = path = None
    for line in proc.stdout:
        if line.startswith("@@COMMIT@@"):
            commit = line[10:].strip()[:12]
        elif line.startswith("+++ b/"):
            path = line[6:].strip()
        elif line.startswith("+") and not line.startswith("+++"):
            for rule in scan_line(line[1:]):
                if not ALLOW.search(line):
                    findings.append({"scope": "history", "commit": commit, "path": path, "rule": rule})
    proc.wait()
    return findings


if __name__ == "__main__":
    root = sys.argv[sys.argv.index("--root") + 1] if "--root" in sys.argv else "."
    res = []
    if "--tree" in sys.argv or not sys.argv[1:]:
        res += scan_tree(root)
    if "--history" in sys.argv:
        res += scan_history()
    # de-dup (path+rule or commit+path+rule)
    seen, uniq = set(), []
    for f in res:
        k = (f.get("commit"), f["path"], f["rule"])
        if k not in seen:
            seen.add(k); uniq.append(f)
    print(json.dumps(uniq, indent=1))

import re, subprocess, sys, collections
# scan added lines + new files in diff base..tip for PII/secret patterns
PATS = {
 'email': re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
 'phone_in': re.compile(r'(?<!\d)(?:\+91[ -]?)?[6-9]\d{9}(?!\d)'),
 'pan': re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),
 'aadhaar': re.compile(r'\b\d{4}[ -]\d{4}[ -]\d{4}\b'),
 'acct_like': re.compile(r'\b\d{11,18}\b'),
 'jwt': re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}'),
 'apikey': re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[A-Za-z0-9_/+\-.]{12,}'),
 'aws': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
}
allow_email = {'test@airco.com','users.noreply.github.com','devin.ai','example.com','example.org'}
hits = collections.defaultdict(list)
diff = subprocess.run(['git','diff','8b57e0d..devin/onboard-wire','--unified=0'],capture_output=True,text=True).stdout
curfile=None
for i,line in enumerate(diff.splitlines()):
    if line.startswith('+++'):
        curfile=line[6:]; continue
    if not line.startswith('+') or line.startswith('+++'): continue
    t=line[1:]
    for name,pat in PATS.items():
        for m in pat.finditer(t):
            s=m.group(0)
            if name=='email' and any(a in s for a in allow_email): continue
            if name=='apikey' and ('${' in t or 'KEYCLOAK_' in t or 'env' in t.lower() and '=' not in s): continue
            hits[name].append(f"{curfile}: {t.strip()[:80]}")
for name,lst in hits.items():
    print(name, len(lst))
    for h in lst[:15]: print('  ',h)
if not hits: print('CLEAN')

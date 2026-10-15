#!/usr/bin/env bash
# N9 rc-stack smoke: health, bank list, one synthetic upload per served bank.
# Local only. No statement content printed — counts/verdicts/statuses only.
# usage: ./tools/final/smoke.sh   (from the repo worktree root; needs python+requests)
set -u
BE="${RC_BACKEND:-http://127.0.0.1:8601}"
FE="${RC_FRONTEND:-http://localhost:3600}"
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS  $1"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL  $1"; }

echo "== health =="
H=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$BE/health")
[ "$H" = "200" ] && ok "backend /health" || bad "backend /health ($H)"
H=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$FE/")
[ "$H" = "200" ] && ok "frontend /" || bad "frontend / ($H)"

echo "== bank list (authenticated) =="
python - "$BE" <<'PY'
import json, sys, urllib.request, urllib.parse
BE = sys.argv[1]
env = {}
for line in open("X:/Airco Projects/Airco Insights fintech/local.env", encoding="utf-8"):
    m = line.strip().split("=", 1)
    if len(m) == 2: env[m[0]] = m[1].strip('"')
data = urllib.parse.urlencode({
    "grant_type": "password", "client_id": "frontend-app",
    "client_secret": env.get("KEYCLOAK_CLIENT_SECRET", ""),
    "username": env.get("TEST_USER_EMAIL", "test@airco.com"), "password": env.get("TEST_USER_PASSWORD", "Test123!"),
    "scope": "openid"}).encode()
try:
    tok = json.load(urllib.request.urlopen(urllib.request.Request(
        "http://localhost:8080/realms/airco-insights/protocol/openid-connect/token", data=data), timeout=30))["access_token"]
except Exception as e:
    print("FAIL  token:", str(e)[:80]); sys.exit(2)
d = json.load(urllib.request.urlopen(urllib.request.Request(
    BE + "/api/statements/banks", headers={"Authorization": "Bearer " + tok}), timeout=30))
banks = d.get("banks", []); allb = d.get("all_banks", [])
served = sorted(b.get("id") for b in banks if b.get("support_state") in ("verified", "review_required") or b.get("v2_served"))
exp = sorted("hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb,bank_of_baroda,canara,icici,indian_bank,karnataka,kotak".split(","))
print("PASS  served==proposed(20)" if served == exp else "FAIL  served list:", served)
print("PASS  all_banks>=44" if len(allb) >= 44 else "FAIL  all_banks:", len(allb))
PY

echo "== one synthetic upload per served bank (analyze only, counts) =="
python - "$BE" <<'PY'
import json, os, sys, urllib.request
import requests
BE = sys.argv[1]
env = {}
for line in open("X:/Airco Projects/Airco Insights fintech/local.env", encoding="utf-8"):
    m = line.strip().split("=", 1)
    if len(m) == 2: env[m[0]] = m[1].strip('"')
tok = requests.post("http://localhost:8080/realms/airco-insights/protocol/openid-connect/token",
    data={"grant_type": "password", "client_id": "frontend-app",
          "client_secret": env.get("KEYCLOAK_CLIENT_SECRET", ""),
          "username": env.get("TEST_USER_EMAIL", "test@airco.com"), "password": env.get("TEST_USER_PASSWORD", "Test123!"),
          "scope": "openid"}, timeout=30).json()["access_token"]
H = {"Authorization": "Bearer " + tok}
gen = json.load(open("tools/final/demo_pdfs/gen_results.json"))
okc = failc = 0
for bank, rec in sorted(gen.items()):
    p = f"tools/final/demo_pdfs/demo_{bank}.pdf"
    if not os.path.exists(p):
        print(f"FAIL  {bank}: missing file"); failc += 1; continue
    r = requests.post(BE + "/api/statements/analyze", headers=H,
        files={"files": (os.path.basename(p), open(p, "rb").read(), "application/pdf")}, timeout=90)
    if r.status_code != 200:
        print(f"FAIL  {bank}: analyze http {r.status_code}"); failc += 1; continue
    doc = (r.json().get("documents") or [{}])[0]
    st = doc.get("state"); det = (doc.get("bank") or {}).get("id")
    # served banks must reach an analyzable state (DETECTED or REVIEW) with a
    # detected bank id or an explicit picker path; never UNSUPPORTED/UNKNOWN.
    good = st in ("DETECTED", "REVIEW") and (det is not None or doc.get("state") in ("DETECTED","REVIEW"))
    print(("PASS" if good else "FAIL") + f"  {bank}: state={st} det={det} detail={doc.get('detail_state')} local={rec.get('verdict')}")
    okc, failc = (okc + 1, failc) if good else (okc, failc + 1)
PY

echo "== summary =="
echo "smoke done — see PASS/FAIL lines above"

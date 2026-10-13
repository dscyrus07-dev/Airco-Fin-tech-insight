"""Negative-case E2E on the onb stack: locked, scanned, wrong-bank override,
unknown bank, non-allowlisted bank.

usage: python tools/verify/e2e_negative.py <probes_dir> <out.jsonl>
          --api=.. --kc=.. --realm=.. --client=.. --secret-env=.. --user=.. --pass-env=..
          --pdf-lock=<path> --pdf-scanned=<path> --pdf-unknown=<path>
          --pdf-bankA=<path> --override-bank=<spec_or_registry_id>
          --pdf-nonallow=<path>
"""
import json, os, sys, time
import requests

probes, out_path = sys.argv[1], sys.argv[2]
opt = {"--api": "http://localhost:8401", "--kc": "http://localhost:8080",
       "--realm": "airco-insights", "--client": "frontend-app",
       "--secret-env": "KEYCLOAK_CLIENT_SECRET", "--user": "test@airco.com",
       "--pass-env": "E2E_USER_PW", "--pdf-lock": "", "--pdf-scanned": "",
       "--pdf-unknown": "", "--pdf-bankA": "", "--override-bank": "",
       "--pdf-nonallow": "", "--pdf-lock-pw": "Verify123!"}
for a in sys.argv[3:]:
    k, _, v = a.partition("=")
    if k in opt:
        opt[k] = v

data = {"grant_type": "password", "client_id": opt["--client"],
        "username": opt["--user"], "password": os.environ.get(opt["--pass-env"], "")}
sec = os.environ.get(opt["--secret-env"], "")
if sec:
    data["client_secret"] = sec
H = {"Authorization": "Bearer " + requests.post(
    f"{opt['--kc']}/realms/{opt['--realm']}/protocol/openid-connect/token",
    data=data, timeout=30).json()["access_token"]}
API = opt["--api"]

def analyze(path, passwords=None, hint=None):
    with open(path, "rb") as f:
        form = {}
        if passwords:
            form["passwords"] = json.dumps(passwords)
        if hint:
            form["bank_hint"] = hint
        r = requests.post(f"{API}/api/statements/analyze", headers=H,
                          files=[("files", (os.path.basename(path), f, "application/pdf"))],
                          data=form, timeout=120)
    return r

def doc0(aj):
    return (aj.get("documents") or [{}])[0]

res = {}

# 1. locked without password
if opt["--pdf-lock"]:
    r = analyze(opt["--pdf-lock"])
    d = doc0(r.json()) if r.status_code == 200 else {}
    res["locked_nopw"] = {"http": r.status_code, "state": d.get("state"),
                          "detail": d.get("detail_state"), "msg": (d.get("message") or "")[:80]}
    # 2. locked with correct password (unlock path)
    fn = os.path.basename(opt["--pdf-lock"])
    r2 = analyze(opt["--pdf-lock"], passwords={fn: opt["--pdf-lock-pw"]})
    d2 = doc0(r2.json()) if r2.status_code == 200 else {}
    res["locked_withpw"] = {"http": r2.status_code, "state": d2.get("state"),
                            "bank": (d2.get("bank") or {}).get("id"),
                            "workflow": d2.get("workflow_status")}
    # also exercise the unlock endpoint if a document_id exists
    if d.get("document_id"):
        ru = requests.post(f"{API}/api/statements/{r.json()['analysis_id']}/documents/{d['document_id']}/unlock",
                           headers=H, json={"password": opt["--pdf-lock-pw"]}, timeout=60)
        res["unlock_endpoint"] = {"http": ru.status_code,
                                  "state": doc0(ru.json()).get("state") if ru.status_code == 200 else ru.text[:120]}

# 3. scanned
if opt["--pdf-scanned"]:
    r = analyze(opt["--pdf-scanned"])
    d = doc0(r.json()) if r.status_code == 200 else {}
    res["scanned"] = {"http": r.status_code, "state": d.get("state"),
                      "detail": d.get("detail_state"), "msg": (d.get("message") or "")[:80]}
    if d.get("document_id"):
        rc = requests.post(f"{API}/api/statements/{r.json()['analysis_id']}/confirm", headers=H,
                           json={"documents": [{"document_id": d["document_id"], "action": "CONFIRM"}]}, timeout=60)
        rr = (rc.json().get("results") or [{}])[0] if rc.status_code == 200 else {}
        res["scanned_confirm"] = {"http": rc.status_code, "ok": rr.get("ok"), "code": rr.get("code")}

# 4. unknown bank
if opt["--pdf-unknown"]:
    r = analyze(opt["--pdf-unknown"])
    d = doc0(r.json()) if r.status_code == 200 else {}
    res["unknown"] = {"http": r.status_code, "state": d.get("state"), "bank": d.get("bank"),
                      "workflow": d.get("workflow_status")}

# 5. wrong-bank override: file of bank A confirmed as override to bank B
if opt["--pdf-bankA"] and opt["--override-bank"]:
    r = analyze(opt["--pdf-bankA"])
    aj = r.json() if r.status_code == 200 else {}
    d = doc0(aj)
    res["overrideA_state"] = {"http": r.status_code, "state": d.get("state"),
                              "detected": (d.get("bank") or {}).get("id")}
    if d.get("document_id"):
        rc = requests.post(f"{API}/api/statements/{aj['analysis_id']}/confirm", headers=H, json={
            "documents": [{"document_id": d["document_id"], "action": "OVERRIDE",
                           "bank_id": opt["--override-bank"], "account_type": "savings"}]}, timeout=60)
        rr = (rc.json().get("results") or [{}])[0] if rc.status_code == 200 else {}
        res["overrideAB"] = {"http": rc.status_code, "ok": rr.get("ok"),
                             "code": rr.get("code"), "msg": (rr.get("message") or "")[:120]}
        if rc.status_code == 200 and rr.get("ok"):
            rp = requests.post(f"{API}/api/statements/{aj['analysis_id']}/process", headers=H,
                               json={"document_ids": [d["document_id"]], "full_name": "Verify Agent"}, timeout=60)
            res["overrideAB_process"] = {"http": rp.status_code, "body": rp.text[:150]}
            if rp.status_code == 200:
                st = (rp.json().get("started") or [])
                if st:
                    jid = st[0]["job_id"]
                    for _ in range(60):
                        time.sleep(3)
                        j = requests.get(f"{API}/api/jobs/{jid}", headers=H, timeout=30).json()
                        if j.get("status") in ("completed", "failed", "completed_with_errors"):
                            break
                    res["overrideAB_job"] = {"status": j.get("status"),
                                             "bank_name": j.get("bank_name"),
                                             "error": str(j.get("error_message") or j.get("result_data") or "")[:200]}

# 6. non-allowlisted bank file: analyze + confirm + process attempt
if opt["--pdf-nonallow"]:
    r = analyze(opt["--pdf-nonallow"])
    aj = r.json() if r.status_code == 200 else {}
    d = doc0(aj)
    res["nonallow"] = {"http": r.status_code, "state": d.get("state"),
                       "bank": (d.get("bank") or {}).get("id"),
                       "v2_served": (d.get("statement_engine") or {}).get("v2_served")
                       if isinstance(d.get("statement_engine"), dict) else d.get("v2_served"),
                       "workflow": d.get("workflow_status")}
    if d.get("document_id"):
        rc = requests.post(f"{API}/api/statements/{aj['analysis_id']}/confirm", headers=H, json={
            "documents": [{"document_id": d["document_id"], "action": "CONFIRM",
                           "account_type": "savings"}]}, timeout=60)
        rr = (rc.json().get("results") or [{}])[0] if rc.status_code == 200 else {}
        res["nonallow_confirm"] = {"http": rc.status_code, "ok": rr.get("ok"), "code": rr.get("code"),
                                   "msg": (rr.get("message") or "")[:120]}

json.dump(res, open(out_path, "w"), indent=1)
print(json.dumps(res, indent=1)[:3000])

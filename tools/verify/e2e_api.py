"""End-to-end driver against the onb stack (real HTTP, real jobs).

usage: python tools/verify/e2e_api.py <manifest_dir> <run.jsonl> <out.jsonl>
           --api=http://localhost:8401 --kc=http://localhost:8080
           --realm=airco-insights --client=frontend-app
           --secret-env=KEYCLOAK_CLIENT_SECRET --user=.. --pass-env=E2E_PW
           [--banks=b1,b2] [--per-bank 2]
Env vars named by --secret-env/--pass-env hold credentials; never printed.
"""
import json, os, sys, time, urllib.parse, urllib.request
import requests

manifest_dir, run_path, out_path = sys.argv[1:4]
opt = {"--api": "http://localhost:8401", "--kc": "http://localhost:8080",
       "--realm": "airco-insights", "--client": "frontend-app",
       "--secret-env": "KEYCLOAK_CLIENT_SECRET", "--user": "test@airco.com",
       "--pass-env": "E2E_USER_PW", "--per-bank": "2"}
banks = set()
for a in sys.argv[4:]:
    k, _, v = a.partition("=")
    if k == "--banks":
        banks = set(v.split(","))
    elif k in opt:
        opt[k] = v

API, KC, REALM, CLIENT = opt["--api"], opt["--kc"], opt["--realm"], opt["--client"]
USER = opt["--user"]
SECRET = os.environ.get(opt["--secret-env"], "")
PW = os.environ.get(opt["--pass-env"], "")

def login():
    data = {"grant_type": "password", "client_id": CLIENT, "username": USER, "password": PW}
    if SECRET:
        data["client_secret"] = SECRET
    r = requests.post(f"{KC}/realms/{REALM}/protocol/openid-connect/token", data=data, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}

H = login()

# index corpus paths
folders = json.load(open(os.path.join(manifest_dir, "folders.json")))
f2b = {f: m["bank_id"] for f, m in folders.items() if isinstance(m, dict) and m.get("bank_id")}
paths = {}
for mf in ("manifest_0.jsonl", "manifest_1.jsonl"):
    for ln in open(os.path.join(manifest_dir, mf)):
        d = json.loads(ln)
        p = d.get("path", "")
        top = p.replace(os.sep, "/").split("Unified All Statements/")[-1].split("/")[0]
        if f2b.get(top):
            paths[d["sha8"]] = (p, f2b[top])

runs = [json.loads(ln) for ln in open(run_path, encoding="utf-8")]
bybank = {}
for rec in runs:
    if rec.get("status") == "v2" and rec["sha8"] in paths and (not banks or rec["exp"] in banks):
        bybank.setdefault(rec["exp"], []).append(rec)

done = set()
if os.path.exists(out_path):
    done = {json.loads(ln)["sha8"] for ln in open(out_path, encoding="utf-8")}

def analyze_one(path):
    with open(path, "rb") as f:
        r = requests.post(f"{API}/api/statements/analyze", headers=H,
                          files=[("files", (os.path.basename(path), f, "application/pdf"))], timeout=120)
    return r

n = 0
with open(out_path, "a", encoding="utf-8") as out:
    for b in sorted(bybank):
        for rec in bybank[b][: int(opt["--per-bank"])]:
            sha = rec["sha8"]
            if sha in done:
                continue
            path = paths[sha][0]
            H = login()  # short-lived token; refresh per file
            row = {"sha8": sha, "bank": b, "shadow": {"status": rec.get("status"),
                   "layout": rec.get("layout"), "verdict": rec.get("verdict"),
                   "rows": rec.get("rows"), "det": rec.get("det_bank")}}
            ra = analyze_one(path)
            row["analyze_http"] = ra.status_code
            if ra.status_code != 200:
                row["analyze_body"] = ra.text[:200]
                out.write(json.dumps(row) + "\n"); out.flush(); n += 1
                continue
            aj = ra.json()
            docs = aj.get("documents") or []
            row["analysis_id"] = aj.get("analysis_id")
            if not docs:
                row["note"] = "no_documents"
                out.write(json.dumps(row) + "\n"); out.flush(); n += 1
                continue
            d = docs[0]
            row["doc"] = {k: d.get(k) for k in ("document_id", "state", "detected_bank", "engines",
                          "v2_served", "verdict", "rows_read", "statement_engine")}
            did = d.get("document_id")
            # confirm
            rc = requests.post(f"{API}/api/statements/{aj['analysis_id']}/confirm", headers=H, json={
                "documents": [{"document_id": did, "action": "CONFIRM",
                               "account_type": "auto_detect"}]}, timeout=60)
            row["confirm_http"] = rc.status_code
            crow = {}
            try:
                crow = (rc.json().get("results") or [{}])[0]
            except Exception:
                pass
            row["confirm_result"] = crow
            if rc.status_code != 200:
                row["confirm_body"] = rc.text[:200]
            elif crow.get("ok") is False:
                pass
            else:
                rp = requests.post(f"{API}/api/statements/{aj['analysis_id']}/process", headers=H,
                                   json={"document_ids": [did], "full_name": "Verify Agent"}, timeout=60)
                row["process_http"] = rp.status_code
                if rp.status_code == 200:
                    started = (rp.json().get("started") or [])
                    if started:
                        jid = started[0]["job_id"]
                        row["job_id"] = jid
                        st = ""
                        for _ in range(60):
                            time.sleep(3)
                            j = requests.get(f"{API}/api/jobs/{jid}", headers=H, timeout=30).json()
                            st = j.get("status")
                            if st in ("completed", "failed", "completed_with_errors"):
                                break
                        row["job_status"] = st
                        row["job_bank_name"] = j.get("bank_name")
                        if st in ("completed", "completed_with_errors"):
                            rd = requests.get(f"{API}/api/jobs/{jid}/download", headers=H, timeout=60)
                            row["download_http"] = rd.status_code
                            if rd.status_code == 200:
                                xdir = os.path.join(os.path.dirname(out_path), "xlsx")
                                os.makedirs(xdir, exist_ok=True)
                                xp = os.path.join(xdir, sha + ".xlsx")
                                open(xp, "wb").write(rd.content)
                                row["xlsx"] = xp
                else:
                    row["process_body"] = rp.text[:200]
            out.write(json.dumps(row) + "\n")
            out.flush()
            n += 1
            print("done", b, sha, row.get("job_status"), flush=True)
print("E2E_DONE", n)

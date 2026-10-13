"""verify2 E2E: real HTTP flow against the onb stack.
Flow per file: analyze -> confirm/override -> process -> poll job -> download -> workbook checks.
Own implementation for prompt-28; auth via keycloak password grant; no statement content printed.
usage: python tools/verify2/e2e2.py <backend_dir> <out.jsonl> --files=sha8,sha8,... [--hint=bank] [--override=bank:sha8] [--timeout=240]
env: KC_SECRET (client secret), E2E_USER_PW (user password)"""
import json, os, sys, glob, time, io
import requests

backend, out_path = sys.argv[1], sys.argv[2]
sha8s, hint, overrides, timeout = [], None, {}, 480
for a in sys.argv[3:]:
    if a.startswith("--files="): sha8s = a[8:].split(",")
    elif a.startswith("--hint="): hint = a[7:]
    elif a.startswith("--override="):
        b, _, s = a[11:].partition(":"); overrides[s] = b
    elif a.startswith("--timeout="): timeout = int(a[10:])

API = "http://127.0.0.1:8401"
KC = "http://localhost:8080"
SECRET = os.environ.get("KC_SECRET", "airco-frontend-secret")
PW = os.environ.get("E2E_USER_PW", "Test123!")

def login():
    r = requests.post(f"{KC}/realms/airco-insights/protocol/openid-connect/token",
                      data={"grant_type": "password", "client_id": "frontend-app",
                            "client_secret": SECRET, "username": "test@airco.com", "password": PW}, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}

mani = {}
for m in glob.glob(os.path.join(os.path.dirname(__file__), ".local", "manifest_*.jsonl")):
    for ln in open(m, encoding="utf-8"):
        d = json.loads(ln); mani[d["sha8"]] = d["path"]

def analyze(H, files):
    up = [("files", (s8 + ".pdf", open(mani[s8], "rb").read(), "application/pdf")) for s8 in files]
    data = {}
    if hint: data["bank_hint"] = hint
    r = requests.post(f"{API}/api/statements/analyze", headers=H, files=up, data=data, timeout=120)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200])

def workbook_check(buf):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(buf), data_only=False)
    out = {"sheets": wb.sheetnames}
    errs = []
    tx_rows = 0
    sc = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("#") and any(
                        e in c.value for e in ("REF", "VALUE", "DIV", "NAME", "N/A", "NULL", "NUM")):
                    errs.append(f"{ws.title}!{c.coordinate}")
    for name in wb.sheetnames:
        if name.lower() in ("transactions", "transaction") or "transaction" in name.lower():
            ws = wb[name]
            tx_rows = max(0, ws.max_row - 1)
        if "check" in name.lower():
            ws = wb[name]
            for row in ws.iter_rows(max_col=4):
                vals = [str(c.value) for c in row if c.value is not None]
                if vals: sc[row[0].row] = vals
    out["tx_rows"] = tx_rows
    out["formula_errors"] = errs[:10]
    out["check_sheet"] = {k: v for k, v in list(sc.items())[:30]}
    return out

def run_file(H, s8, do_confirm=True):
    rec = {"sha8": s8}
    code, resp = analyze(H, [s8])
    rec["analyze_http"] = code
    if code != 200:
        rec["fail_stage"] = "analyze"; rec["detail"] = resp; return rec
    docs = resp.get("documents") or []
    rec["analysis_id"] = resp.get("analysis_id")
    if not docs:
        rec["fail_stage"] = "no_docs"; return rec
    d = docs[0]
    rec["doc_state"] = d.get("state")
    rec["doc_detail"] = d.get("detail_state")
    rec["doc_msg_code"] = (d.get("message") or "")[:80]
    bank = d.get("bank") or d.get("suggestion") or {}
    rec["detected"] = {"id": bank.get("id"), "confidence": bank.get("confidence"), "tier": bank.get("tier")}
    rec["workflow"] = d.get("workflow_status")
    if not do_confirm or d.get("workflow_status") != "AWAITING_CONFIRMATION":
        return rec
    action = "OVERRIDE" if s8 in overrides else "CONFIRM"
    payload = {"documents": [{"document_id": d["document_id"], "action": action}]}
    if action == "OVERRIDE":
        payload["documents"][0]["bank_id"] = overrides[s8]
    r = requests.post(f"{API}/api/statements/{rec['analysis_id']}/confirm", headers=H, json=payload, timeout=30)
    rec["confirm_http"] = r.status_code
    try:
        cj = r.json()
        rec["confirm"] = cj.get("results") or cj
    except Exception:
        rec["confirm"] = r.text[:150]; return rec
    ok = any(x.get("ok") for x in rec["confirm"]) if isinstance(rec["confirm"], list) else True
    if not ok:
        return rec
    r = requests.post(f"{API}/api/statements/{rec['analysis_id']}/process", headers=H,
                      json={"document_ids": [d["document_id"]], "full_name": "V2 Verify"}, timeout=30)
    rec["process_http"] = r.status_code
    try:
        pj = r.json()
    except Exception:
        rec["process_resp"] = r.text[:150]; return rec
    started = pj.get("started") or []
    if not started:
        rec["skipped"] = pj.get("skipped"); return rec
    job = started[0]["job_id"]
    rec["job_id"] = job
    t0 = time.time()
    while time.time() - t0 < timeout:
        rj = requests.get(f"{API}/api/v1/jobs/{job}", headers=H, timeout=30)
        if rj.status_code == 401:
            H.update(login())
            rj = requests.get(f"{API}/api/v1/jobs/{job}", headers=H, timeout=30)
        j = rj.json()
        st = j.get("status")
        if st in ("completed", "failed"):
            rec["job_status"] = st
            rec["job_error"] = (j.get("error") or j.get("error_message") or "")[:120]
            rd = j.get("result_data") or {}
            rec["engine_meta"] = rd.get("statement_engine") or {}
            rec["stats_txn"] = (rd.get("stats") or {}).get("total_transactions")
            break
        time.sleep(4)
    else:
        rec["job_status"] = "timeout"; return rec
    if rec["job_status"] != "completed":
        return rec
    r = requests.get(f"{API}/api/v1/jobs/{job}/download", headers=H, timeout=60)
    rec["download_http"] = r.status_code
    if r.status_code == 200 and r.content[:2] == b"PK":
        dl = os.path.join(os.path.dirname(out_path), "dl")
        os.makedirs(dl, exist_ok=True)
        open(os.path.join(dl, s8 + ".xlsx"), "wb").write(r.content)
        try:
            rec["workbook"] = workbook_check(r.content)
        except Exception as e:
            rec["workbook_error"] = type(e).__name__
    else:
        rec["download_head"] = r.text[:80]
    return rec

out = open(out_path, "w", encoding="utf-8")
for s8 in sha8s:
    try:
        H = login()
        rec = run_file(H, s8)
    except Exception as e:
        rec = {"sha8": s8, "exception": type(e).__name__ + ":" + str(e)[:120]}
    out.write(json.dumps(rec) + "\n"); out.flush()
    print(s8, rec.get("doc_state"), rec.get("detected", {}).get("id"), rec.get("job_status"), rec.get("doc_msg_code"))
out.close()

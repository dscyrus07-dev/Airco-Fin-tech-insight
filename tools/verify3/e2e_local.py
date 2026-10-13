"""verify3: real-HTTP e2e for files outside the corpus manifest (synthetics).
Same flow as tools/verify2/e2e2.py: analyze -> confirm/override -> process -> poll -> download -> workbook checks.
usage: python tools/verify3/e2e_local.py <backend_dir> <out.jsonl> --files=/path/a.pdf,/path/b.pdf [--override=bank:filekey] [--timeout=240]
filekey = basename without extension. env: KC_SECRET, E2E_USER_PW."""
import json, os, sys, time, io
import requests

backend, out_path = sys.argv[1], sys.argv[2]
files, overrides, timeout = [], {}, 480
for a in sys.argv[3:]:
    if a.startswith("--files="):
        files = [f for f in a[8:].split(",") if f]
    elif a.startswith("--override="):
        b, _, s = a[11:].partition(":"); overrides[s] = b
    elif a.startswith("--timeout="):
        timeout = int(a[10:])

API = "http://127.0.0.1:8401"
KC = "http://localhost:8080"
SECRET = os.environ.get("KC_SECRET", "")
PW = os.environ.get("E2E_USER_PW", "Test123!")

def login():
    r = requests.post(f"{KC}/realms/airco-insights/protocol/openid-connect/token",
                      data={"grant_type": "password", "client_id": "frontend-app",
                            "client_secret": SECRET, "username": "test@airco.com", "password": PW}, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}

def workbook_check(buf):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(buf), data_only=False)
    errs, tx_rows, sc = [], 0, {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("#") and any(
                        e in c.value for e in ("REF", "VALUE", "DIV", "NAME", "N/A", "NULL", "NUM")):
                    errs.append(f"{ws.title}!{c.coordinate}")
    for name in wb.sheetnames:
        if "transaction" in name.lower():
            tx_rows = max(0, wb[name].max_row - 1)
        if "check" in name.lower():
            for row in wb[name].iter_rows(max_col=4):
                vals = [str(c.value) for c in row if c.value is not None]
                if vals: sc[row[0].row] = vals
    return {"sheets": wb.sheetnames, "tx_rows": tx_rows, "formula_errors": errs[:10],
            "check_sheet": dict(list(sc.items())[:30])}

def key(p):
    return os.path.splitext(os.path.basename(p))[0]

def run_file(H, p):
    rec = {"file": key(p)}
    code, resp = 0, {}
    try:
        up = [("files", (key(p) + ".pdf", open(p, "rb").read(), "application/pdf"))]
        r = requests.post(f"{API}/api/statements/analyze", headers=H, files=up, timeout=180)
        code, resp = r.status_code, (r.json() if "json" in r.headers.get("content-type", "") else r.text[:200])
    except Exception as e:
        rec["fail_stage"], rec["detail"] = "analyze", str(e)[:160]; return rec
    rec["analyze_http"] = code
    if code != 200:
        rec["fail_stage"], rec["detail"] = "analyze", str(resp)[:160]; return rec
    docs = resp.get("documents") or []
    rec["analysis_id"] = resp.get("analysis_id")
    if not docs:
        rec["fail_stage"] = "no_docs"; return rec
    d = docs[0]
    rec["doc_state"] = d.get("state")
    rec["doc_detail"] = d.get("detail_state")
    rec["doc_msg_code"] = (d.get("message") or "")[:100]
    bank = d.get("bank") or d.get("suggestion") or {}
    rec["detected"] = {"id": bank.get("id"), "name": bank.get("name"),
                       "confidence": bank.get("confidence"), "supported": bank.get("supported")}
    rec["workflow"] = d.get("workflow_status")
    if d.get("workflow_status") != "AWAITING_CONFIRMATION":
        return rec
    action = "OVERRIDE" if key(p) in overrides else "CONFIRM"
    payload = {"documents": [{"document_id": d["document_id"], "action": action}]}
    if action == "OVERRIDE":
        payload["documents"][0]["bank_id"] = overrides[key(p)]
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
                      json={"document_ids": [d["document_id"]], "full_name": "V3 Verify"}, timeout=30)
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
            H.update(login()); rj = requests.get(f"{API}/api/v1/jobs/{job}", headers=H, timeout=30)
        j = rj.json()
        st = j.get("status")
        if st in ("completed", "failed"):
            rec["job_status"] = st
            rec["job_error"] = (j.get("error") or j.get("error_message") or "")[:150]
            rd = j.get("result_data") or {}
            rec["engine_meta"] = rd.get("statement_engine") or {}
            rec["validation"] = rd.get("validation") or {}
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
        open(os.path.join(dl, key(p) + ".xlsx"), "wb").write(r.content)
        try:
            rec["workbook"] = workbook_check(r.content)
        except Exception as e:
            rec["workbook_error"] = str(e)[:120]
    return rec

H = login()
out = open(out_path, "a", encoding="utf-8")
for p in files:
    rec = run_file(H, p)
    out.write(json.dumps(rec) + "\n"); out.flush()
    print(rec["file"], rec.get("doc_state"), rec.get("detected"), rec.get("job_status"),
          (rec.get("engine_meta") or {}).get("verdict"), (rec.get("workbook") or {}).get("tx_rows"))
out.close()

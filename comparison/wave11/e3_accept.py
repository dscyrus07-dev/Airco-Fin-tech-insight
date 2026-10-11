# Wave11 E3: per-bank API acceptance on the w11 stack (port 8005).
# analyze -> confirm -> process -> poll -> statement_engine block + Excel.
import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error

API = "http://localhost:8005"
KC = "http://localhost:8080"
REALM = "airco-insights"
OUT = r"X:\Airco Projects\Airco Insights fintech\wt-w11\comparison\wave11"
PICKS = json.load(open(os.path.join(OUT, "e3_picks.json")))
ENV = {}
for line in open(r"X:\Airco Projects\Airco Insights fintech\wt-demo\local.env", encoding="utf-8"):
    m = re.match(r"^([A-Z_0-9]+)=(.*)$", line.strip())
    if m:
        ENV[m.group(1)] = m.group(2).strip().strip('"')
USER, PW = ENV.get("TEST_USER_EMAIL", "test@airco.com"), ENV.get("TEST_USER_PASSWORD") or "Test123!"
CLIENT = "frontend-app"


def token():
    body = urllib.parse.urlencode({
        "grant_type": "password", "client_id": CLIENT,
        "client_secret": ENV.get("KEYCLOAK_CLIENT_SECRET", ""),
        "username": USER, "password": PW, "scope": "openid"}).encode()
    req = urllib.request.Request(f"{KC}/realms/{REALM}/protocol/openid-connect/token",
                                 data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.load(urllib.request.urlopen(req))["access_token"]


TOK = [token(), time.time()]

def hdrs(multipart=False):
    if time.time() - TOK[1] > 240:
        TOK[0], TOK[1] = token(), time.time()
    h = {"Authorization": f"Bearer {TOK[0]}"}
    return h


def api(method, path, body=None, files=None, raw=False):
    url = API + path
    if files:
        import io, uuid
        bnd = uuid.uuid4().hex
        buf = io.BytesIO()
        for name, data, fn, ct in files:
            buf.write(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode())
            buf.write(data)
            buf.write(b"\r\n")
        buf.write(f"--{bnd}--\r\n".encode())
        req = urllib.request.Request(url, data=buf.getvalue(),
                                     headers={**hdrs(), "Content-Type": f"multipart/form-data; boundary={bnd}"})
    else:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={**hdrs(), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return (r.status, r.read() if raw else json.loads(r.read()))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": "unreadable"}


def flow(spec, rec):
    """full product flow for one pick; returns result dict"""
    p = rec["path"]
    pdf = open(p, "rb").read()
    st, an = api("POST", "/api/statements/analyze", files=[("files", pdf, os.path.basename(p), "application/pdf")])
    res = {"spec": spec, "sha": rec["sha"], "corpus_verdict": rec["verdict"], "analyze_status": st}
    if st != 200 or not an.get("documents"):
        res.update(outcome="analyze_fail", detail=str(an)[:300])
        return res
    doc = an["documents"][0]
    res["doc_state"] = doc.get("state")
    res["doc_bank"] = (doc.get("bank") or {}).get("id")
    aid = an["analysis_id"]; did = doc["document_id"]
    # confirm: use detected bank if supported, else override with the corpus spec id
    supported = (doc.get("bank") or {}).get("supported")
    action = {"document_id": did, "action": "CONFIRM"} if supported else \
             {"document_id": did, "action": "OVERRIDE", "bank_id": spec}
    st, cf = api("POST", f"/api/statements/{aid}/confirm", body={"documents": [action]})
    res["confirm_status"] = st
    if st != 200 or not (cf.get("results") or [{}])[0].get("ok"):
        res.update(outcome="confirm_fail", detail=str(cf)[:300])
        return res
    st, pr = api("POST", f"/api/statements/{aid}/process", body={"document_ids": [did]})
    if st != 200 or not pr.get("started"):
        res.update(outcome="process_fail", detail=str(pr)[:300])
        return res
    jid = pr["started"][0]["job_id"]
    res["job_id"] = jid
    for _ in range(90):
        time.sleep(4)
        st, js = api("GET", f"/api/jobs/{jid}")
        if st == 200 and js.get("status") in ("completed", "failed"):
            break
    res["job_status"] = js.get("status")
    rd = js.get("result_data") or {}
    res["statement_engine"] = rd.get("statement_engine")
    res["txns"] = ((rd.get("stats") or {}).get("total_transactions"))
    res["excel_url"] = rd.get("excel_url")
    res["hygiene"] = {k: (rd.get("progress") or {}).get("hygiene", {}).get(k)
                      for k in ("bank_name", "transaction_count", "start_date", "end_date")}
    if js.get("status") == "completed":
        st, xl = api("GET", f"/api/jobs/{jid}/download", raw=True)
        if st == 200:
            res["excel_bytes"] = len(xl)
            fn = os.path.join(OUT, "xlsx", f"{spec}_{rec['sha']}.xlsx")
            os.makedirs(os.path.dirname(fn), exist_ok=True)
            open(fn, "wb").write(xl)
            res["excel_path"] = fn
    res["outcome"] = "done"
    return res


if __name__ == "__main__":
    only = sys.argv[1:] or list(PICKS)
    log = open(os.path.join(OUT, "e3_results.jsonl"), "a", encoding="utf-8", buffering=1)
    for spec in only:
        for rec in PICKS[spec]:
            r = flow(spec, rec)
            print(json.dumps(r, default=str)[:600], flush=True)
            log.write(json.dumps(r, default=str) + "\n")
    log.close()

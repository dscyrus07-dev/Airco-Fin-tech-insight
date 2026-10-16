"""DP §2 tail: restart persistence + pypdf call-site exercises on rc."""
import json, os, sys, time, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "av"))
from probes import req, upload, wait_job, kc_token, rec, R

KIT = os.path.join(os.path.dirname(__file__), "..", "final", "demo_pdfs")


def upload_file(name, token=None, extra=None):
    pdf = open(os.path.join(KIT, name), "rb").read()
    return req("POST", "/api/upload/bank-statement-async", token=token,
               files={"file": (name, pdf)}, fields=extra or {"bank_name": "hdfc"})


def analyze(pdf_path, token=None, password=None):
    """Detection route — exercises pdfplumber/pikepdf+pypdf unlock."""
    pdf = open(pdf_path, "rb").read()
    name = os.path.basename(pdf_path)
    fields = {"passwords": json.dumps({name: password})} if password is not None else {}
    s, j = req("POST", "/api/statements/analyze", token=token,
               files={"files": (name, pdf)}, fields=fields)
    doc = ((j or {}).get("documents") or [{}])[0]
    return s, j, doc


def main():
    tokA = kc_token(os.environ["TEST_USER_EMAIL"], os.environ["TEST_USER_PASSWORD"])

    FAST = "analyze" in sys.argv
    # --- restart persistence (waits through boot) ---
    import urllib.request
    if not FAST:
        r = urllib.request.Request("http://localhost:3600/api/jobs/923a4214-903f-49cd-ad41-e1fd006ea527",
                                   headers={"Authorization": f"Bearer {tokA}"})
        tkX = json.loads(urllib.request.urlopen(r, timeout=30).read())["result_data"]["download_token"]
        subprocess.run(["docker", "restart", "rc_backend"], capture_output=True)
        up = False
        for _ in range(60):
            time.sleep(2)
            try:
                s, _ = req("GET", "/health")
                if s == 200:
                    up = True
                    break
            except Exception:
                pass
        rec("backend back after restart", True, up)
        time.sleep(3)
        s, _ = req("GET", "/api/jobs/923a4214-903f-49cd-ad41-e1fd006ea527?t=" + tkX)
        rec("token survives restart", 200, s)

    # --- pypdf 6.x call-site exercises (analyze route = detection path) ---
    import os.path as P
    LOCKED = P.join(KIT, "demo_locked_hdfc.pdf")
    # locked, right password -> pypdf 6.x decrypt path works
    s, j, d = analyze(LOCKED, token=tokA, password="demo1234")
    rec("locked pdf right password (analyze)",
        lambda a: a == 200 and not d.get("requires_password"), s,
        extra={"state": d.get("state"), "detail": d.get("detail_state")})
    # locked, wrong password -> honest password-required/failed, not a crash
    s, j, d = analyze(LOCKED, token=tokA, password="wrongpass9")
    rec("locked pdf wrong password (analyze)",
        lambda a: a == 200 and (d.get("requires_password") or "PASSWORD" in str(d.get("detail_state"))), s,
        extra={"state": d.get("state"), "detail": d.get("detail_state")})
    # locked, no password
    s, j, d = analyze(LOCKED, token=tokA)
    rec("locked pdf no password -> PASSWORD_REQUIRED",
        lambda a: a == 200 and (d.get("requires_password") or "PASSWORD" in str(d.get("detail_state"))), s,
        extra={"state": d.get("state"), "detail": d.get("detail_state")})
    # scanned -> honest capability/state, no crash
    s, j, d = analyze(P.join(KIT, "demo_scanned.pdf"), token=tokA)
    rec("scanned pdf (analyze)", lambda a: a == 200, s,
        extra={"state": d.get("state"), "capability": (d.get("capability") or {}).get("capability")})
    # truncated -> honest fail state, no 500
    s, j, d = analyze(P.join(KIT, "demo_truncated_canara.pdf"), token=tokA)
    rec("truncated pdf (analyze)", lambda a: a != 500, s,
        extra={"state": d.get("state"), "detail": d.get("detail_state")})

    # --- one unified flow end-to-end: upload -> process -> ?t= download ---
    if not FAST:
        s, upx = upload(token=tokA)
        jx = upx["job_id"]
        s, j = wait_job(jx, token=tokA)
        rec("e2e job completes", 200, s, extra={"status": j.get("status")})
        if str(j.get("status", "")).lower() == "completed":
            tk = (j.get("result_data") or {}).get("download_token")
            s, b = req("GET", f"/api/jobs/{jx}/download?t={tk}", raw=True)
            rec("e2e workbook download via ?t=", 200, s, extra={"bytes": len(b) if isinstance(b, bytes) else 0})

    fails = [r["probe"] for r in R if not r["PASS"]]
    print(f"\n{len(R) - len(fails)}/{len(R)} PASS" + (f" FAILS: {fails}" if fails else ""))
    json.dump(R, open(os.path.join(os.path.dirname(__file__), ".local", "dp_checks.json"), "w"), indent=2)


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), ".local"), exist_ok=True)
    main()

"""N8 robustness: time async process of largest corpus PDFs; log job status +
elapsed only (no content). Usage: python big_run.py"""
import json, time, requests, subprocess, sys

API = "http://127.0.0.1:8401"
BASE = r"X:\Airco Projects\Airco Insights fintech\Unified All Statements"
FILES = [
 ("474ff6d2", "Paytm Bank", BASE + r"\Paytm Payments Bank\3044583_Account_St_1700458861694.pdf"),
 ("1203ecf7", "ICICI Bank", BASE + r"\ICICI Bank\3106733_Statement__1737990592715.pdf"),
 ("b3724368", "Citibank",   BASE + r"\Citibank\431202_CitibankA_1713202378927.pdf"),
 ("a6aebcf5", "Paytm Bank", BASE + r"\Paytm Payments Bank\28636_Account_St_1699609539953.pdf"),
 ("400b9d03", "Kotak Bank", BASE + r"\Kotak Mahindra Bank\2602009_caaf040a-8_1745572458785.pdf"),
]
out = open("tools/n8/.local/big_run.jsonl", "a", encoding="utf-8")

def mem_mb():
    try:
        r = subprocess.run(["docker","stats","--no-stream","--format","{{.MemUsage}}","onb_backend"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception:
        return "?"

for s8, bank, p in FILES:
    t0 = time.time()
    try:
        resp = requests.post(f"{API}/api/upload/bank-statement-async",
            files={"file": (s8 + ".pdf", open(p, "rb").read(), "application/pdf")},
            data={"bank_name": bank, "full_name": "N8 Rob", "account_type": "savings", "mode": "free"},
            timeout=60)
        job = resp.json().get("job_id")
    except Exception as e:
        out.write(json.dumps({"sha8": s8, "stage": "submit", "err": type(e).__name__}) + "\n"); out.flush(); continue
    peak, status, err = 0.0, "?", None
    while time.time() - t0 < 900:
        m = mem_mb()
        try:
            head = m.split("/")[0].strip()
            used = float(head.replace("MiB","").replace("GiB","").split()[0])
            if "GiB" in head: used *= 1024
            peak = max(peak, used)
        except Exception: pass
        try:
            j = requests.get(f"{API}/api/jobs/{job}", timeout=20).json()
            status = j.get("status"); err = j.get("error_message")
            if status in ("completed", "failed"): break
        except Exception: pass
        time.sleep(3)
    out.write(json.dumps({"sha8": s8, "job8": job[:8], "status": status,
                          "sec": round(time.time()-t0,1), "err": (err or "")[:120],
                          "mem_peak_mib": round(peak)} ) + "\n")
    out.flush()
out.close()

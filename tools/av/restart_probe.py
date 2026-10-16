"""Token-survives-restart probe (DOWNLOAD_TOKEN_SECRET set on rc)."""
import json, os, sys, time, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from probes import req, kc_token, rec, R, OUT

tokA = kc_token(os.environ["TEST_USER_EMAIL"], os.environ["TEST_USER_PASSWORD"])
s, jobs = req("GET", "/api/jobs/", token=tokA)
job = next((j for j in jobs if str(j.get("status", "")).lower() == "completed"), None)
assert job, "no completed job"
jid = job["job_id"] if "job_id" in job else job["id"]
tok = subprocess.run(["docker", "exec", "rc_backend", "python", "-c",
                      f"from app.services.download_tokens import issue_download_token;print(issue_download_token('{jid}'))"],
                     capture_output=True, text=True).stdout.strip()
print("minted for", jid)
subprocess.run(["docker", "restart", "rc_backend"], capture_output=True)
ok = False
for _ in range(60):
    time.sleep(2)
    try:
        s, _ = req("GET", "/health")
        if s == 200:
            ok = True
            break
    except Exception:
        pass
print("backend back:", ok)
time.sleep(3)
s, _ = req("GET", f"/api/jobs/{jid}?t={tok}")
rec("token survives backend restart", 200, s)
json.dump(R, open(OUT.replace("probe_results", "restart_result"), "w"), indent=2)

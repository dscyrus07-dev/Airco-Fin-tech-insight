"""AV §2 tail: anonymous download_token flow + token-survives-restart."""
import json, os, sys, time, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from probes import req, upload, wait_job, kc_token, rec, R, OUT


def main():
    # anonymous upload -> token in response -> poll + download with ?t=
    s, upa = upload()
    rec("anon upload 200", 200, s, extra={"has_tok": bool(upa.get("download_token"))})
    atok, ajid = upa.get("download_token"), upa.get("job_id")
    s, j = wait_job(ajid, t=atok)
    rec("anon poll via ?t=", 200, s, extra={"status": j.get("status")})
    if str(j.get("status", "")).lower() == "completed":
        s, _ = req("GET", f"/api/jobs/{ajid}/download?t={atok}")
        rec("anon download via ?t=", 200, s)
    s, _ = req("GET", f"/api/jobs/{ajid}")
    rec("anon job no-auth still 401", 401, s)

    # restart persistence: mint token for a fresh A job, restart, reuse
    tokA = kc_token(os.environ["TEST_USER_EMAIL"], os.environ["TEST_USER_PASSWORD"])
    s, up = upload(token=tokA)
    jid = up["job_id"]
    s, j = wait_job(jid, token=tokA)
    tok = (j.get("result_data") or {}).get("download_token")
    rec("completed job issues token", bool, bool(tok))
    subprocess.run(["docker", "restart", "rc_backend"], capture_output=True)
    for _ in range(45):
        time.sleep(2)
        s, _ = req("GET", "/health")
        if s == 200:
            break
    time.sleep(3)
    s, _ = req("GET", f"/api/jobs/{jid}?t={tok}")
    rec("token survives backend restart", 200, s)

    json.dump(R, open(OUT.replace("probe_results", "probe_tail_results"), "w"), indent=2)
    fails = [r["probe"] for r in R if not r["PASS"]]
    print(f"\n{len(R) - len(fails)}/{len(R)} PASS" + (f" FAILS: {fails}" if fails else ""))


if __name__ == "__main__":
    main()

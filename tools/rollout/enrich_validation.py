"""rollout: back-fill validation.* into e2e2 records.

e2e2.py reads result_data while the job row can still be mid-persist;
validation (reconciliation_passed / integrity_passed) lands after. This
re-queries each record's job_id and stores rd["validation"] + the
statement_engine block keys + sheet names for the rollout comparisons.

usage: python tools/rollout/enrich_validation.py <record.jsonl> [...]
"""
import json, os, sys
import requests

API = "http://127.0.0.1:8401"
KC = "http://localhost:8080"


def token():
    r = requests.post(
        f"{KC}/realms/airco-insights/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "frontend-app",
            "client_secret": "",
            "username": "test@airco.com",
            "password": "Test123!",
        },
    )
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def main(paths):
    h = token()
    for path in paths:
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        changed = False
        for r in rows:
            jid = r.get("job_id")
            if not jid or r.get("job_status") != "completed":
                continue
            j = None
            for _ in range(4):
                try:
                    j = requests.get(f"{API}/api/v1/jobs/{jid}", headers=h, timeout=90).json()
                    break
                except requests.RequestException:
                    pass
            if j is None:
                continue
            rd = j.get("result_data") or {}
            r["validation"] = rd.get("validation")
            se = rd.get("statement_engine") or {}
            em = r.get("engine_meta") or {}
            for k in ("engine", "mode", "verdict", "needs_review", "review_codes"):
                em.setdefault(k, se.get(k))
            r["engine_meta"] = em
            r["se_block_json"] = json.dumps(se, sort_keys=True)
            changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
        print(path, len(rows), "records")


if __name__ == "__main__":
    main(sys.argv[1:])

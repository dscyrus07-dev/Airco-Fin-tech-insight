"""AV §2 attack probes against the rc stack (synthetic PDFs only).

Every probe asserts an expected HTTP status/body property. Results are written
to tools/av/.local/probe_results.json. No statement content is printed; only
job ids, statuses and booleans.
"""
import json, os, sys, time, urllib.request, urllib.error, uuid

API = "http://localhost:8601"
KC = "http://localhost:8080"
REALM = "airco-insights"
CLIENT = "frontend-app"
DEMO = os.path.join(os.path.dirname(__file__), "..", "final", "demo_pdfs", "demo_hdfc.pdf")
OUT = os.path.join(os.path.dirname(__file__), ".local", "probe_results.json")

R = []


def rec(name, expected, actual, extra=None):
    ok = actual == expected if not callable(expected) else expected(actual)
    R.append({"probe": name, "expected": expected if not callable(expected) else "predicate", "actual": actual, "PASS": bool(ok), **({"extra": extra} if extra else {})})
    print(f"{'PASS' if ok else 'FAIL'} {name}: expected={expected if not callable(expected) else 'pred'} actual={actual}")


def req(method, path, token=None, headers=None, body=None, files=None, fields=None, raw=False):
    url = API + path
    h = dict(headers or {})
    data = None
    if files:  # multipart
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in files.items():
            fn, content = v
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: application/pdf\r\n\r\n".encode() + content + b"\r\n")
        for k, v in (fields or {}).items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        data = b"".join(parts) + f"--{boundary}--\r\n".encode()
        h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            b = resp.read()
            return resp.status, b if raw else _j(b)
    except urllib.error.HTTPError as e:
        b = e.read()
        return e.code, b if raw else _j(b)


def _j(b):
    try:
        return json.loads(b.decode())
    except Exception:
        return {"_raw": b[:120].decode(errors="replace")}


_SECRET = None

def _client_secret():
    global _SECRET
    if _SECRET:
        return _SECRET
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
                                   "username": os.environ["KEYCLOAK_ADMIN"],
                                   "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"]}).encode()
    at = json.loads(urllib.request.urlopen(
        urllib.request.Request(f"{KC}/realms/master/protocol/openid-connect/token", data=data),
        timeout=30).read())["access_token"]
    r = urllib.request.Request(f"{KC}/admin/realms/{REALM}/clients?clientId={CLIENT}",
                               headers={"Authorization": f"Bearer {at}"})
    cid = json.loads(urllib.request.urlopen(r, timeout=30).read())[0]["id"]
    r2 = urllib.request.Request(f"{KC}/admin/realms/{REALM}/clients/{cid}/client-secret",
                                headers={"Authorization": f"Bearer {at}"})
    _SECRET = json.loads(urllib.request.urlopen(r2, timeout=30).read())["value"]
    return _SECRET


def kc_token(user, pw):
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": CLIENT,
                                   "client_secret": _client_secret(),
                                   "username": user, "password": pw}).encode()
    r = urllib.request.Request(f"{KC}/realms/{REALM}/protocol/openid-connect/token",
                               data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


def upload(token=None, headers=None):
    pdf = open(DEMO, "rb").read()
    return req("POST", "/api/upload/bank-statement-async", token=token, headers=headers,
               files={"file": ("demo_hdfc.pdf", pdf)}, fields={"bank_name": "hdfc"})


def wait_job(job_id, token=None, t=None, timeout=240):
    q = f"?t={t}" if t else ""
    end = time.time() + timeout
    s, j = 0, {}
    while time.time() < end:
        s, j = req("GET", f"/api/jobs/{job_id}{q}", token=token)
        if s == 200 and str(j.get("status", "")).lower() in ("completed", "failed"):
            return s, j
        time.sleep(4)
    return s, j


import urllib.parse

def main():
    u1, p1 = os.environ["TEST_USER_EMAIL"], os.environ["TEST_USER_PASSWORD"]
    u2, p2 = os.environ.get("TEST_USER2_EMAIL", "n9test2@airco.com"), os.environ.get("TEST_USER2_PASSWORD", "N9Test!234")
    tokA = kc_token(u1, p1)
    tokB = kc_token(u2, p2)
    import base64
    aid = json.loads(base64.urlsafe_b64decode(tokA.split(".")[1] + "=="))["sub"]

    # --- setup jobs ---
    s, up = upload(token=tokA)
    assert s == 200, up
    jobX = up["job_id"]
    s, jx = wait_job(jobX, token=tokA)
    assert jx.get("status", "").lower() == "completed", jx.get("status")
    dtX = (jx.get("result_data") or {}).get("download_token")
    s, up2 = upload(token=tokA)
    jobY = up2["job_id"]; wait_job(jobY, token=tokA)

    # --- 1. no auth -> 401 on all four surfaces ---
    for p, path in [("jobs/{id}", f"/api/jobs/{jobX}"),
                    ("jobs/{id}/download", f"/api/jobs/{jobX}/download"),
                    ("upload/download/{id}", f"/api/upload/download/{jobX}")]:
        s, _ = req("GET", path)
        rec(f"noauth {p}", 401, s)
    # /download/{file}: need a real JOB_-prefixed name in /app/tmp
    import subprocess
    names = subprocess.run(["docker", "exec", "rc_backend", "ls", "/app/tmp"],
                           capture_output=True, text=True).stdout.split()
    jobfiles = [n for n in names if n.startswith("JOB")]
    nonjob = [n for n in names if not n.startswith("JOB") and n.endswith((".xlsx", ".pdf"))]
    fX = next((n for n in jobfiles if jobX.split("-")[0].upper().replace("JOB", "") in n or jobX in n or jobX.upper().replace("-", "") in n.replace("-", "")), None)
    print("tmp jobfiles:", jobfiles[:5], "nonjob:", nonjob[:3])
    if fX:
        s, _ = req("GET", f"/download/{fX}")
        rec("noauth /download/{JOBfile}", 401, s)

    # --- 2. user B bearer on A's job -> 403 ---
    s, _ = req("GET", f"/api/jobs/{jobX}", token=tokB)
    rec("userB GET job X", 403, s)
    s, _ = req("GET", f"/api/jobs/{jobX}/download", token=tokB)
    rec("userB download job X", 403, s)
    s, _ = req("GET", f"/api/upload/download/{jobX}", token=tokB)
    rec("userB /api/upload/download X", 403, s)

    # --- 3. admin bearer -> 200 ---
    tokadm = kc_token("avadmin@airco.com", "AvTest!234")
    if tokadm:
        s, _ = req("GET", f"/api/jobs/{jobX}", token=tokadm)
        rec("admin GET job X", 200, s)
    else:
        rec("admin GET job X", 200, "SKIP-no-admin")

    # --- 4. header spoof ---
    sp = {"X-Airco-User-Id": aid, "X-Airco-User-Email": u1}
    s, j = req("GET", "/api/profile/history", headers=sp)
    rec("spoof X-Airco-User-Id /api/profile/history", lambda a: a in (401, 403) or (isinstance(a, int) and a == 200 and False), s,
        extra={"leaksA": bool(isinstance(j, dict) and aid in json.dumps(j))})
    s, j = req("DELETE", f"/api/profile/files/{jobX}", headers=sp)
    rec("spoof DELETE /api/profile/files/{id}", lambda a: a in (401, 403, 404, 405), s)
    s, j = upload(headers=sp)
    rec("spoof upload w/o bearer", 200, s, extra={"job_user": "anonymous-or-none" if s == 200 else None})
    if s == 200:
        anon_job = j.get("job_id")
        s2, j2 = req("GET", f"/api/jobs/{anon_job}", token=tokB)  # B shouldn't see anon job either
        rec("anon job not readable by userB", 403, s2)
        # confirm it isn't owned by A: A's list should not gain it? check owner field via token-less? record:
        s3, j3 = req("GET", f"/api/jobs/{anon_job}", token=tokA)
        rec("anon job GET by A", lambda a: a in (200, 403), s3, extra={"owner": j3.get("user_id") if isinstance(j3, dict) else None})

    # --- 5. token scoping ---
    s, _ = req("GET", f"/api/jobs/{jobY}?t={dtX}")
    rec("token(X) on job Y", lambda a: a == 401, s)
    # tampered signature
    tamp = dtX[:-2] + ("aa" if not dtX.endswith("aa") else "bb")
    s, _ = req("GET", f"/api/jobs/{jobX}?t={tamp}")
    rec("tampered signature", 401, s)
    # tampered expiry (re-sign impossible -> 401)
    parts = dtX.split(".")
    texp = f"{parts[0]}.{int(parts[1]) + 99999}.{parts[2]}"
    s, _ = req("GET", f"/api/jobs/{jobX}?t={texp}")
    rec("tampered expiry", 401, s)
    # expired token minted in-container (same secret)
    exp = subprocess.run(["docker", "exec", "rc_backend", "python", "-c",
                          f"from app.services.download_tokens import issue_download_token;print(issue_download_token('{jobX}',-60))"],
                         capture_output=True, text=True).stdout.strip()
    s, _ = req("GET", f"/api/jobs/{jobX}?t={exp}")
    rec("expired token", 401, s)

    # --- 6. /download/{file} variants ---
    if fX:
        s, _ = req("GET", f"/download/{fX}", token=tokB)
        rec("userB /download/{A's JOBfile}", lambda a: a in (401, 403), s)
        if jobfiles and len(jobfiles) > 1:
            other = next(n for n in jobfiles if n != fX)
            s, _ = req("GET", f"/download/{other}?t={dtX}")
            rec("token(X) on other JOB file", lambda a: a in (401, 403), s)
        s, b = req("GET", f"/download/{fX}?t={dtX}", raw=True)
        rec("owner token /download/{JOBfile}", 200, s)
        s, _ = req("GET", f"/download/{fX}", token=tokA)
        rec("owner bearer /download/{JOBfile}", 200, s)
        if tokadm:
            s, _ = req("GET", f"/download/{fX}", token=tokadm)
            rec("admin /download/{JOBfile}", 200, s)
    if nonjob:
        s, _ = req("GET", f"/download/{nonjob[0]}", token=tokA)
        rec("non-admin /download/{non-JOB file}", lambda a: a in (401, 403), s)
        if tokadm:
            s, _ = req("GET", f"/download/{nonjob[0]}", token=tokadm)
            rec("admin /download/{non-JOB file}", 200, s)
    # traversal
    s, _ = req("GET", "/download/..%2F..%2Fetc%2Fpasswd", token=tokA)
    rec("path traversal", lambda a: a in (400, 401, 403, 404), s)
    s, _ = req("GET", "/download/..%2F..%2Fetc%2Fpasswd")
    rec("path traversal anon", lambda a: a in (400, 401, 403, 404), s)

    # --- 7. anonymous upload -> download_token flow ---
    s, upa = upload()
    rec("anonymous upload returns token", 200, s, extra={"has_tok": bool(upa.get("download_token"))})
    anon_tok = upa.get("download_token")
    anon_job = upa["job_id"]
    s, j = wait_job(anon_job, t=anon_tok)
    rec("anon job poll via ?t=", 200, s)
    if j.get("status", "").lower() == "completed":
        s, _ = req("GET", f"/api/jobs/{anon_job}/download?t={anon_tok}")
        rec("anon job download via ?t=", 200, s)
    s, _ = req("GET", f"/api/jobs/{anon_job}")  # no token still 401
    rec("anon job no-auth", 401, s)

    # --- 8. restart persistence ---
    # mint a token inside the container (download_token lives only in the
    # Next-proxy response, not in the backend's stored result_data)
    mint = subprocess.run(
        ["docker", "exec", "rc_backend", "python", "-c",
         f"from app.services.download_tokens import issue_download_token; print(issue_download_token('{jobX}'))"],
        capture_output=True, text=True)
    tok_persist = mint.stdout.strip()
    subprocess.run(["docker", "restart", "rc_backend"], capture_output=True)
    time.sleep(3)
    for _ in range(45):
        try:
            s, _ = req("GET", "/health")
            if s == 200:
                break
        except Exception:
            pass
        time.sleep(2)
    s, _ = req("GET", f"/api/jobs/{jobX}?t={tok_persist}")
    rec("token survives backend restart (secret set)", 200, s)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(R, open(OUT, "w"), indent=2)
    fails = [r["probe"] for r in R if not r["PASS"]]
    print(f"\n{len(R) - len(fails)}/{len(R)} PASS" + (f" FAILS: {fails}" if fails else ""))


if __name__ == "__main__":
    main()

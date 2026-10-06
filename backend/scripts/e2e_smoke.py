r"""End-to-end smoke test: upload -> backend job -> result with verification -> Excel download.

Stdlib only. Talks to the RUNNING stack over HTTP (the same endpoints the UI uses):
  POST /api/upload/bank-statement-async   -> job_id
  GET  /api/jobs/{job_id}                 -> status + result_data (frontend result)
  GET  /api/jobs/{job_id}/download        -> Excel

Checks:
  1. job reaches COMPLETED
  2. result_data carries the additive `verification` block (state, 6 checks, raw counts)
  3. verification raw counts agree with the stats the UI shows
  4. the Excel downloads and is a valid .xlsx (zip) with 9 sheets
Exit code 0 only if every check passes. Writes a JSON report next to --out.

    python scripts/e2e_smoke.py --api http://host.docker.internal:8000 --pdf /samples/HDFC\ Bank/x.pdf --bank hdfc
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _multipart(fields: Dict[str, str], file_field: str, filename: str, data: bytes) -> Tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()
    for k, v in fields.items():
        buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    buf.write(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: application/pdf\r\n\r\n"
        ).encode()
    )
    buf.write(data)
    buf.write(f"\r\n--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def _req(method: str, url: str, headers: Optional[Dict[str, str]] = None, body: Optional[bytes] = None, timeout: int = 60):
    r = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def _token(keycloak: str, realm: str, client: str, user: str, pw: str) -> Optional[str]:
    url = f"{keycloak}/realms/{realm}/protocol/openid-connect/token"
    body = urllib.parse.urlencode(
        {"grant_type": "password", "client_id": client, "username": user, "password": pw}
    ).encode()
    status, raw, _ = _req("POST", url, {"Content-Type": "application/x-www-form-urlencoded"}, body)
    if status == 200:
        return json.loads(raw).get("access_token")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--bank", required=True, help="bank name as the UI sends it, e.g. hdfc")
    ap.add_argument("--mode", default="free")
    ap.add_argument("--password", default="", help="PDF password if locked")
    ap.add_argument("--keycloak", default="")
    ap.add_argument("--realm", default="airco-insights")
    ap.add_argument("--client", default="frontend-app")
    ap.add_argument("--user", default="")
    ap.add_argument("--pass", dest="pw", default="")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    report: Dict[str, Any] = {"pdf": a.pdf, "bank": a.bank, "checks": {}}
    ok_all = True

    def check(name: str, ok: bool, detail: Any = "") -> None:
        nonlocal ok_all
        report["checks"][name] = {"ok": bool(ok), "detail": detail}
        ok_all &= bool(ok)
        print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail != "" else ""))

    headers: Dict[str, str] = {}
    if a.keycloak and a.user:
        tok = _token(a.keycloak, a.realm, a.client, a.user, a.pw)
        report["authenticated"] = bool(tok)
        print("auth:", "token obtained" if tok else "token NOT obtained (continuing unauthenticated)")
        if tok:
            headers["Authorization"] = f"Bearer {tok}"

    data = Path(a.pdf).read_bytes()
    fields = {"bank_name": a.bank, "mode": a.mode, "full_name": "E2E Smoke", "account_type": "savings"}
    if a.password:
        fields["pdf_password"] = a.password
    body, ctype = _multipart(fields, "file", Path(a.pdf).name, data)
    status, raw, _ = _req("POST", f"{a.api}/api/upload/bank-statement-async", {**headers, "Content-Type": ctype}, body, 120)
    check("upload_accepted", status == 200, f"HTTP {status} {raw[:200].decode(errors='replace') if status != 200 else ''}")
    if status != 200:
        _finish(report, a.out)
        return 1
    job_id = json.loads(raw)["job_id"]
    report["job_id"] = job_id

    job: Dict[str, Any] = {}
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        st, raw, _ = _req("GET", f"{a.api}/api/jobs/{job_id}", headers)
        if st == 200:
            job = json.loads(raw)
            if str(job.get("status", "")).lower() in ("completed", "failed", "cancelled"):
                break
        time.sleep(2)
    check("job_completed", str(job.get("status", "")).lower() == "completed", f"status={job.get('status')} error={job.get('error_message')}")
    result = job.get("result_data") or {}
    report["result_keys"] = sorted(result.keys())

    v = result.get("verification")
    check("verification_block_present", isinstance(v, dict), "missing: backend image is old or result builder dropped it" if not isinstance(v, dict) else v.get("state"))
    if isinstance(v, dict):
        check("verification_observe_only_v1", v.get("version") == "v1" and v.get("observe_only") is True)
        check(
            "verification_has_all_six_checks",
            set(v.get("checks", {})) == {"schema_check", "balance_check", "opening_closing_check", "printed_totals_check", "duplicate_check", "header_period_check"},
        )
        check(
            "verification_non_verified_is_explained",
            v.get("state") == "VERIFIED" or bool(v.get("reasons")),
            f"state={v.get('state')} class={v.get('failure_class')} reasons={v.get('reasons')}",
        )
        report["verification"] = {k: v.get(k) for k in ("state", "failures", "reasons", "notes", "failure_class", "repair_masks_balance_failure", "raw_transaction_count", "raw_debit_count", "raw_credit_count", "repairs")}
        stats = result.get("stats") or {}
        shown = stats.get("total_transactions") or stats.get("transaction_count")
        if shown is not None:
            # The UI count is after the validator step; raw may be >= shown. Record both; raw < shown would be a bug.
            check("raw_count_not_below_ui_count", v["raw_transaction_count"] >= int(shown), f"raw={v['raw_transaction_count']} ui={shown}")
        report["ui_stats"] = stats

    st, raw, hdrs = _req("GET", f"{a.api}/api/jobs/{job_id}/download", headers, timeout=120)
    xlsx_ok = False
    sheets = None
    if st == 200 and raw[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
                sheets = len(names)
                xlsx_ok = sheets > 0
        except zipfile.BadZipFile:
            pass
    check("excel_downloads_and_opens", xlsx_ok, f"HTTP {st}, {len(raw)} bytes, sheets={sheets}")
    check("excel_has_9_sheets_unchanged", sheets == 9, f"sheets={sheets}")

    _finish(report, a.out)
    return 0 if ok_all else 1


def _finish(report: Dict[str, Any], out: str) -> None:
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("RESULT:", "ALL PASS" if all(c["ok"] for c in report["checks"].values()) else "FAILURES")


if __name__ == "__main__":
    sys.exit(main())

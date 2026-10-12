# Wave11 E3 probes. Mutation: first-row amount +1 re-fed to the v2 checks
# (read-only engine calls; no engine code changed) must not stay VERIFIED.
# Wrong-bank: a file of spec X submitted as bank Y must never be VERIFIED.
import dataclasses, json, os, sys
from decimal import Decimal

sys.path.insert(0, r"X:\Airco Projects\Airco Insights fintech\wt-w11\backend")
sys.path.insert(0, r"X:\Airco Projects\Airco Insights fintech\wt-w11\comparison\wave11")
import e3_accept as e
from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as REG
from app.services.statement_engine.extraction.checks import run_checks

OUT = r"X:\Airco Projects\Airco Insights fintech\wt-w11\comparison\wave11"
PICKS = e.PICKS
ELIGIBLE = list(PICKS)


def mutation_probe(spec: str) -> dict:
    from app.services.statement_engine.extraction.pdf_extractor import read_pages
    from app.services.statement_engine.extraction.engine import extract_pages
    rec = next((r for r in PICKS[spec] if r["verdict"] == "VERIFIED" and r.get("path")), PICKS[spec][0])
    routed = route_pdf(rec["path"], REG)
    if routed.status != "v2" or not routed.layout_id:
        return {"spec": spec, "probe": "mutation", "result": "skipped_no_v2", "sha": rec["sha"]}
    spec_obj = REG.get(routed.layout_id)
    pages = read_pages(rec["path"], None)
    out = extract_pages(pages, spec_obj)
    if not out.rows:
        return {"spec": spec, "probe": "mutation", "result": "skipped_no_rows", "sha": rec["sha"]}
    base = out.checks.verdict if out.checks else None
    rows = list(out.rows)
    t0 = rows[0].txn
    # first-row amount +1 on whichever side is printed
    bumped = dataclasses.replace(
        t0,
        debit=(t0.debit + Decimal(1)) if t0.debit is not None else t0.debit,
        credit=(t0.credit + Decimal(1)) if t0.credit is not None and t0.debit is None else t0.credit,
    )
    rows[0] = dataclasses.replace(rows[0], txn=bumped)
    chk = run_checks(rows, out.period, out.summary, out.schema_errors, out.warnings,
                     spec_obj.period_date_format, spec_obj.summary_expected,
                     spec_obj.dates_monotonic_expected, spec_obj.period_tolerance_days,
                     spec_obj.side_flip_policy)
    return {"spec": spec, "probe": "mutation", "sha": rec["sha"],
            "baseline_verdict": base, "mutated_verdict": chk.verdict,
            "chain": chk.results["chain"].status, "reference": chk.results["reference"].status,
            "totals": chk.results["totals"].status,
            "blocked_verified": chk.verdict != "VERIFIED"}


def wrong_bank_probe(spec: str) -> dict:
    """First pick of `spec` force-OVERRIDDEN as another bank through the live API."""
    other = "hdfc" if spec != "hdfc" else "sbi"
    rec = PICKS[spec][0]
    pdf = open(rec["path"], "rb").read()
    st, an = e.api("POST", "/api/statements/analyze",
                   files=[("files", pdf, "x.pdf", "application/pdf")])
    out = {"spec": spec, "probe": "wrong_bank", "as_bank": other, "sha": rec["sha"]}
    if st != 200 or not an.get("documents"):
        out.update(safe=None, outcome="analyze_fail", detail=str(an)[:120])
        return out
    doc = an["documents"][0]
    aid, did = an["analysis_id"], doc["document_id"]
    st, cf = e.api("POST", f"/api/statements/{aid}/confirm",
                   body={"documents": [{"document_id": did, "action": "OVERRIDE", "bank_id": other}]})
    if st != 200 or not (cf.get("results") or [{}])[0].get("ok"):
        out.update(safe=True, outcome="refused_at_confirm", detail=str(cf)[:120])
        return out
    st, pr = e.api("POST", f"/api/statements/{aid}/process", body={"document_ids": [did]})
    if st != 200 or not pr.get("started"):
        out.update(safe=True, outcome="refused_at_process", detail=str(pr)[:120])
        return out
    jid = pr["started"][0]["job_id"]
    js = {}
    import time
    for _ in range(90):
        time.sleep(4)
        st, js = e.api("GET", f"/api/jobs/{jid}")
        if st == 200 and js.get("status") in ("completed", "failed"):
            break
    rd = js.get("result_data") or {}
    se = rd.get("statement_engine") or {}
    verdict = se.get("verdict")
    codes = (se.get("review_codes") or []) + ((se.get("advisory") or {}).get("review_codes") or [])
    safe = verdict != "VERIFIED"
    out.update(safe=safe, outcome="done", job_status=js.get("status"), engine=se.get("engine"),
               verdict=verdict, codes=codes,
               mismatch_flag="BANK_MISMATCH" in codes,
               detail=str(rd.get("error") or "")[:120])
    return out


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "all"
    log = open(os.path.join(OUT, "e3_probe_results.jsonl"), "a", encoding="utf-8", buffering=1)
    fns = {"mutation": (mutation_probe,), "wrong": (wrong_bank_probe,), "all": (mutation_probe, wrong_bank_probe)}[kind]
    for spec in (sys.argv[2:] or ELIGIBLE):
        for fn in fns:
            r = fn(spec)
            print(json.dumps(r, default=str), flush=True)
            log.write(json.dumps(r, default=str) + "\n")
    log.close()

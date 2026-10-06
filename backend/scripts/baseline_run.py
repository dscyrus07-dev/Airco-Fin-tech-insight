"""Baseline run for verification v1 (observe-only).

Answers one question: how reliable is the CURRENT parser output?

For every sample PDF it runs pipeline steps 1-4 of the existing bank processor
(integrity -> structure -> parse -> transaction validation), runs verification v1 on
the RAW parser rows, and separately records what repair_transaction_sides would have
changed. No Excel, no DB, no S3, no AI, no file is modified.

Run inside the backend container (Python 3.11):

    python -m scripts.baseline_run --samples-dir /samples --out-dir /out \
        --per-bank 25 --exclude-csv /out/MOVE_PLAN_not_executed.csv

Resumable: results are appended to <out-dir>/baseline.jsonl and files already
present there are skipped on the next run.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

CHECKS = [
    "schema_check",
    "balance_check",
    "opening_closing_check",
    "printed_totals_check",
    "duplicate_check",
    "header_period_check",
]


def _load_exclusions(csv_path: Optional[str]) -> Set[str]:
    """Names of files known/suspected to sit in the wrong bank folder (kept out of the baseline)."""
    if not csv_path:
        return set()
    out: Set[str] = set()
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            name = (r.get("file") or r.get("filename") or "").strip()
            src = (r.get("from_folder") or r.get("folder") or "").strip()
            if name:
                out.add(f"{src}/{name}".lower())
    return out


def _pick(samples: List[Dict[str, str]], per_bank: int) -> List[Dict[str, str]]:
    """Deterministic, evenly spaced pick per bank (sorted by path)."""
    by_bank: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for s in samples:
        by_bank[s["bank_key"]].append(s)
    picked: List[Dict[str, str]] = []
    for bank in sorted(by_bank):
        items = sorted(by_bank[bank], key=lambda x: x["path"])
        if per_bank <= 0 or len(items) <= per_bank:
            picked.extend(items)
        else:
            step = len(items) / per_bank
            picked.extend(items[int(i * step)] for i in range(per_bank))
    return picked


def _run_one(sample: Dict[str, str]) -> Dict[str, Any]:
    from app.services.pipeline.reconciliation import repair_transaction_sides
    from app.services.pipeline_orchestrator import _get_bank_processor
    from app.services.verification import verify_from_pipeline

    t0 = time.monotonic()
    row: Dict[str, Any] = {
        "bank_key": sample["bank_key"],
        "file": Path(sample["path"]).name,
        "path": sample["path"],
        "stage": "start",
        "error": "",
    }
    try:
        cls = _get_bank_processor(sample["bank_key"])
        if cls is None:
            row.update(stage="no_processor")
            return row
        proc = cls(strict_mode=False)

        pdf = proc.pdf_validator.validate(sample["path"])
        row["pages"] = pdf.total_pages
        structure = proc.structure_validator.validate(pdf.text_content, pdf.first_page_text)
        parse = proc.parser.parse(sample["path"], pdf.text_content)
        if parse.total_count <= 0:
            row.update(stage="parse_no_transactions")
            return row

        raw_dicts = [t.to_dict() if hasattr(t, "to_dict") else dict(t) for t in parse.transactions]
        val_raw = proc.transaction_validator.validate([dict(d) for d in raw_dicts])
        if isinstance(val_raw, tuple):
            validated = val_raw[0]
        elif hasattr(val_raw, "validated_transactions"):
            validated = val_raw.validated_transactions
        else:
            validated = list(val_raw)

        meta = getattr(structure, "metadata", None)
        o = getattr(meta, "opening_balance", None)
        c = getattr(meta, "closing_balance", None)
        opening = o if o is not None else parse.opening_balance
        closing = c if c is not None else parse.closing_balance

        report = verify_from_pipeline(
            parse.transactions,
            structure_metadata=meta,
            opening=opening,
            closing=closing,
            validated_count=len(validated),
        )
        # What repair would do afterwards (recorded only; verification above never saw repaired rows).
        _, repair_stats = repair_transaction_sides(validated, opening_balance=opening)
        report.repairs = dict(repair_stats)

        d = report.to_dict()
        row.update(
            stage="verified_run",
            state=d["state"],
            failures=",".join(d["failures"]),
            raw_transaction_count=d["raw_transaction_count"],
            raw_debit_count=d["raw_debit_count"],
            raw_credit_count=d["raw_credit_count"],
            validated_transaction_count=d["validated_transaction_count"],
            parser_total_count=parse.total_count,
            reasons=",".join(d["reasons"]),
            notes=",".join(d["notes"]),
            failure_class=d["failure_class"] or "",
            repair_masks_balance_failure=d["repair_masks_balance_failure"],
            repair_swap=repair_stats.get("swap", 0),
            repair_delta=repair_stats.get("delta_repair", 0),
            repair_unfixed=repair_stats.get("unfixed", 0),
            opening_source="structure" if o is not None else ("parser" if parse.opening_balance is not None else "none"),
        )
        for name in CHECKS:
            row[name] = d["checks"][name]["status"]
        row["balance_mismatches"] = d["checks"]["balance_check"]["detail"].get("mismatches")
        row["balance_order_used"] = d["checks"]["balance_check"]["detail"].get("order_used")
        row["oc_difference"] = d["checks"]["opening_closing_check"]["detail"].get("difference")
        row["declared_closing_matches_last_row"] = d["checks"]["opening_closing_check"]["detail"].get("declared_closing_matches_last_row")
        row["declared_opening_matches_chain"] = d["checks"]["opening_closing_check"]["detail"].get("declared_opening_matches_chain")
        row["empty_descriptions"] = d["checks"]["schema_check"]["detail"].get("empty_descriptions")
        row["rows_without_single_amount"] = d["checks"]["schema_check"]["detail"].get("rows_with_both_or_no_amount")
        row["printed_differences"] = json.dumps(d["checks"]["printed_totals_check"]["detail"].get("differences", {}))
        row["detail"] = d["checks"]
    except Exception as exc:  # the baseline must never stop on one bad file
        code = getattr(exc, "error_code", None)
        row.update(stage=f"error:{code or type(exc).__name__}", error=str(exc)[:300])
        if not code:
            row["traceback"] = traceback.format_exc()[-800:]
    finally:
        row["seconds"] = round(time.monotonic() - t0, 2)
    return row


WRONG_BANK = ("NOT_", "NOT_SUPPORTED_UNKNOWN_STATEMENT")


def _outcome(r: Dict[str, Any]) -> str:
    """Coarse outcome class so identical root causes are grouped, not listed one by one."""
    st = r["stage"]
    if st == "verified_run":
        return "parsed"
    if st == "parse_no_transactions" or st.endswith("NO_TRANSACTIONS") or st.endswith("NO_TRANSACTION_TABLE"):
        return "no_transactions_found"
    if st.endswith("INSUFFICIENT_TEXT"):
        return "UNSUPPORTED_SCANNED_PDF"
    if "ENCRYPTED" in st:
        return "encrypted"
    code = st.split(":", 1)[-1]
    if code.startswith("NOT_") and code.endswith("_STATEMENT"):
        return "wrong_bank_for_folder"
    return "other_error"


def _rate(rows: List[Dict[str, Any]], name: str) -> str:
    p = sum(1 for r in rows if r.get(name) == "pass")
    f = sum(1 for r in rows if r.get(name) == "fail")
    return f"{p}/{p + f}" if (p + f) else "n/a"


def _summarise(rows: List[Dict[str, Any]], out_dir: Path) -> str:
    lines: List[str] = []
    total = len(rows)
    lines.append(f"# Verification v1 baseline ({total} PDFs from banks that have a processor)\n")
    outc = Counter(_outcome(r) for r in rows)
    lines.append("## What happened to each PDF\n")
    for k, v in outc.most_common():
        lines.append(f"- {k}: {v}")
    lines.append(
        "\n`wrong_bank_for_folder` = the bank's own processor rejected the file (it is another bank's statement, "
        "or the bank hint disagrees). `UNSUPPORTED_SCANNED_PDF` = no usable text layer (no OCR by design). "
        "Both go to `needs_manual_review.csv`; they say nothing about parser accuracy.\n"
    )
    ran = [r for r in rows if r["stage"] == "verified_run"]
    lines.append(f"## Verification state ({len(ran)} statements that parsed)\n")
    st = Counter(r["state"] for r in ran)
    for k in ("VERIFIED", "REVIEW", "FAILED"):
        lines.append(f"- {k}: {st.get(k, 0)} ({(100 * st.get(k, 0) // len(ran)) if ran else 0}%)")
    lines.append("\n## Failure class (non-VERIFIED statements)\n")
    fc = Counter(r.get("failure_class") or "-" for r in ran if r["state"] != "VERIFIED")
    for k, v in fc.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("\n## Check results (pass / fail / skip)\n")
    for name in CHECKS:
        c = Counter(r.get(name) for r in ran)
        lines.append(f"- {name}: {c.get('pass', 0)} / {c.get('fail', 0)} / {c.get('skip', 0)}")
    rep = [r for r in ran if (r.get("repair_swap") or 0) + (r.get("repair_delta") or 0) > 0]
    masked = [r for r in ran if r.get("repair_masks_balance_failure")]
    lines.append("\n## Repair\n")
    lines.append(f"- statements where repair changed at least one row: {len(rep)} of {len(ran)}")
    lines.append(f"- statements where the RAW balance chain failed and repair then changed rows (repair would mask it): {len(masked)}")
    dropped = sum(1 for r in ran if (r.get("validated_transaction_count") or 0) < (r.get("raw_transaction_count") or 0))
    lines.append(f"- statements where the step-4 validator dropped rows: {dropped}")
    lines.append("\n## Reasons (count of statements)\n")
    rc = Counter(x for r in ran for x in (r.get("reasons") or "").split(",") if x)
    for k, v in rc.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("\n## By bank\n")
    lines.append(
        "| bank | PDFs | parsed | VERIFIED | REVIEW | FAILED | balance pass | open/close pass | printed pass | "
        "dup fails | schema fails | period fails | avg txns | repaired stmts | not parsed |"
    )
    lines.append("|" + "---|" * 15)
    for bank in sorted({r["bank_key"] for r in rows}):
        b = [r for r in rows if r["bank_key"] == bank]
        bp = [r for r in b if r["stage"] == "verified_run"]
        s2 = Counter(r["state"] for r in bp)
        avg = round(sum(r["raw_transaction_count"] for r in bp) / len(bp)) if bp else 0
        repd = sum(1 for r in bp if (r.get("repair_swap") or 0) + (r.get("repair_delta") or 0) > 0)
        lines.append(
            f"| {bank} | {len(b)} | {len(bp)} | {s2.get('VERIFIED', 0)} | {s2.get('REVIEW', 0)} | {s2.get('FAILED', 0)} | "
            f"{_rate(bp, 'balance_check')} | {_rate(bp, 'opening_closing_check')} | {_rate(bp, 'printed_totals_check')} | "
            f"{sum(1 for r in bp if r.get('duplicate_check') == 'fail')} | {sum(1 for r in bp if r.get('schema_check') == 'fail')} | "
            f"{sum(1 for r in bp if r.get('header_period_check') == 'fail')} | {avg} | {repd} | {len(b) - len(bp)} |"
        )
    nb = out_dir / "banks_without_processor.json"
    if nb.exists():
        data = json.loads(nb.read_text(encoding="utf-8"))
        lines.append(f"\n## Banks with no processor yet ({len(data)} folders, not run)\n")
        lines.append(", ".join(f"{k} ({v})" for k, v in data.items()))
    text = "\n".join(lines) + "\n"
    (out_dir / "baseline_summary.md").write_text(text, encoding="utf-8")

    # Manual-review queue: everything that needs human judgement, one row per file.
    with open(out_dir / "needs_manual_review.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "bank_key", "file", "state_or_stage", "reasons", "path"])
        for r in rows:
            o = _outcome(r)
            if o in ("wrong_bank_for_folder", "UNSUPPORTED_SCANNED_PDF", "encrypted", "other_error", "no_transactions_found"):
                w.writerow([o, r["bank_key"], r["file"], r["stage"], r.get("error", "")[:120], r["path"]])
            elif r.get("state") == "FAILED" or r.get("failure_class") == "ROWS_SUSPECT":
                w.writerow([f"verify_{r.get('failure_class') or 'FAILED'}", r["bank_key"], r["file"], r.get("state"), r.get("reasons", ""), r["path"]])
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples-dir", required=True, help="folder with one sub-folder per bank")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--per-bank", type=int, default=25, help="0 = all files")
    ap.add_argument("--banks", default="", help="comma list of bank_keys to include")
    ap.add_argument("--exclude-csv", default="", help="MOVE_PLAN csv: files suspected to be in the wrong folder")
    ap.add_argument("--max-seconds", type=int, default=0, help="stop after this many seconds (resume later)")
    args = ap.parse_args()

    from tests.golden.snapshot_utils import discover_samples

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / "baseline.jsonl"

    samples = discover_samples(Path(args.samples_dir))
    excl = _load_exclusions(args.exclude_csv)
    if excl:
        samples = [
            s for s in samples
            if f"{Path(s['path']).parent.name}/{Path(s['path']).name}".lower() not in excl
        ]
    if args.banks:
        keep = {b.strip() for b in args.banks.split(",") if b.strip()}
        samples = [s for s in samples if s["bank_key"] in keep]
    from app.services.pipeline_orchestrator import _get_bank_processor

    has_proc: Dict[str, bool] = {}
    for b in {x["bank_key"] for x in samples}:
        try:
            has_proc[b] = _get_bank_processor(b) is not None
        except Exception:
            has_proc[b] = False
    unsupported_counts = Counter(x["bank_key"] for x in samples if not has_proc[x["bank_key"]])
    samples = _pick([x for x in samples if has_proc[x["bank_key"]]], args.per_bank)
    (out_dir / "banks_without_processor.json").write_text(
        json.dumps(dict(sorted(unsupported_counts.items())), indent=2), encoding="utf-8"
    )

    done: Dict[str, Dict[str, Any]] = {}
    if jsonl.exists():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["path"]] = r

    start = time.monotonic()
    todo = [s for s in samples if s["path"] not in done]
    print(f"{len(samples)} selected, {len(done)} already done, {len(todo)} to run")
    with open(jsonl, "a", encoding="utf-8") as fh:
        for i, s in enumerate(todo, 1):
            if args.max_seconds and time.monotonic() - start > args.max_seconds:
                print("time budget reached; re-run the same command to resume")
                break
            r = _run_one(s)
            done[s["path"]] = r
            fh.write(json.dumps(r, default=str) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {s['bank_key']:<15} {r.get('state', r['stage']):<10} {r['file'][:60]}")

    rows = [done[s["path"]] for s in samples if s["path"] in done]
    flat = [{k: v for k, v in r.items() if k not in ("detail", "traceback")} for r in rows]
    cols = sorted({k for r in flat for k in r}, key=lambda k: (k not in ("bank_key", "file", "stage", "state"), k))
    with open(out_dir / "baseline.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(flat)
    print(_summarise(rows, out_dir))


if __name__ == "__main__":
    main()

"""Capture RAW output of the existing HDFC pipeline (steps 1-4 only) as old_result.json.

Purpose: a trustworthy row-level reference for the old-vs-new comparator.

What it runs (UNCHANGED existing code, same order as BaseBankProcessor._run_pipeline):
  1 PDFIntegrityValidator   2 HDFCStructureValidator   3 HDFCParser.parse
  4 HDFCTransactionValidator   + verification v1 on the RAW parser rows (as the pipeline does)
What it deliberately does NOT run: repair_transaction_sides, reconciliation, classification,
recurring, aggregation, Excel. Nothing here mutates rows.

Safety: no passwords are accepted or stored (locked PDFs are recorded as LOCKED and skipped);
outputs hold customer data, so they go to an ignored folder (default <repo>/comparison/) and
must never be committed; source PDFs are referenced by path + SHA-256, never copied.
Deterministic (sorted keys, no timestamps inside old_result.json) and resumable.

Usage (from backend/):
  python -m scripts.capture_old_output --input "../samples/HDFC Bank" --out ../comparison/hdfc --pilot 16
  python -m scripts.capture_old_output --input "../New Dataset/Ready to Use PDF/HDFC Bank" --out ../comparison/hdfc --time-budget 150
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

SCHEMA = "airco.old_result/1"
TOOL_VERSION = "5"
BANK_KEY = "hdfc"
BANK_NAME = "HDFC Bank"
PARSER_FILES = [
    "app/services/banks/hdfc/parser.py",
    "app/services/banks/hdfc/structure_validator.py",
    "app/services/banks/hdfc/transaction_validator.py",
    "app/services/banks/_shared/base_parser.py",
    "app/services/banks/_shared/dynamic_column_detector.py",
    "app/services/core/pdf_integrity_validator.py",
    "app/services/pipeline/normalize.py",
    "app/services/verification/engine.py",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def producer_fingerprint(git_commit: str = "") -> Dict[str, Any]:
    versions: Dict[str, str] = {}
    for mod in ("pdfplumber", "pdfminer", "pikepdf", "pypdf"):
        try:
            m = __import__(mod)
            versions[mod] = str(getattr(m, "__version__", "?"))
        except Exception:
            versions[mod] = "not-installed"
    files = {f: (sha256_file(BACKEND / f) if (BACKEND / f).is_file() else "MISSING") for f in PARSER_FILES}
    return {
        "tool_version": TOOL_VERSION,
        "git_commit": git_commit or os.environ.get("CAPTURE_GIT_COMMIT") or _git("rev-parse", "HEAD"),
        "git_tag_baseline": "v2.0-slice-2c-stable",
        "parser_files_sha256": files,
        "python": platform.python_version(),
        "libraries": versions,
    }


def fingerprint_id(fp: Dict[str, Any]) -> str:
    """Identity of the producing code (excludes git commit so unrelated commits don't invalidate captures)."""
    core = {"t": fp["tool_version"], "f": fp["parser_files_sha256"], "py": fp["python"], "lib": fp["libraries"]}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def _plain(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _plain(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _row(t: Any) -> Dict[str, Any]:
    """Native raw row exactly as the parser produced it (incl. raw_line/line_number)."""
    if dataclasses.is_dataclass(t) and not isinstance(t, type):
        return _plain(t)
    if hasattr(t, "to_dict"):
        return _plain(t.to_dict())
    return _plain(dict(t))


def _dec(x: Any) -> Optional[str]:
    return None if x is None else str(x)


def isolate_side_effects(sidefx: Path) -> None:
    """Redirect the parser's queue/metrics files away from real data dirs (behaviour otherwise unchanged)."""
    sidefx.mkdir(parents=True, exist_ok=True)
    from app.services.banks._shared.parser_metrics import ParserMetrics
    from app.services.banks._shared.unsupported_format_queue import UnsupportedFormatQueue

    ParserMetrics.DEFAULT_STORAGE_PATH = str(sidefx / "parser_metrics.json")
    UnsupportedFormatQueue.DEFAULT_STORAGE_PATH = str(sidefx / "unsupported_formats")


def is_locked(path: Path) -> bool:
    try:
        import pikepdf

        with pikepdf.open(str(path)):
            return False
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__ == "PasswordError"


def derive_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Facts computed ONLY from the raw rows (no metadata): used as a metadata-independent reference."""
    from decimal import Decimal, InvalidOperation

    def d(x: Any) -> Decimal:
        try:
            return Decimal(str(x)) if x not in (None, "") else Decimal("0")
        except InvalidOperation:
            return Decimal("0")

    if not rows:
        return {"row_count": 0}
    first, last = rows[0], rows[-1]
    opening = d(first.get("balance")) + d(first.get("debit")) - d(first.get("credit"))
    chain_breaks, prev = 0, d(first.get("balance"))
    for r in rows[1:]:
        expected = prev - d(r.get("debit")) + d(r.get("credit"))
        if abs(expected - d(r.get("balance"))) > Decimal("0.01"):
            chain_breaks += 1
        prev = d(r.get("balance"))
    return {
        "row_count": len(rows),
        "opening_from_first_row": str(opening.quantize(Decimal("0.01"))),
        "closing_from_last_row": str(d(last.get("balance"))),
        "sum_debits": str(sum((d(r.get("debit")) for r in rows), Decimal("0"))),
        "sum_credits": str(sum((d(r.get("credit")) for r in rows), Decimal("0"))),
        "debit_rows": sum(1 for r in rows if d(r.get("debit")) > 0),
        "credit_rows": sum(1 for r in rows if d(r.get("credit")) > 0),
        "balance_chain_breaks": chain_breaks,
        "first_row_date": first.get("date"),
        "last_row_date": last.get("date"),
    }


def detector_context(path: Path) -> Dict[str, Any]:
    """Slice 2B detector + layout view of the PDF (corpus curation / layout diversity; not part of the old output)."""
    try:
        from app.services.statement_engine import analyze_text_pages, detect_layout
        from app.services.statement_engine.capability import check_pdf

        cap, texts = check_pdf(str(path))
        a = analyze_text_pages(path.name, cap, texts)
        det = a.detection
        lay = detect_layout(texts, det.bank_id if det else None)
        return {
            "capability": cap.capability.value, "detector_state": a.state.value,
            "detector_bank": getattr(det, "bank_id", None) if det else None,
            "detector_confidence": det.confidence.value if det else None,
            "layout_id": lay.layout_id, "layout_confidence": lay.confidence.value, "layout_header": lay.column_header,
            "page_count": getattr(cap, "page_count", None),
            "table_headers": table_headers(texts),
        }
    except Exception as exc:  # noqa: BLE001
        return {"detector_error": type(exc).__name__}


def table_headers(texts: List[str]) -> List[str]:
    """Distinct transaction-table header lines (whitespace-normalised, <=3): a layout fingerprint for diversity analysis."""
    import re

    seen: List[str] = []
    for t in texts:
        for line in (t or "").splitlines():
            low = line.lower()
            if "narration" in low and ("withdrawal" in low or "debit" in low) and ("balance" in low):
                norm = re.sub(r"\s+", " ", line).strip()[:160]
                if norm not in seen:
                    seen.append(norm)
    return seen[:3]


def categorize(doc: Dict[str, Any]) -> str:
    """CAPTURED | LOCKED | SCANNED_UNSUPPORTED | NON_HDFC | PARSER_ERROR.

    A non-HDFC file is an exclusion, never an old-parser failure; folder membership is not ground truth.
    """
    status = doc.get("status")
    err = doc.get("error") or {}
    ctx = doc.get("context") or {}
    if status == "OK":
        return "CAPTURED"
    if status == "LOCKED":
        return "LOCKED"
    msg = (err.get("message") or "").lower()
    if status == "PDF_INVALID" or "insufficient text" in msg or ctx.get("capability") == "SCANNED":
        return "SCANNED_UNSUPPORTED"
    other = ctx.get("detector_bank") not in (None, "hdfc") and ctx.get("detector_confidence") in ("HIGH", "VERY_HIGH", "MEDIUM")
    if "does not appear to be an hdfc" in msg or other:
        return "NON_HDFC"
    return "PARSER_ERROR"


def capture_one(path: Path, sha: str, fp: Dict[str, Any]) -> Dict[str, Any]:
    doc = _capture_one(path, sha, fp)
    doc["category"] = categorize(doc)
    return doc


def _capture_one(path: Path, sha: str, fp: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.banks.hdfc.parser import HDFCParser
    from app.services.banks.hdfc.structure_validator import HDFCStructureValidator
    from app.services.banks.hdfc.transaction_validator import HDFCTransactionValidator
    from app.services.core.pdf_integrity_validator import PDFIntegrityValidator
    from app.services.pipeline.models import StatementMetadata
    from app.services.pipeline.normalize import to_normalized
    from app.services.verification import verify_from_pipeline

    doc: Dict[str, Any] = {
        "schema": SCHEMA, "engine": "old", "bank_key": BANK_KEY, "stage": "RAW",
        "source": {"sha256": sha, "size_bytes": path.stat().st_size, "file_name": path.name},
        "producer": fp, "status": "ERROR", "error": None, "steps": {}, "metadata": None,
        "printed": None, "derived": None, "context": None, "category": None, "raw_rows": [], "validated_rows": [], "normalized": None, "verification": None,
    }
    doc["context"] = detector_context(path)
    if is_locked(path):
        doc["status"], doc["error"] = "LOCKED", {"code": "PASSWORD_REQUIRED", "message": "encrypted; not captured (no passwords are used)"}
        return doc
    try:
        pdf = PDFIntegrityValidator().validate(str(path))
        doc["steps"]["pdf_integrity"] = pdf.to_dict()
        if not pdf.is_valid:
            doc["status"], doc["error"] = "PDF_INVALID", {"code": pdf.error_code, "message": pdf.error_message}
            return doc
        structure = HDFCStructureValidator().validate(pdf.text_content, pdf.first_page_text)
        doc["steps"]["structure"] = {k: v for k, v in structure.to_dict().items() if k != "metadata"}
        meta = structure.metadata
        doc["metadata"] = _plain(meta)
        doc["printed"] = {"debit_count": meta.dr_count, "credit_count": meta.cr_count,
                          "total_debits": meta.total_debits, "total_credits": meta.total_credits}
        if not structure.is_valid:
            doc["status"], doc["error"] = "STRUCTURE_INVALID", {"code": structure.error_code, "message": structure.error_message}
            return doc
        parser = HDFCParser(audit_service=None, job_id=None)
        parsed = parser.parse(str(path), pdf.text_content)
        doc["steps"]["parse"] = {
            "total_count": parsed.total_count, "parse_method": parsed.parse_method,
            "opening_balance": parsed.opening_balance, "closing_balance": parsed.closing_balance,
            "total_credits": parsed.total_credits, "total_debits": parsed.total_debits,
            "warnings": list(parsed.warnings or []),
            "parser_metrics": [{k: v for k, v in m.items() if k != "execution_time_ms"}  # timing is nondeterministic
                               for m in _plain(getattr(parser, "_collected_parser_metrics", []) or [])],
        }
        doc["raw_rows"] = [_row(t) for t in parsed.transactions]
        if parsed.total_count <= 0:
            doc["status"], doc["error"] = "PARSER_FAILURE", {"code": "NO_TRANSACTIONS", "message": "parser returned no transactions"}
            return doc
        val = HDFCTransactionValidator(strict_mode=False).validate([t.to_dict() if hasattr(t, "to_dict") else t for t in parsed.transactions])
        validated = val.validated_transactions if hasattr(val, "validated_transactions") else (val[0] if isinstance(val, tuple) else list(val))
        doc["steps"]["transaction_validation"] = _plain(val.to_dict()) if hasattr(val, "to_dict") else {}
        doc["validated_rows"] = [_plain(r) for r in validated]
        # same openings/closings the pipeline hands to verification and reconciliation
        opening = meta.opening_balance if meta.opening_balance is not None else parsed.opening_balance
        closing = meta.closing_balance if meta.closing_balance is not None else parsed.closing_balance
        try:
            rep = verify_from_pipeline(parsed.transactions, structure_metadata=meta, opening=opening, closing=closing, validated_count=len(validated))
            doc["verification"] = _plain(rep.to_dict())
        except Exception as exc:  # noqa: BLE001
            doc["verification"] = {"error": f"{type(exc).__name__}: {exc}"}
        norm = to_normalized(parsed.transactions, bank_key=BANK_KEY)
        smeta = StatementMetadata.from_mapping(_plain(meta), bank_name=BANK_NAME, bank_key=BANK_KEY)
        doc["normalized"] = {
            "boundary": "app.services.pipeline.normalize.to_normalized(raw parser rows, bank_key='hdfc'); no repair, no classification",
            "metadata": {
                "bank_name": smeta.bank_name, "bank_key": smeta.bank_key, "account_number": smeta.account_number,
                "account_holder": smeta.account_holder, "account_type": smeta.account_type,
                "opening_balance": _dec(opening), "closing_balance": _dec(closing),
                "statement_from": smeta.statement_from, "statement_to": smeta.statement_to,
            },
            "transactions": [
                {"date": t.date, "description": t.description, "debit": _dec(t.debit), "credit": _dec(t.credit),
                 "balance": _dec(t.balance), "ref_no": t.ref_no, "value_date": t.value_date}
                for t in norm
            ],
        }
        doc["derived"] = derive_from_rows(doc["raw_rows"])
        doc["status"] = "OK"
    except Exception as exc:  # noqa: BLE001 — one bad PDF must never stop the corpus
        doc["status"], doc["error"] = "ERROR", {"code": type(exc).__name__, "message": str(exc)[:500]}
    return doc


def write_json(path: Path, doc: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def mask(s: Optional[str]) -> str:
    s = s or ""
    return ("X" * max(0, len(s) - 4)) + s[-4:]


def discover(inputs: Iterable[Path]) -> List[Path]:
    seen, out = set(), []
    for root in inputs:
        for p in sorted(root.rglob("*.pdf"), key=lambda x: str(x).lower()):
            if str(p) not in seen:
                seen.add(str(p)); out.append(p)
    return out


def pick_pilot(files: List[Path], n: int) -> List[Path]:
    """Deterministic spread: golden-covered PDFs, locked ones, size extremes, then even spacing by size."""
    golden = {p.stem for p in (BACKEND / "tests/golden/hdfc").glob("*.json")}
    chosen: List[Path] = [p for p in files if p.stem in golden]
    chosen += [p for p in files if "locked" in str(p).lower()][:2]
    by_size = sorted(files, key=lambda p: (p.stat().st_size, str(p)))
    chosen += by_size[:2] + [p for p in by_size if p.stat().st_size < 4_000_000][-2:]
    k = max(1, n - len(set(chosen)))
    step = max(1, len(by_size) // (k + 1))
    chosen += by_size[step::step][:k]
    uniq: List[Path] = []
    for p in chosen:
        if p not in uniq:
            uniq.append(p)
    return uniq[:n]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", action="append", required=True, help="folder with HDFC PDFs (repeatable)")
    ap.add_argument("--out", default=str(REPO / "comparison" / "hdfc"))
    ap.add_argument("--pilot", type=int, default=0, help="capture only N representative PDFs")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--time-budget", type=float, default=0, help="stop starting new PDFs after N seconds (re-run to resume)")
    ap.add_argument("--git-commit", default="", help="commit hash to record (use when git is unavailable, e.g. in Docker)")
    ap.add_argument("--summary", action="store_true", help="only (re)write summary.md from existing results; no capture")
    ap.add_argument("--force", action="store_true", help="recapture even if a matching result exists")
    args = ap.parse_args(argv)

    if args.summary:
        mp = Path(args.out) / "manifest.json"
        write_summary(Path(args.out), json.loads(mp.read_text(encoding="utf-8"))["items"])
        print("summary.md written")
        return 0
    logging.disable(logging.CRITICAL)  # parser logs are noisy and may echo statement text
    out = Path(args.out).resolve()
    isolate_side_effects(Path(tempfile.gettempdir()) / "airco_capture_sidefx")
    fp = producer_fingerprint(args.git_commit)
    fid = fingerprint_id(fp)
    files = discover(Path(i) for i in args.input)
    if args.pilot:
        files = pick_pilot(files, args.pilot)
    if args.limit:
        files = files[: args.limit]
    results_dir = out / "results"
    started = time.monotonic()
    done = skipped = 0
    manifest_rows: List[Dict[str, Any]] = []
    stopped_early = False
    for p in files:
        if args.time_budget and time.monotonic() - started > args.time_budget:
            stopped_early = True
            break
        sha = sha256_file(p)
        target = results_dir / f"{sha}.json"
        doc = None
        if target.exists() and not args.force:
            try:
                prev = json.loads(target.read_text(encoding="utf-8"))
                if prev.get("producer") and fingerprint_id(prev["producer"]) == fid:
                    doc = prev; skipped += 1
            except Exception:
                doc = None
        if doc is None:
            doc = capture_one(p, sha, fp)
            write_json(target, doc)
            done += 1
        manifest_rows.append(_manifest_row(p, sha, doc, target, out))

    # manifest is rebuilt from every result on disk so partial runs accumulate
    _write_manifest(out, manifest_rows, fid)
    print(json.dumps({"captured_now": done, "reused": skipped, "stopped_early": stopped_early,
                      "remaining_in_selection": max(0, len(files) - done - skipped), "out": str(out)}))
    return 0


def _manifest_row(p: Path, sha: str, doc: Dict[str, Any], target: Path, out: Path) -> Dict[str, Any]:
    txns = (doc.get("normalized") or {}).get("transactions") or []
    meta = (doc.get("normalized") or {}).get("metadata") or {}
    return {
        "pdf_path": str(p), "sha256": sha, "status": doc.get("status"), "category": doc.get("category"),
        "error_code": (doc.get("error") or {}).get("code"), "error_message": (doc.get("error") or {}).get("message"),
        "parse_method": (doc.get("steps", {}).get("parse") or {}).get("parse_method"),
        "txn_count": len(txns), "debit_count": sum(1 for t in txns if t["debit"]), "credit_count": sum(1 for t in txns if t["credit"]),
        "opening_balance": meta.get("opening_balance"), "closing_balance": meta.get("closing_balance"),
        "printed_dr_count": (doc.get("printed") or {}).get("debit_count"), "printed_cr_count": (doc.get("printed") or {}).get("credit_count"),
        "verification_state": (doc.get("verification") or {}).get("state"),
        "account_masked": mask(meta.get("account_number")),
        "detector_bank": (doc.get("context") or {}).get("detector_bank"),
        "layout_id": (doc.get("context") or {}).get("layout_id"),
        "table_header": " | ".join((doc.get("context") or {}).get("table_headers") or []),
        "page_count": (doc.get("context") or {}).get("page_count"),
        "chain_breaks": (doc.get("derived") or {}).get("balance_chain_breaks"),
        "closing_from_rows": (doc.get("derived") or {}).get("closing_from_last_row"),
        "old_result": str(target.relative_to(out)),
    }


def _write_manifest(out: Path, rows: List[Dict[str, Any]], fid: str) -> None:
    mpath = out / "manifest.json"
    existing: Dict[str, Dict[str, Any]] = {}
    if mpath.exists():
        try:
            for r in json.loads(mpath.read_text(encoding="utf-8")).get("items", []):
                existing[r["pdf_path"]] = r
        except Exception:
            pass
    for r in rows:
        existing[r["pdf_path"]] = r
    items = sorted(existing.values(), key=lambda r: r["pdf_path"].lower())
    counts: Dict[str, int] = {}
    for r in items:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    write_json(mpath, {"schema": "airco.old_manifest/2", "producer_fingerprint": fid, "totals_by_category": counts, "items": items})
    write_summary(out, items)
    if items:
        with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(items[0].keys()))
            w.writeheader(); w.writerows(items)


def write_summary(out: Path, items: List[Dict[str, Any]]) -> None:
    """Baseline summary: categories, parse methods, verification, layouts. Counts only, no customer data."""
    from collections import Counter

    cat = Counter(r["category"] for r in items)
    uniq = {r["sha256"] for r in items}
    cap = [r for r in items if r["category"] == "CAPTURED"]
    lines = ["# HDFC old-output capture summary", "",
             f"PDF entries: {len(items)}  |  unique SHA-256: {len(uniq)}", "", "## By category"]
    lines += [f"- {k}: {cat.get(k, 0)}" for k in ("CAPTURED", "LOCKED", "SCANNED_UNSUPPORTED", "NON_HDFC", "PARSER_ERROR")]
    lines += ["", "## Captured statements",
              f"- parse methods: {dict(Counter(r['parse_method'] for r in cap))}",
              f"- verification states (v1, raw rows): {dict(Counter(r['verification_state'] for r in cap))}",
              f"- balance-chain breaks > 0: {sum(1 for r in cap if (r.get('chain_breaks') or 0) > 0)}",
              f"- detector agrees (hdfc): {sum(1 for r in cap if r.get('detector_bank') == 'hdfc')}/{len(cap)}",
              f"- Slice 2C layout ids: {dict(Counter(r.get('layout_id') for r in cap))}",
              f"- table header fingerprints: {dict(Counter(r.get('table_header') for r in cap))}",
              f"- pages: min {min((r['page_count'] or 0) for r in cap) if cap else 0}, max {max((r['page_count'] or 0) for r in cap) if cap else 0}",
              "", "## Non-HDFC exclusions: detector's bank",
              f"- {dict(Counter(r.get('detector_bank') for r in items if r['category'] == 'NON_HDFC'))}",
              "", "## Parser errors (old parser on files that look like HDFC)"]
    perr = Counter((r["error_code"], r["error_message"]) for r in items if r["category"] == "PARSER_ERROR")
    lines += [f"- {n} x {code}: {msg}" for (code, msg), n in perr.most_common()] or ["- none"]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

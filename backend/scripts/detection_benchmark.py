"""Benchmark the Slice 2B bank detector against the corpus folder labels, and against today's detector.

Observe-only: reads PDFs, writes reports. Changes nothing in the pipeline.

    python -m scripts.detection_benchmark --samples-dir "/samples" --out-dir /out --per-bank 60 --workers 4

The corpus folder is a LABEL, not the truth: Slice 1 found misplaced files. So every disagreement is written to
a review file, and the headline numbers are reported both ways (all labels, and confident predictions only).
A disagreement is a finding to look at, not automatically a detector error.

Resumable: results are appended to <out-dir>/detection.jsonl; files already present are skipped.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

UNKNOWN_BUCKETS = {"other_unknown", "non_bank_documents", "password_protected"}
CONF_ORDER = ["VERY_HIGH", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
CONFIDENT = {"VERY_HIGH", "HIGH"}

_LEGACY = None


def _legacy():
    global _LEGACY
    if _LEGACY is None:
        try:
            from app.services.banks._shared.hygiene_check import HygieneCheck

            _LEGACY = HygieneCheck(".")
        except Exception:
            _LEGACY = False
    return _LEGACY or None


def _collect(samples_dir: Path) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for folder in sorted(p for p in samples_dir.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for pdf in sorted(folder.rglob("*.pdf")):
            out.append({"folder": folder.name, "path": str(pdf)})
    return out


def _pick(items: List[Dict[str, str]], per_bank: int) -> List[Dict[str, str]]:
    by: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for s in items:
        by[s["folder"]].append(s)
    picked: List[Dict[str, str]] = []
    for folder in sorted(by):
        rows = sorted(by[folder], key=lambda x: x["path"])
        if per_bank <= 0 or len(rows) <= per_bank:
            picked.extend(rows)
        else:
            step = len(rows) / per_bank
            picked.extend(rows[int(i * step)] for i in range(per_bank))
    return picked


def _work(sample: Dict[str, str]) -> Dict[str, Any]:
    from app.services.statement_engine import analyze_pdf, default_registry
    from app.services.statement_engine.detector import _resolve_bank

    reg = default_registry()
    t0 = time.monotonic()
    name = Path(sample["path"]).name
    row: Dict[str, Any] = {"folder": sample["folder"], "file": name, "path": sample["path"], "error": ""}
    try:
        cfg = reg.by_folder(sample["folder"])
        row["expected"] = cfg.id if cfg else None
        row["label_kind"] = "bank" if cfg else ("unknown_bucket" if sample["folder"].lower() in UNKNOWN_BUCKETS else "unmapped")
        a = analyze_pdf(sample["path"], filename=name)
        row["capability"] = a.capability.capability.value
        row["pages"] = a.capability.page_count
        row["state"] = a.state.value
        d = a.detection
        if d:
            row.update(
                detected=d.bank_id,
                confidence=d.confidence.value,
                score=d.score,
                runner_up=d.runner_up_id,
                runner_up_score=d.runner_up_score,
                supported=d.supported,
                evidence="|".join(f"{e.kind.value}:{e.matched}" for e in d.evidence),
                reason=d.reason,
            )
        # today's detector, same file, no hint (filename is the corpus name, which rarely carries a bank)
        leg = _legacy()
        if leg is not None and a.capability.capability.value in ("TEXT", "MIXED"):
            raw = leg.detect_bank_name(sample["path"], original_filename=name)
            row["legacy_raw"] = raw
            row["legacy"] = _resolve_bank(reg, raw) if raw and raw != "unknown" else None
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["trace"] = traceback.format_exc()[-400:]
    row["seconds"] = round(time.monotonic() - t0, 2)
    return row


def _outcome(r: Dict[str, Any], key: str = "detected") -> str:
    """CORRECT / WRONG / ABSTAIN / NOT_ANALYZED / FOUND_IN_UNKNOWN_FOLDER / UNMAPPED"""
    if r.get("error"):
        return "ERROR"
    if r.get("capability") not in ("TEXT", "MIXED"):
        return "NOT_ANALYZED"
    conf = r.get("confidence", "UNKNOWN") if key == "detected" else ("HIGH" if r.get(key) else "UNKNOWN")
    got = r.get(key) if (key != "detected" or conf not in ("UNKNOWN", "LOW")) else None
    if r["label_kind"] == "unmapped":
        return "UNMAPPED"
    if r["label_kind"] == "unknown_bucket":
        return "FOUND_IN_UNKNOWN_FOLDER" if got else "ABSTAIN"
    if not got:
        return "ABSTAIN"
    return "CORRECT" if got == r["expected"] else "WRONG"


def _write_reports(rows: List[Dict[str, Any]], out: Path) -> None:
    csv_fields = [
        "folder", "file", "expected", "detected", "confidence", "score", "runner_up", "runner_up_score",
        "supported", "state", "capability", "pages", "legacy", "evidence", "reason", "error", "seconds", "outcome", "legacy_outcome", "path",
    ]
    for r in rows:
        r["outcome"] = _outcome(r)
        r["legacy_outcome"] = _outcome(r, "legacy")
    with open(out / "detection.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    review = [r for r in rows if r["outcome"] in ("WRONG", "FOUND_IN_UNKNOWN_FOLDER", "ERROR")]
    review.sort(key=lambda r: (CONF_ORDER.index(r.get("confidence", "UNKNOWN")) if r.get("confidence") in CONF_ORDER else 9, r["folder"]))
    with open(out / "detection_disagreements.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(review)

    analyzed = [r for r in rows if r["outcome"] not in ("NOT_ANALYZED", "ERROR", "UNMAPPED")]
    labelled = [r for r in analyzed if r["label_kind"] == "bank"]
    total_s = sum(r.get("seconds", 0) for r in rows)
    L: List[str] = ["# Bank detection benchmark (Slice 2B)\n"]
    L.append(f"Files run: **{len(rows)}** from {len({r['folder'] for r in rows})} folders. Seconds per file: {total_s / max(len(rows), 1):.2f} average.")
    L.append("\nCorpus folders are labels, not truth: a disagreement can be a misplaced file. Read `detection_disagreements.csv` before trusting any error count.\n")

    cap = Counter(r.get("capability", "ERROR") for r in rows)
    L.append("## Capability\n\n| Result | Files |\n|---|---|")
    for k, v in cap.most_common():
        L.append(f"| {k} | {v} |")

    L.append("\n## Precision by confidence (files labelled with a bank folder)\n")
    L.append("A prediction counts as made when confidence is not UNKNOWN or LOW. `wrong` = detected bank differs from the folder.\n")
    L.append("| Confidence | Predictions | Agree with folder | Disagree with folder | Agreement |\n|---|---|---|---|---|")
    for c in CONF_ORDER[:3]:
        sub = [r for r in labelled if r.get("confidence") == c]
        ok = sum(1 for r in sub if r["outcome"] == "CORRECT")
        bad = sum(1 for r in sub if r["outcome"] == "WRONG")
        L.append(f"| {c} | {len(sub)} | {ok} | {bad} | {(100 * ok / len(sub)) if sub else 0:.1f}% |")
    abst = sum(1 for r in labelled if r["outcome"] == "ABSTAIN")
    L.append(f"\nAbstained (UNKNOWN or LOW, user would pick the bank): **{abst}** of {len(labelled)} labelled files ({100 * abst / max(len(labelled), 1):.1f}%).")

    hi_wrong = [r for r in labelled if r["outcome"] == "WRONG" and r.get("confidence") in CONFIDENT]
    L.append(f"\n**Disagreements at HIGH or VERY_HIGH: {len(hi_wrong)}.** Each needs a human look (misplaced file, or a detector bug). Listed first in `detection_disagreements.csv`.")

    L.append("\n## New detector vs today's detector (same files, same labelled set)\n")
    leg_ok = sum(1 for r in labelled if r["legacy_outcome"] == "CORRECT")
    leg_bad = sum(1 for r in labelled if r["legacy_outcome"] == "WRONG")
    new_ok = sum(1 for r in labelled if r["outcome"] == "CORRECT")
    new_bad = sum(1 for r in labelled if r["outcome"] == "WRONG")
    n = max(len(labelled), 1)
    L.append("| Detector | Agrees with folder | Disagrees | Abstains |\n|---|---|---|---|")
    L.append(f"| Today's (`HygieneCheck.detect_bank_name`) | {leg_ok} ({100 * leg_ok / n:.1f}%) | {leg_bad} | {n - leg_ok - leg_bad} |")
    L.append(f"| New (any confidence above LOW) | {new_ok} ({100 * new_ok / n:.1f}%) | {new_bad} | {n - new_ok - new_bad} |")
    only_new = sum(1 for r in labelled if r["outcome"] == "CORRECT" and r["legacy_outcome"] != "CORRECT")
    only_old = sum(1 for r in labelled if r["legacy_outcome"] == "CORRECT" and r["outcome"] != "CORRECT")
    L.append(f"\nAgrees with folder only for new: {only_new}. Only for today's: {only_old} (look at these: they are possible regressions).")

    L.append("\n## Unknown and non-bank folders\n")
    unk = [r for r in analyzed if r["label_kind"] == "unknown_bucket"]
    f_unk = [r for r in unk if r["outcome"] == "FOUND_IN_UNKNOWN_FOLDER"]
    L.append(f"{len(unk)} analyzed files from Other_Unknown / Non_Bank_Documents / Password_Protected; the detector named a bank for **{len(f_unk)}**. By confidence: {dict(Counter(r.get('confidence') for r in f_unk))}. These are either misfiled statements or false detections.")

    L.append("\n## Per folder\n\n| Folder | Files | Text | Agree | Disagree | Abstain | Not analyzed | Unsupported bank found |\n|---|---|---|---|---|---|---|---|")
    by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by[r["folder"]].append(r)
    for f in sorted(by):
        rs = by[f]
        c = Counter(r["outcome"] for r in rs)
        text = sum(1 for r in rs if r.get("capability") in ("TEXT", "MIXED"))
        uns = sum(1 for r in rs if r.get("detected") and r.get("supported") is False and r.get("confidence") in ("VERY_HIGH", "HIGH", "MEDIUM"))
        L.append(f"| {f} | {len(rs)} | {text} | {c['CORRECT']} | {c['WRONG'] + c['FOUND_IN_UNKNOWN_FOLDER']} | {c['ABSTAIN']} | {c['NOT_ANALYZED'] + c['ERROR']} | {uns} |")

    pairs = Counter((r["expected"], r["detected"]) for r in labelled if r["outcome"] == "WRONG")
    if pairs:
        L.append("\n## Most common disagreements (folder label to detected bank)\n\n| Folder says | Detector says | Files |\n|---|---|---|")
        for (a, b), v in pairs.most_common(15):
            L.append(f"| {a} | {b} | {v} |")

    errs = [r for r in rows if r.get("error")]
    if errs:
        L.append(f"\n## Errors\n\n{len(errs)} files raised an error; first: `{errs[0]['file']}`: {errs[0]['error']}")
    (out / "detection_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples-dir", required=True, help="folder with one sub-folder per bank (the labels)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--per-bank", type=int, default=60, help="0 = every file")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jl = out / "detection.jsonl"
    done: Dict[str, Dict[str, Any]] = {}
    if jl.exists():
        for line in jl.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                done[r["path"]] = r
            except Exception:
                pass

    todo = [s for s in _pick(_collect(Path(a.samples_dir)), a.per_bank) if s["path"] not in done]
    print(f"{len(todo)} files to run, {len(done)} already done", flush=True)
    t0 = time.monotonic()
    with open(jl, "a", encoding="utf-8") as fh, ProcessPoolExecutor(max_workers=max(a.workers, 1)) as ex:
        futs = [ex.submit(_work, s) for s in todo]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            done[r["path"]] = r
            fh.write(json.dumps(r, default=str) + "\n")
            fh.flush()
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}  {time.monotonic() - t0:.0f}s", flush=True)
    _write_reports(list(done.values()), out)
    print(f"done in {time.monotonic() - t0:.0f}s -> {out}/detection_summary.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

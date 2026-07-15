"""
Capture golden snapshots from the CURRENT pipeline.

Uses bank processors directly so full transaction lists are available
(process_statement().to_dict() omits transactions).

Usage (from backend/):
  python -m tests.golden.capture_snapshots --samples-dir ../samples --mode free
  python -m tests.golden.capture_snapshots --samples-dir ../samples --mode hybrid --api-key sk-...

Env:
  GOLDEN_SAMPLES_DIR  default samples directory if --samples-dir omitted
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from tests.golden.snapshot_utils import (  # noqa: E402
    bank_display_name,
    build_snapshot_payload,
    discover_samples,
    extract_reconciliation_from_result,
)


def _default_samples_dir() -> Path:
    env = os.environ.get("GOLDEN_SAMPLES_DIR")
    if env:
        return Path(env)
    return _BACKEND_ROOT.parent / "samples"


def _snapshot_path(out_root: Path, bank_key: str, sample_name: str, mode: str) -> Path:
    suffix = "" if mode == "free" else f"__{mode}"
    return out_root / bank_key / f"{sample_name}{suffix}.json"


def _run_processor(
    *,
    pdf_path: str,
    bank_key: str,
    mode: str,
    api_key: Optional[str],
    output_dir: str,
) -> Any:
    from app.services.pipeline_orchestrator import _get_bank_processor

    ProcessorClass = _get_bank_processor(bank_key)
    if ProcessorClass is None:
        raise RuntimeError(f"Unsupported bank_key: {bank_key}")

    enable_ai = mode == "hybrid"
    processor = ProcessorClass(
        strict_mode=False,
        enable_ai=enable_ai,
        api_key=api_key if enable_ai else None,
        audit_service=None,
        job_id=None,
    )
    user_info = {
        "full_name": "Golden Snapshot",
        "account_type": "Savings",
        "bank_name": bank_display_name(bank_key),
    }
    return processor.process(
        file_path=pdf_path,
        user_info=user_info,
        output_dir=output_dir,
    )


def capture_one(
    *,
    pdf_path: str,
    bank_key: str,
    sample_name: str,
    mode: str,
    api_key: Optional[str],
    out_root: Path,
) -> Path:
    with tempfile.TemporaryDirectory(prefix="golden_out_") as tmp:
        result = _run_processor(
            pdf_path=pdf_path,
            bank_key=bank_key,
            mode=mode,
            api_key=api_key,
            output_dir=tmp,
        )

        transactions: List[Dict[str, Any]] = []
        if hasattr(result, "transactions") and result.transactions:
            for t in result.transactions:
                if isinstance(t, dict):
                    transactions.append(t)
                elif hasattr(t, "to_dict"):
                    transactions.append(t.to_dict())
                else:
                    transactions.append({})

        process_dict: Dict[str, Any] = {}
        if hasattr(result, "to_dict"):
            try:
                process_dict = result.to_dict()
            except Exception:
                process_dict = {
                    "status": getattr(result, "status", "unknown"),
                    "bank_key": bank_key,
                }
        else:
            process_dict = {"status": "unknown", "bank_key": bank_key}

        aggregation = getattr(result, "aggregation", None)
        # Phase-3-ready: re-run bank reconciler for real opening/closing + mismatch list
        reconciliation = extract_reconciliation_from_result(
            result, transactions, bank_key
        )

        metadata = {
            "bank_name": bank_display_name(bank_key),
            "bank_key": bank_key,
            "account_number": "",
            "account_holder": "Golden Snapshot",
            "account_type": "Savings",
            "opening_balance": reconciliation.get("opening_balance"),
            "closing_balance": reconciliation.get("closing_balance"),
        }

        payload = build_snapshot_payload(
            bank_key=bank_key,
            sample_name=sample_name,
            mode=mode,
            process_result=process_dict,
            transactions=transactions,
            reconciliation=reconciliation,
            aggregation=aggregation,
            metadata=metadata,
        )

        dest = _snapshot_path(out_root, bank_key, sample_name, mode)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return dest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Capture golden pipeline snapshots")
    parser.add_argument(
        "--samples-dir",
        type=Path,
        default=_default_samples_dir(),
        help="Directory of sample PDFs (samples/{bank_key}/*.pdf)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Output root for golden JSON (default: tests/golden/)",
    )
    parser.add_argument("--mode", choices=("free", "hybrid"), default="free")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GROQ_API_KEY"),
    )
    parser.add_argument(
        "--bank",
        action="append",
        dest="banks",
        help="Limit to bank_key (repeatable). Default: all discovered.",
    )
    parser.add_argument(
        "--max-per-bank",
        type=int,
        default=0,
        help="If >0, keep only the first N PDFs per bank_key (stable sort).",
    )
    args = parser.parse_args(argv)

    samples = discover_samples(args.samples_dir)
    if args.banks:
        allow = {b.lower() for b in args.banks}
        samples = [s for s in samples if s["bank_key"] in allow]
    if args.max_per_bank and args.max_per_bank > 0:
        kept: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {}
        for sample in samples:
            bk = sample["bank_key"]
            n = counts.get(bk, 0)
            if n >= args.max_per_bank:
                continue
            counts[bk] = n + 1
            kept.append(sample)
        samples = kept

    if not samples:
        print(
            "No PDFs found under {}. "
            "Place files as samples/{{bank_key}}/statement.pdf and re-run. "
            "See samples/README.md.".format(args.samples_dir),
            file=sys.stderr,
        )
        return 2

    if args.mode == "hybrid" and not args.api_key:
        print(
            "hybrid mode requires --api-key or ANTHROPIC_API_KEY/GROQ_API_KEY",
            file=sys.stderr,
        )
        return 2

    print(f"Capturing {len(samples)} sample(s) mode={args.mode}")
    failures = 0
    for sample in samples:
        try:
            dest = capture_one(
                pdf_path=sample["path"],
                bank_key=sample["bank_key"],
                sample_name=sample["sample_name"],
                mode=args.mode,
                api_key=args.api_key,
                out_root=args.out_dir,
            )
            print(f"  OK  {sample['bank_key']}/{sample['sample_name']} -> {dest}")
        except Exception as exc:
            failures += 1
            print(
                f"  FAIL {sample['bank_key']}/{sample['sample_name']}: {exc}",
                file=sys.stderr,
            )

    print(f"Done. failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

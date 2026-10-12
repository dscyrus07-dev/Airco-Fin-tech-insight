"""U4 onboarding pipeline: cluster T3-clean files by structure and propose
LayoutSpec sources for clusters of >=MIN_CLUSTER files. Registers nothing —
output is a report + proposed spec sources under comparison/universal/proposals/
(untracked).

Fingerprint = (sorted header token multiset, money-column count + role order,
date shape, amount form, page-width bucket). Two files with the same fingerprint
are candidates for one hand-reviewed LayoutSpec; the gate report runs build/
hold-out verification per cluster.

Usage:
    python -m tools.propose_layouts u3b.jsonl [u3a.jsonl ...]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
CORPUS = ROOT.parent / "Unified All Statements"
OUTDIR = ROOT / "comparison" / "universal" / "proposals"
MIN_CLUSTER = 10
TOP_N = 20


def fingerprint(rec: dict) -> str:
    inf = rec.get("univ", {}).get("infer", {})
    money = inf.get("money", "")
    shape = inf.get("date_shape", "")
    form = inf.get("amount_form", "")
    header = "|".join(sorted(str(inf.get("header_tokens", "")))) if inf.get("header_tokens") else "implicit"
    return hashlib.sha256(f"{header}::{money}::{shape}::{form}".encode()).hexdigest()[:12]


def main(jsonl_paths) -> int:
    recs = []
    for fp in jsonl_paths:
        p = Path(fp)
        if not p.exists():
            p = ROOT / "comparison" / "universal" / fp
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                recs.append(json.loads(line))
            except Exception:
                pass
    clean = [r for r in recs if r.get("univ", {}).get("verdict") == "REVIEW"]
    print(f"{len(recs)} records, {len(clean)} T3-clean")

    clusters = defaultdict(list)
    for r in clean:
        clusters[fingerprint(r)].append(r)
    ranked = sorted(clusters.items(), key=lambda kv: -len(kv[1]))
    OUTDIR.mkdir(parents=True, exist_ok=True)
    report = OUTDIR / "proposals_report.md"
    lines = ["# Universal-reader layout proposals",
             f"T3-clean files: {len(clean)} | clusters: {len(ranked)} | shown: top {TOP_N} (min {MIN_CLUSTER})", ""]
    shown = 0
    for fp, members in ranked:
        if len(members) < MIN_CLUSTER or shown >= TOP_N:
            continue
        shown += 1
        folders = Counter(m["folder"] for m in members)
        banks = Counter(m.get("bank", "?") for m in members)
        inf = members[0].get("univ", {}).get("infer", {})
        # 60/40 build/hold-out split by sha
        members_sorted = sorted(members, key=lambda m: m["sha"])
        cut = int(len(members_sorted) * 0.6)
        build, hold = members_sorted[:cut], members_sorted[cut:]
        lines += [
            f"## Proposal {shown}: fp {fp} — {len(members)} files",
            f"- folders: {dict(folders.most_common(5))}",
            f"- banks(detector): {dict(banks.most_common(5))}",
            f"- infer: {json.dumps({k: v for k, v in inf.items() if k != 'row_keys'}, default=str)[:300]}",
            f"- build {len(build)} / hold-out {len(hold)}: gate results pending (G1-G6 harness)",
            f"- shas: {[m['sha'] for m in members[:25]]}{'...' if len(members) > 25 else ''}",
            ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {report} — {shown} proposals")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["u3a.jsonl", "u3b.jsonl"]))

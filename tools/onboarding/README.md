# tools/onboarding — corpus triage for all-banks onboarding

Read-only measurement of the statement corpus (`Unified All Statements/`).
No product code is touched. Outputs are PII-free: sha8 ids, counts, generic
column labels only. Statement paths live only in `.local/` (gitignored).

## Order

```bash
# 1. coverage map (static): folder -> bank_id, aliases, existing coverage
python tools/onboarding/coverage_map.py

# 2. per-file scan, resumable + shardable (2 lanes uses ~2 CPUs)
python tools/onboarding/scan_meta.py 40000 0 2 &
python tools/onboarding/scan_meta.py 40000 1 2 &

# 3. route probe: v2 shadow, then universal tier on (resumable by sha8)
python tools/onboarding/probe.py shadow 3000      # re-run until done
python tools/onboarding/probe.py universal 3000

# 4. fingerprint-aware representative samples (sha8 only in reports)
python tools/onboarding/samples.py

# 5. analysis -> docs/onboarding/ONBOARDING_QUEUE.csv + .local/bank_stats.json
python tools/onboarding/analyze.py

# 6. narrative report -> docs/onboarding/TRIAGE.md
python tools/onboarding/report.py
```

## Outputs

- `.local/scan_meta_*.jsonl` — per-file scan (gitignored)
- `.local/manifest_*.jsonl` — sha8 → real path (gitignored, never committed)
- `.local/probe_<mode>.jsonl` — route results keyed by sha8
- `.local/samples*.json` — sample picks + local paths
- `docs/onboarding/ONBOARDING_QUEUE.csv` — committed
- `docs/onboarding/TRIAGE.md` — committed

## Conventions

- Locked PDFs are counted, never opened. `passwords.txt` is never read.
- Header fingerprints use a fixed label vocabulary
  (`scan_meta.py:LABELS`), so no free statement text can leak.

# Slice 1: how to run (Docker, Python 3.11)

Branch: `feature/statement-verification-v1`. Nothing here changes production behaviour:
verification is attached to the result as an extra `verification` key and nothing reads it yet.

Run these in PowerShell from `X:\Airco Projects\Airco Insights fintech`.

## 0. Build the backend image once (Python 3.11, existing requirements.txt, no new libraries)

```powershell
docker build -t airco-backend-slice1 .\backend
```

(If you already have the compose-built backend image, you can use its name instead.)

## 1. Synthetic verification tests + the existing test suite

```powershell
docker run --rm -v "${PWD}\backend:/app" -w /app airco-backend-slice1 `
  python -m pytest tests/verification -q
docker run --rm -v "${PWD}\backend:/app" -w /app airco-backend-slice1 `
  python -m pytest tests -q -x --ignore=tests/golden --ignore=tests/mypaisaa
```

Expected: 15 passed for `tests/verification`. For the second command, send me the last 15 lines.

## 2. Golden PDFs (existing regression) if you have them

```powershell
docker run --rm -v "${PWD}\backend:/app" -v "${PWD}\New Dataset\Ready to Use PDF:/samples:ro" `
  -e GOLDEN_SAMPLES_DIR=/samples -w /app airco-backend-slice1 `
  python -m pytest tests/golden -q
```

## 3. Baseline on the corpus (~200 PDFs, 15 per bank, deterministic pick)

Files listed in the move plan (suspected wrong folder) are excluded so wrong-bank files do not pollute the baseline. The dataset is mounted read-only and nothing is moved.

```powershell
New-Item -ItemType Directory -Force .\docs\slice1\out | Out-Null
docker run --rm `
  -v "${PWD}\backend:/app" `
  -v "${PWD}\New Dataset\Ready to Use PDF:/samples:ro" `
  -v "${PWD}\New Dataset\_validation_by_claude:/ref:ro" `
  -v "${PWD}\docs\slice1\out:/out" `
  -w /app airco-backend-slice1 `
  python -m scripts.baseline_run --samples-dir /samples --out-dir /out --per-bank 15 --exclude-csv /ref/MOVE_PLAN_not_executed.csv
```

It is resumable: if it is interrupted, run the same command again. Results appear in `docs\slice1\out\`:
`baseline.csv`, `baseline.jsonl` (full per-check detail), `baseline_summary.md`.

Only the 14 banks that have a processor are run; other bank folders are skipped by the sample discovery.

## One command for everything (recommended)

```powershell
powershell -ExecutionPolicy Bypass -File .\docs\slice1\run_all_slice1.ps1
```

Runs git state, image build, environment capture, verification tests, the full existing suite, golden PDFs, the corpus baseline, then rebuilds the backend container and uploads real PDFs through the running stack (`backend/scripts/e2e_smoke.py`), checking job completion, the new `verification` block in the job result, and the Excel download (9 sheets, unchanged). Use `-SkipStack` to skip the live-stack part. Logs: `docs\slice1\out\logs\`, status table: `docs\slice1\out\RUN_STATUS.txt`.

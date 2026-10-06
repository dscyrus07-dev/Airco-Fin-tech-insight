# MyPaisaa Bank Statement Fetch Pipeline

Retrieves **ALL** bank statements for every user in `New Dataset/PS ids for users.xlsx`
via the MyPaisaa `customerbankdetails` API, downloads them, validates them,
deduplicates them and records full metadata for model training.

A user may have multiple statements pulled at different times — **every** statement
returned by the API is fetched and retained (never "latest only").

```
backend/scripts/mypaisaa_fetch/
├── __main__.py        CLI entry point
├── config.py          env/CLI configuration
├── input_loader.py    CSV/XLSX user-list validation (goalid, ps_month, ps_date kept)
├── api_client.py      async API client: timeouts, retries, exponential backoff
├── parser.py          recursive statement extraction from API responses
├── downloader.py      streaming downloads, SHA-256, dedup, password verification
├── manifest.py        SQLite manifest (restartable state)
├── ratelimit.py       optional global request pacing
├── pipeline.py        orchestration + concurrency + reports
├── report.py          summary / failure reports
└── models.py          data models + status constants
```

---

## 1. Requirements

Python 3.11+ with the backend dependencies already present in
`backend/requirements.txt` (httpx, tenacity, pypdf, openpyxl, python-dotenv).
No extra installs are needed.

## 2. IP whitelist (mandatory)

MyPaisaa only serves this API to whitelisted public IPs:

| Role      | IP              |
|-----------|-----------------|
| Primary   | `123.201.8.65`  |
| Secondary | `171.50.245.234`|

Check the machine's public IP before running (e.g. `curl https://ifconfig.me`).
If it is not one of the two addresses above **the API will not respond** — do not
start the bulk job from another network. The pipeline never attempts to bypass
this restriction.

## 3. Input file

`New Dataset/PS ids for users.xlsx` is the source of truth (12,019 data rows,
columns `goalid`, `userid`, `ps_month`, `ps_date`). The program reads it
directly — no manual copying of IDs.

Validation performed automatically (report written to
`input_validation_report.csv`):

- blank rows ignored, whitespace trimmed
- numeric IDs normalized (`656296.0` → `656296`)
- duplicate user IDs detected; goal IDs from all their rows are merged
- rows with missing/invalid user IDs are reported and skipped
- original file is never modified

Current dataset: **12,020 rows → 7,748 unique users**, 0 missing dates.

CSV files with a `user_id` (or `userid`, `Customer ID`, …) header column are
also accepted.

## 4. Configuration

All settings come from environment variables (see `.env.example` at the repo
root) and can be overridden on the CLI:

| Env var                    | CLI flag                | Default                              |
|----------------------------|-------------------------|--------------------------------------|
| `MYPAAISA_INPUT_FILE`      | `--input`               | `New Dataset/users.csv`              |
| `MYPAAISA_OUTPUT_DIR`      | `--output-dir`          | `New Dataset/bank_statements`        |
| `MYPAAISA_API_BASE_URL`    | –                       | MyPaisaa production endpoint         |
| `MAX_CONCURRENT_USERS`     | `--max-concurrent`      | `5`                                  |
| `REQUESTS_PER_SECOND`      | `--requests-per-second` | `0` (unlimited; concurrency applies) |
| `MAX_RETRIES`              | `--max-retries`         | `3`                                  |
| `BACKOFF_BASE_SECONDS`     | –                       | `2` (2s → 4s → 8s … capped at 60s)   |
| `REQUEST_TIMEOUT_SECONDS`  | `--timeout`             | `60`                                 |
| `CONNECT_TIMEOUT_SECONDS`  | –                       | `15`                                 |

No secrets are required — the API is protected by IP whitelisting only.

## 5. Running

All commands run from `backend/`:

```bash
# 0) validate the input file only (no API calls)
python -m scripts.mypaisaa_fetch --input "../New Dataset/PS ids for users.xlsx" --dry-run

# 1) controlled test: first 10 users only
python -m scripts.mypaisaa_fetch --input "../New Dataset/PS ids for users.xlsx" --limit 10

# 2) full run (resumable — safe to interrupt with Ctrl+C and re-run)
python -m scripts.mypaisaa_fetch --input "../New Dataset/PS ids for users.xlsx"

# 3) reprocess only users/statements that failed
python -m scripts.mypaisaa_fetch --input "../New Dataset/PS ids for users.xlsx" --retry-failed

# 4) re-download everything from scratch (keeps manifest history)
python -m scripts.mypaisaa_fetch --input "../New Dataset/PS ids for users.xlsx" --force
```

Exit code is `0` when everything succeeded, `1` when failures were recorded.

## 6. Output layout

```
New Dataset/bank_statements/
├── manifest.db                  SQLite manifest (ALL state; restartable)
├── input_validation_report.csv  user-list validation
├── users_report.csv             per-user status + goalid/ps_month/ps_date
├── statements_report.csv        per-statement metadata (NO passwords)
├── failed_users.csv             users whose API call failed (latest run)
├── failed_statements.csv        statements that failed (latest run)
├── summary.json                 machine-readable run summary
├── summary_<stamp>.txt          human-readable run summary
├── failed_users_<stamp>.csv     timestamped history
├── failed_statements_<stamp>.csv
└── <userid>/                    one folder per user
    ├── statement_001.pdf
    ├── statement_002.jpg        (some "statements" are photos; extension is
    └── ...                       detected from file content, not the URL)
```

## 7. What gets recorded (manifest)

`users`: user_id, goalids, ps_month, ps_date, api_status
(`success` / `no_statements` / `error`), statements_found, error_message,
retry_count, timestamps.

`statements`: user_id, statement_id (docStore.id), statement_url,
statement_index, filename, original_filename (MyPaisaa `storenode`),
local_path, bank_name, account_type, pulled_at (docStore.createdate),
file_type, file_size, sha256, password_available, password_verified,
download_status, error_message, retry_count, api_fetched_at, downloaded_at.

Download statuses: `downloaded`, `duplicate`, `password_required`,
`password_invalid`, `download_failed`, `download_invalid`, `invalid_url`,
`no_url`.

## 8. Behaviour notes

- **Multiple statements**: every entry in the API `data` array is processed;
  `data: []` is a successful "no statements" user, not an error.
- **Deduplication**: same URL within a user is parsed once; identical file
  content (SHA-256) is stored once and further copies marked `duplicate`.
  Files are never overwritten with different content (a `_1` suffix is used).
- **Download validation**: HTML error pages, XML and empty bodies are rejected
  (`download_invalid`) and never saved as statements. The real file type is
  detected from magic bytes — some uploads are JPEG photos.
- **Passwords**: taken from the API `password` field, stored only inside
  `manifest.db` (gitignored), never logged, never exported to CSV. Encrypted
  PDFs are verified with pypdf: correct password → `downloaded`
  (password_verified=1); wrong → `password_invalid`; missing → `password_required`.
  The file is always kept so it can be re-verified later.
- **Retries**: timeouts/connection errors/HTTP 429/5xx retried with exponential
  backoff; 4xx failures are not retried.
- **Failure isolation**: one user's crash/timeout never stops the batch.
- **Resume**: an interrupted run continues where it stopped — completed users
  and statements are skipped automatically.

## 9. Reports

After every run:

- console summary (users/statements counts)
- `summary.json` + `summary_<stamp>.txt`
- `users_report.csv` — answers "which users have no statements / failed?"
- `statements_report.csv` — answers "how many statements per user, which are
  duplicates / password protected, where is each file?"
- `failed_users.csv` / `failed_statements.csv` — retry worklists

## 10. Security

- Downloaded statements and the manifest are gitignored
  (`New Dataset/bank_statements/`, `bank_statements/`).
- Passwords never appear in logs, CSV reports or console output.
- Statement URLs are logged host-only (presigned query strings are dropped).
- Files are stored with restrictive permissions where the OS supports it.
- Nothing is uploaded anywhere; statements stay on the local machine.

## 11. Tests

```bash
cd backend
python -m pytest tests/mypaisaa -q
```

60 tests cover: input validation (CSV/XLSX, duplicates, blanks, missing IDs,
goal merging), API client (success, empty data, 5xx/429 retries, 4xx
no-retry, timeout, malformed JSON), parser (flat/nested/multi-statement/
password inheritance/duplicate URLs), downloader (valid PDF, dedup by hash,
no-overwrite, password correct/missing/wrong, 404, 500-retry, HTML/empty
rejection, corrupted PDF, JPEG detection) and end-to-end pipeline runs
(single/multi/no statements, resume after interruption, `--retry-failed`,
`--force`, dry-run, `--limit`, 60-user concurrent run, failure isolation,
report generation).

## 13. Results of the production run (2026-10-02)

Full dataset (`PS ids for users.xlsx`) executed from whitelisted IP `123.201.8.65`:

```
Unique users in input:      7,748
Users successful:           2,924
Users with no statements:   2,610
Users with errors:          2,214   (password issues only — files still saved)

Statements discovered:      16,457
Statements downloaded:      11,478   (readable; 3,340 opened with API password)
Duplicates:                     31
Password required (no pw):   3,879   (encrypted PDF, API gave no password)
Password invalid (bad pw):   1,046   (API password did not unlock the PDF)
Download failures:               0
Invalid downloads:              23   (HTML/empty responses rejected)
```

Output: 14,175 files / 4.0 GB under `New Dataset/bank_statements/`
(13,817 PDF, 309 JPG, 24 PNG — extensions verified from file content).
Every statement record is in `statements_report.csv` with its `local_path`.

The 4,925 password-affected statements are **saved on disk** and listed in
`failed_statements.csv`; they can be re-verified automatically if MyPaisaa
provides correct passwords (`--retry-failed` re-checks locally without
re-downloading).

## 14. Troubleshooting

| Symptom                                  | Meaning / fix                                             |
|------------------------------------------|-----------------------------------------------------------|
| HTTP 403 on every request                | This machine's public IP is not whitelisted — stop.       |
| Many `download_failed` after running fine| Presigned URLs expire after 24 h; re-run `--retry-failed`.|
| `password_invalid` rows                  | API-stored password doesn't unlock the PDF; file is kept, re-run later if MyPaisaa supplies better passwords. |
| Run interrupted                          | Just run the same command again — it resumes.             |
| Want to re-verify passwords only         | `--retry-failed` re-verifies locally without re-downloading.|

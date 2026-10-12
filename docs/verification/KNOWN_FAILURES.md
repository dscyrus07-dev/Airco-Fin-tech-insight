# Known test failures (not caused by Slice 1 or Slice 2)

Measured on 6 Oct 2026 by running the same tests with and without our changes (`docs/slice1/out/logs/04b_*`, `05b_*`): the failing lists were identical.
The machine-readable list is `known_failures.txt`; `run_slice2b.ps1` fails on any failure that is not in it.

| Test | Class | Cause / next step |
|---|---|---|
| `test_axis_parser` x2, `test_canara_parser`, `test_icici_parser` | ENVIRONMENT (unconfirmed) | They open PDFs from `/samples/New Bank Samples Results/...`, a path that does not exist in the container. Mount that folder (or point the tests at `New Dataset`) and re-run to see whether they are real failures. |
| `test_finbit_analytics` x2 | PRE-EXISTING | Unrelated to verification or detection. Needs an owner. |
| `test_json_rule_engine` x2 | PRE-EXISTING | HDFC JSON rule engine vs legacy tables. Needs an owner. |
| `test_api_key_service ... rate_limit_allows_then_blocks` | PRE-EXISTING | Likely needs Redis or timing. |
| `tests/test_pipeline_orchestrator.py` | PRE-EXISTING (collection error) | Imports `_tag_as_others`, which no longer exists in `pipeline_orchestrator.py`. Stale test or removed function. |
| golden `test_golden_snapshots_against_live_pipeline` | PRE-EXISTING | `910010002434549_1661418866251.json`: category assignment mismatch. Decide whether the snapshot or the rules are right. |

Total: 9 failed tests, 1 collection error, 1 golden failure.

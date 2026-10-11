# Demo Script — 15 minutes

Prep: stack up per `comparison/demo/RUNBOOK.md`, flags `MODE=serve`, `SERVE_BANKS=hdfc`.
Browser: `http://localhost:3000` — sign in with the dev-realm account (see RUNBOOK).
Candidate statements (user picks which may be shown; sha8 + folder only):

| sha8 | folder | role in demo |
|---|---|---|
| `0000d106` | HDFC Bank | the verified-engine hero |
| `0034814d` | SBI | legacy, everyday path |
| `00c09764` | ICICI Bank | legacy |
| `000df35f` | Axis Bank | largest statement (1,147 rows) |
| `00196b23` | Bank of Baroda | the deliberate "needs review" moment |

## 1. Landing + login (1 min)

Home → sign in → dashboard. Say: "The product analyzes statements only after
detecting the bank and layout — nothing is processed on a guess."

## 2. HDFC — the verified engine (4 min)

Analyze → upload the HDFC file → click **Analyze**.
Say: "It detected HDFC Bank with high confidence — look at the evidence chips:
IFSC in the header, bank domain. This is the 'why' we can show customers."
Confirm → Process → when it completes, download the Excel and open the
**Statement Check** sheet: `Engine: v2`, `Verdict: VERIFIED`,
`Independently verified: yes`. Say: "Verified means the numbers were checked
independently of the parser — not just extracted."

## 3. SBI + ICICI — the everyday path (4 min)

Upload both, analyze, confirm, process. Say: "These run the current production
engine today — byte-identical to what customers already get. The new engine is
switched on bank-by-bank, only after proof." Download one Excel; show Summary +
Transactions sheets.

## 4. Axis — scale (2 min)

Process the 1,147-row Axis file. Say: "Same flow at a thousand rows — no
different code path."

## 5. Bank of Baroda — deliberate "needs review" (3 min)

Upload the BoB file → it lands in **REVIEW** (low-confidence detection).
Say: "This is the safe path working: when the detector isn't sure, the product
asks instead of guessing. If you override and process anyway, the bank's own
validation still refuses a file it can't prove — no silent wrong answers."

## 6. Dashboard (1 min)

Show the job list; note the engine badges where data exists.

## What NOT to show

- Other-bank overrides succeeding silently (legacy gap — under review, see report).
- Locked/passworded PDFs (out of scope).
- The ~30 unsupported folders — if asked: "unsupported files are refused
  cleanly at the document gate; they never reach the parser."

## Reset procedure

```bash
python comparison/demo/reset_demo.py   # clears the demo user's history
```

## Fallback if a service dies

```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.local.yml --env-file local.env up -d backend   # or frontend / keycloak
```

If Keycloak dies: restart `keycloak` + `keycloak-postgres`, re-login.
If everything is down: the screenshots under `comparison/demo/private/shots/`
cover every step of this script.

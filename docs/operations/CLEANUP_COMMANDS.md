# Cleanup Commands (owner-run; N8 did NOT execute these)

Generated on branch `devin/n8-compliance-hygiene`. Each command was verified
read-only (merge status, worktree attachment). **Review before running** — a
merged branch is safe to delete; its commits remain reachable from
`integration/v2-waves`.

Run from the main worktree: `X:\Airco Projects\Airco Insights fintech`

## 1. Already executed by N8 (recorded for the log)

```
docker rmi onb-backend:pr1 onb-frontend:pr1     # unused onb tags  (~0.1GB unique)
docker builder prune -af                        # build cache      (~35.7GB)
docker image prune -f                           # dangling images  (0B — none)
```

Result: ~35.8GB reclaimed. No volumes, containers, protected-stack images or
corpus paths touched.

## 2. Worktrees whose branches are MERGED into `integration/v2-waves`

For each: remove the worktree first, then delete the branch.

```bat
git worktree remove "X:/Airco Projects/wt-ca"      && git branch -d devin/cleanup-audit
git worktree remove "X:/Airco Projects/wt-final"   && git branch -d devin/final-rc
git worktree remove "X:/Airco Projects/wt-pii"     && git branch -d devin/pii-fixtures
git worktree remove "X:/Airco Projects/wt-pr1"     && git branch -d devin/promote-1
git worktree remove "X:/Airco Projects/wt-ro"      && git branch -d devin/rollout-1
git worktree remove "X:/Airco Projects/wt-sc"      && git branch -d devin/test-typing
git worktree remove "X:/Airco Projects/wt-ui"      && git branch -d devin/ui-banks
git worktree remove "X:/Airco Projects/wt-ub"      && git branch -d devin/unblock-1
git worktree remove "X:/Airco Projects/wt-univ"    && git branch -d devin/universal
git worktree remove "X:/Airco Projects/wt-v2"      && git branch -d devin/verify-2
git worktree remove "X:/Airco Projects/wt-v3"      && git branch -d devin/verify-3
git worktree remove "X:/Airco Projects/wt-wave10"  && git branch -d devin/wave10
git worktree remove "X:/Airco Projects/wt-w11"     && git branch -d devin/wave11
git worktree remove "X:/Airco Projects/wt-trackA"  && git branch -d devin/wave6
git worktree remove "X:/Airco Projects/wt-trackB"  && git branch -d devin/wave8
git worktree remove "X:/Airco Projects/Airco Insights fintech/wt-demo" && git branch -d demo/rc
```

## 3. Merged branches with no worktree (delete only)

```bat
git branch -d claude/onboard-fix devin/onboard-all devin/onboard-verify devin/onboard-wire devin/safe-cleanup devin/wave1 devin/wave2 devin/wave3 feature/statement-engine-v2-foundation feature/statement-verification-v1 trial/cleanup-probe
```

Keep `main` (merged but is the trunk) and `integration/v2-waves` itself.

## 4. Detached-HEAD worktrees (no branch; remove if done with them)

```bat
git worktree remove "X:/Airco Projects/Airco Insights fintech/wt-audit"
git worktree remove "X:/Airco Projects/Airco Insights fintech/wt-p8c"
git worktree remove "X:/Airco Projects/Airco Insights fintech/wt-w11clean"
git worktree remove "X:/Airco Projects/wt-base"
git worktree remove "X:/Airco Projects/wt-guard"
git worktree remove "X:/Airco Projects/wt-pr1base"
git worktree remove "X:/Airco Projects/wt-v26base"
git worktree remove "X:/Airco Projects/wt-v3base"
git worktree prune      :: drops stale session worktrees already marked prunable
```

## 5. Do NOT remove (unmerged or active work)

Branches NOT merged into `integration/v2-waves` — removing loses work:
`devin/n1-engine-headers`, `devin/n2-engine-tables`, `devin/n3-engine-grouped`,
`devin/n4-engine-audit`, `devin/n5-bank-wave`, `devin/n6-legacy-vs-v2`,
`devin/n8-compliance-hygiene` (this branch), `devin/onboarding-triage`,
`devin/unified-entry`, `devin/guard-verify`, `devin/wave4`, `devin/wave5`
(main checkout), `devin/wave9`, and their worktrees
(`wt-n1`…`wt-n8`, `wt-trackA` equivalents, `wt-ue`, `wt-gv`, `wt-wave9b`).

## 6. Protected — never touch

- Containers/images/volumes of `airco_*`, `keycloak*`, `ue_*`, `demo_*`
  (incl. the four `ue_*` exited containers and `postgres:15` for keycloak).
- Anything under `Unified All Statements` / corpus folders.
- `.env` files (they hold live credentials; rotate, don't delete).

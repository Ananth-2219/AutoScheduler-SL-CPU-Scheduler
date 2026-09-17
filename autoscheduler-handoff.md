# AutoScheduler Handoff

## Current State

Repository: `/Users/knightnm/Documents/AutoScheduler-SL-CPU-Scheduler`

Implementation now includes:

- CPU/I/O burst event simulation
- FCFS, SJF, Round Robin, and Priority Scheduling adapters
- Extended metrics and seeded workload profiles
- Oracle labeling, decision-tree training, adaptive selection, CLI evaluation
- 17 passing tests

Read project details and commands in:

- `/Users/knightnm/Documents/AutoScheduler-SL-CPU-Scheduler/README.md`
- `/Users/knightnm/Documents/AutoScheduler-SL-CPU-Scheduler/results/REPORT.md`
- `/Users/knightnm/Documents/AutoScheduler-SL-CPU-Scheduler/results/summary.json`

## Verified Experiment Result

Default training: 2,500 workloads. Held-out evaluation: 1,000 workloads.

- Decision-tree test accuracy: 81.3%
- Held-out accuracy: 80.0%
- Best static policy: SJF, weighted score 0.2556
- Adaptive weighted score: 0.2556
- Oracle score: 0.2370
- Mean regret: 0.0187

Adaptive selected SJF for all 1,000 held-out workloads. Do not claim adaptive improvement over SJF.

## Recommended Next Work

Run a diagnostic experiment before adding UI, RL, online switching, or more schedulers.

1. Add oracle-label distribution by workload profile.
2. Add confusion matrix, feature importance, and per-policy regret.
3. Compare every model against constant-SJF baseline.
4. Replace classifier-only training with four supervised score regressors, one per policy; select lowest predicted score.
5. Keep current oracle, held-out seeds, and static baselines unchanged for comparison.

Use RL only if scope changes to repeated dispatch decisions with delayed rewards. Current one-selection-per-workload simulator has oracle labels, so supervised learning is lower-risk and more interpretable.

## Workspace Notes

- Worktree has implementation changes not committed.
- Preserve unrelated untracked `.claude/`, `CLAUDE.md`, and `graphify-out/` content.
- Local `.venv/`, `.cache/`, model binary, raw CSV, and raw evaluation CSV are ignored.
- Dependencies: `scikit-learn`, `matplotlib`; install with `pip install -r requirements.txt` inside `.venv`.
- Error notes were logged in `~/Vault/Errors/` for RTK interpreter usage, Matplotlib headless execution, unittest discovery, and sandboxed pip network access.

## Suggested Skills

- `agent-skills:using-agent-skills` to select workflow
- `agent-skills:spec-driven-development` before changing learning objective
- `agent-skills:incremental-implementation` for diagnostics/regression slices
- `agent-skills:test-driven-development` for new metrics and model tests
- `agent-skills:code-review-and-quality` before completion
- `ponytail:ponytail` to prevent unnecessary RL/UI expansion

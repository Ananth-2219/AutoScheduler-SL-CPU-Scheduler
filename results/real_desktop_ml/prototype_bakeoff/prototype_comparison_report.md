# Prototype Action-Cost Bake-off Report

## Status

Development-only offline replay screening. This is not evidence of Linux kernel scheduler performance.

## Data

- Label provenance: `pilot_offline_replay_development_only`
- Action rows (train / validation / locked test): 345 / 85 / 85
- Traces (train / validation / locked test): 4 / 1 / 1

## Selection

- Model: **Ridge** with `{"alpha": 0.01}`
- Validation realized cost: `0.000000`
- Locked-test realized cost: `0.000000`

The model receives an observed state plus one proposed action, predicts that action's cost, then selects the action with the smallest prediction.

## Locked-test comparators

| Choice | Mean offline replay cost |
| --- | ---: |
| Fixed FCFS | 0.821429 |
| Fixed Round Robin | 0.088219 |
| Fixed Priority | 0.821429 |
| Fixed Priority RR | 0.514733 |
| Fixed MLFQ | 0.000000 |
| Per-state oracle | 0.000000 |
| Selected Ridge | 0.000000 |

## Interpretation

The pilot has only one trace in its locked test split. Its replay-cost labels are insufficient for a model or policy claim. Re-run this report after the full grouped Linux collection; only then apply the frozen improvement, confidence, latency, and fairness gates.

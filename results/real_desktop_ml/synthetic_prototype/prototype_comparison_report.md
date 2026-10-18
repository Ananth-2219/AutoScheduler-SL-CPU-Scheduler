# Prototype Action-Cost Bake-off Report

## Status

Development-only offline replay screening. This is not evidence of Linux kernel scheduler performance.

## Data

- Label provenance: `synthetic_development_only`
- Action rows (train / validation / locked test): 7900 / 1565 / 1370
- Traces (train / validation / locked test): 180 / 60 / 60
- Profiles: `['batch', 'cpu_intensive', 'interactive', 'io_intensive', 'mixed']`
- Processes / events: 3240 / 31335
- Seeds: `{'split': 7001, 'model_tuning': 7002, 'bootstrap': 7003, 'generation': [9001]}`
- Cleaning: completed traces are anonymized before feature extraction; action rows are group-split by application, scenario, and capture session.
- Limitation: synthetic data tests the pipeline only and cannot establish a real scheduler result.

## Feature method

At each decision time, every feature is calculated only from events strictly before that time. The model receives these observed-history features plus a one-hot proposed action:

`arrivals_seen`, `ready_count`, `blocked_count`, `running_count`, `wait_mean_ms`, `wait_p95_ms`, `observed_service_mean_ms`, `observed_service_variance_ms2`, `completed_burst_mean_ms`, `completed_burst_variance_ms2`, `io_returns`, `priority_mean`, `priority_variance`, `context_switches`, `wakeups`, `cpu_busy_fraction`.

## Selection

- Model: **Histogram Gradient Boosting** with `{"learning_rate": 0.1, "max_iter": 100, "max_leaf_nodes": 7}`
- Validation realized cost: `0.161176`
- Locked-test realized cost: `0.185541`

The model receives an observed state plus one proposed action, predicts that action's cost, then selects the action with the smallest prediction.

## Locked-test comparators

| Choice | Mean offline replay cost |
| --- | ---: |
| Fixed FCFS | 0.230544 |
| Fixed Round Robin | 0.185991 |
| Fixed Priority | 0.257400 |
| Fixed Priority RR | 0.750452 |
| Fixed MLFQ | 0.185556 |
| Per-state oracle | 0.183600 |
| Selected Histogram Gradient Boosting | 0.185541 |

## Model comparison

Cost MAE and R² evaluate cost prediction. Action-selection accuracy is agreement with the lowest-cost action for each observed state; it is not a classifier training accuracy.

| Model | Validation cost | Locked-test cost | Cost MAE | Cost R² | Oracle-action agreement | P99 ms | Selected |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Dummy | 0.205613 | 0.230544 | 0.170031 | -0.00023467949643030117 | 0.058 | 0.053334 | No |
| Ridge | 0.162158 | 0.185556 | 0.032252 | 0.9654775582856391 | 0.489 | 0.270250 | No |
| Decision Tree | 0.162158 | 0.185556 | 0.027688 | 0.9681267777212215 | 0.489 | 0.124459 | No |
| Random Forest | 0.161848 | 0.185881 | 0.019508 | 0.9816968996018335 | 0.438 | 7.075917 | No |
| Histogram Gradient Boosting | 0.161176 | 0.185541 | 0.021890 | 0.9796401439685292 | 0.496 | 21.594625 | Yes |

## Interpretation

This synthetic dataset exercises the full report pipeline. Its results are not a real-workload or Linux-kernel claim.

# AutoScheduler: Workload-Adaptive CPU Scheduling Simulator

AutoScheduler is a single-CPU research simulator that compares FCFS, SJF,
Round Robin, and Priority Scheduling, then uses an offline-trained decision tree
to select one algorithm for a new workload.

The project is a simulator, not an operating-system kernel scheduler.

## Features

- Backward-compatible single CPU-burst processes
- Alternating CPU and I/O bursts with blocked-process events
- Deterministic FCFS, SJF, Round Robin, Priority, and Priority-RR policies
- Interactive, batch, CPU-intensive, I/O-intensive, and mixed workloads
- Waiting, response, turnaround, utilization, throughput, idle-time, makespan,
  context-switch, switch-time, and maximum-wait metrics
- Consistent five-policy ML labels and static baseline evaluation
- Offline decision-tree training and held-out evaluation
- CLI comparison tables, timelines, CSV data, JSON summaries, and PNG charts

## Setup

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

Run the original Phase 1 demonstration:

```bash
python main.py
```

Tune Priority-RR, generate 2,500 five-policy oracle labels, and train the model:

```bash
python main.py train
```

Compare all static policies with the adaptive selection:

```bash
python main.py compare --profile mixed --seed 42
```

Evaluate 1,000 unseen workloads and write `results/` artifacts:

```bash
python main.py evaluate
```

Measure scheduler decision latency across small, medium, and large workloads:

```bash
python main.py latency
```

Train and evaluate safe adaptive routing across changing three-phase workloads:

```bash
python main.py dynamic-train
python main.py dynamic-evaluate
```

Run the corrected experiment without replacing historical results:

```bash
python main.py train --model results/five_policy_consistent/model.joblib --dataset results/five_policy_consistent/training.csv
python main.py evaluate --model results/five_policy_consistent/model.joblib --output results/five_policy_consistent
python main.py latency --model results/five_policy_consistent/model.joblib --score-summary results/five_policy_consistent/summary.json --output results/five_policy_consistent
```

Use `python main.py <command> --help` to override sample counts, seeds, paths,
or comparison workload size.

## Architecture

- `scheduler/`: stable policy entry points
- `simulator/`: process model, shared event engine, and metrics
- `autoscheduler/workloads.py`: seeded synthetic workload generation
- `autoscheduler/features.py`: pre-simulation feature extraction
- `autoscheduler/evaluation.py`: static comparison and weighted oracle scoring
- `autoscheduler/dataset.py`: labeled CSV dataset generation
- `autoscheduler/model.py`: decision-tree tuning and persistence
- `autoscheduler/adaptive.py`: one-time workload classification and execution
- `autoscheduler/experiments.py`: held-out evaluation and artifacts
- `autoscheduler/dynamic.py`: state-preserving epoch routing and dynamic experiments
- `autoscheduler/cli.py`: train, compare, evaluate, and latency commands

## Workload Profiles

| Profile | Main behavior |
|---|---|
| Interactive | Short CPU bursts with repeated I/O waits |
| Batch | Long jobs arriving in compact groups |
| CPU-intensive | Long CPU bursts with little I/O |
| I/O-intensive | Many short CPU bursts separated by longer I/O waits |
| Mixed | Per-process mixture of the other four profiles |

Every generator uses a local seeded random source. Identical profile, seed, and
process count produce identical workloads.

## Model Inputs

The classifier receives only information available before scheduling:

- Process count and arrival rate
- Total CPU-burst mean and variance
- Short-job ratio
- Priority mean and variance
- Mean I/O frequency
- I/O-to-CPU time ratio

Post-simulation metrics are never classifier inputs.

## Oracle Score

ML training labels and held-out evaluation use the same five policies: FCFS,
SJF, Round Robin, Priority, and Priority-RR. Priority-RR is tuned on deterministic
seed-42 development workloads, then its configuration is frozen before label
generation and unseen evaluation.

| Metric | Weight |
|---|---:|
| Mean waiting time | 30% |
| Mean response time | 25% |
| Mean turnaround time | 20% |
| CPU-utilization penalty | 15% |
| Throughput penalty | 10% |

The default dataset has 500 workloads per profile. Training uses a seeded,
stratified 70/15/15 train, validation, and test split. Tuning changes only tree
depth and minimum leaf size. It selects the candidate with the lowest validation
mean regret (then lower depth, then larger leaf size), rather than highest
classification accuracy. The best global static comparator is selected from
validation rows and frozen before held-out evaluation.

## Evaluation

Default evaluation uses 200 unseen workloads per profile with a separate seed.
Reports include classification accuracy, score regret against the oracle,
inference time, per-profile summaries, all static baselines, adaptive score, and
oracle score. It also writes `confusion_matrix.csv`, `feature_importance.csv`,
and `diagnostics.png`, alongside `evaluation.csv`, `summary.json`, and
`scores.png`.

`summary.json` records oracle and selected-policy distributions per profile,
the oracle-versus-selected confusion matrix, and mean score/regret for each
static policy, constant SJF, adaptive selection, and the oracle. Adaptive success
requires a lower paired mean score than the frozen static comparator and a 95%
bootstrap confidence interval whose upper bound is below zero. The report uses
10,000 paired resamples with seed 2027, overall and per workload profile. Score
weights remain fixed; changing them requires a separate findings review.

`fairness_metrics.csv` and `fairness.png` report pooled process behavior without
changing scores: P95 and maximum wait, starvation count, priority-class delay,
and post-I/O response delay. Starvation means waiting more than three times a
process's total CPU time. Priority delay covers classes 1 and 2.

`python main.py latency` writes `latency.csv`, `latency_summary.json`, and
`latency.png`. It measures next-ready-process selection for SJF, Round Robin,
Priority, and Priority-RR, and feature extraction plus model inference for
Adaptive. CPU execution and metric aggregation are excluded from timed samples.
Every policy must have P99 decision latency strictly below 10 ms for small (12),
medium (100), and large (1,000) workloads. Among gate passers, the lowest
validation-frozen static policy is recommended unless Adaptive passes both the
paired statistical gate and every latency gate.

Priority-RR tuning evaluates nine validation-only settings: quantums `1`, `2`,
`4` and aging intervals `4`, `8`, `12`. It promotes I/O-returning processes one
priority class and charges one tick for each process switch. It passes only when
held-out mean score and maximum individual waiting time are both strictly lower
than SJF.

The corrected experiment is under `results/five_policy_consistent/`. Root-level
results are historical four-policy/five-policy-mismatch artifacts and are not
the primary research evidence. Corrected evidence recommends Round Robin; the
adaptive selector does not beat it.

## Dynamic Routing Experiment

`dynamic-train` creates traces with three distinct workload cohorts injected at
simulated times `0`, `20`, and `40`. Existing processes continue running, so a
policy change must preserve remaining CPU work, I/O events, priority, wait
history, and completed work. Reviews occur at fixed epochs but take effect only
at a dispatch boundary, preserving non-preemptive policy behavior.

The router starts with Round Robin. It observes ready and blocked queue state,
remaining CPU work, priorities, recent arrivals, and I/O returns. A decision
tree selects among all five policies. Low-confidence or dwell-time-blocked
decisions keep the active policy.

Training labels run a next-epoch counterfactual from the same state for every
static policy, then complete each trial with Round Robin. `dynamic-train` tunes
epoch length `{5, 10, 20}`, dwell time `{1, 2, 3}` epochs, and confidence
threshold `{0.0, 0.6, 0.8}` on seed-42 development traces. It selects lowest
P95 response among candidates whose paired weighted-score confidence interval
is not worse than Round Robin, then freezes the configuration.

`dynamic-evaluate` writes `dynamic_evaluation.csv`, `dynamic_summary.json`, and
`dynamic_diagnostics.png`. Success requires a negative paired 95% confidence
interval for Adaptive-minus-RR P95 response, a non-positive upper confidence
limit for weighted-score difference, and a full routing-path P99 below 10 ms.

Run tests with:

```bash
python -m unittest discover -v
```

## Research Interpretation

The experiment must report observed results, including negative or mixed
results. A high classifier accuracy alone does not prove better scheduling.
Primary evidence is adaptive weighted score and paired difference against the
validation-frozen static comparator, plus the per-workload oracle and latency
gate. Do not expand ML when the statistical or latency gate fails. Publish the
negative result or conduct a separately specified objective review.

Suggested paper sections: Methodology, Simulator Design, Workload Generation,
Feature Engineering, Oracle Labeling, Model Training, Experimental Setup,
Results, Discussion, Limitations, and Conclusion.

## Limitations

- Single simulated CPU only
- One algorithm selected before each workload; no mid-run switching
- Offline retraining only
- Synthetic workloads, not kernel traces
- No multicore affinity, deadlines, cache effects, or burst prediction
- Switch cost is simulated only for Priority-RR; it is not kernel timing
- Priority is not part of the weighted objective, so Priority Scheduling may
  rarely be the oracle winner

# AutoScheduler: Workload-Adaptive CPU Scheduling Simulator

AutoScheduler is a single-CPU research simulator that compares FCFS, SJF,
Round Robin, and Priority Scheduling, then uses an offline-trained decision tree
to select one algorithm for a new workload.

The project is a simulator, not an operating-system kernel scheduler.

## Features

- Backward-compatible single CPU-burst processes
- Alternating CPU and I/O bursts with blocked-process events
- Deterministic FCFS, SJF, Round Robin, and Priority policies
- Interactive, batch, CPU-intensive, I/O-intensive, and mixed workloads
- Waiting, response, turnaround, utilization, throughput, idle-time, makespan,
  and context-switch metrics
- Oracle labels based on all four algorithms
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

Generate 2,500 oracle-labeled workloads and train the model:

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
- `autoscheduler/cli.py`: train, compare, and evaluate commands

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

Each workload runs under all four algorithms. Metrics are min-max normalized
within that workload. Lower score is better.

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
classification accuracy.

## Evaluation

Default evaluation uses 200 unseen workloads per profile with a separate seed.
Reports include classification accuracy, score regret against the oracle,
inference time, per-profile summaries, all static baselines, adaptive score, and
oracle score. It also writes `confusion_matrix.csv`, `feature_importance.csv`,
and `diagnostics.png`, alongside `evaluation.csv`, `summary.json`, and
`scores.png`.

`summary.json` records oracle and selected-policy distributions per profile,
the oracle-versus-selected confusion matrix, and mean score/regret for each
static policy, constant SJF, adaptive selection, and the oracle. The adaptive
phase passes only when its held-out mean score is *strictly lower* than constant
SJF (`adaptive_beats_sjf` and `eligible_for_next_adaptive_phase` are both true).
The score weights are fixed for this experiment; changing them requires a
separate written findings review.

The checked-in experiment summary is available at `results/REPORT.md`. Current
evidence shows that the trained selector matches, but does not beat, static SJF.

Run tests with:

```bash
python -m unittest discover -v
```

## Research Interpretation

The experiment must report observed results, including negative or mixed
results. A high classifier accuracy alone does not prove better scheduling.
Primary evidence is adaptive weighted score and regret compared with the best
global static algorithm, constant SJF, and the per-workload oracle. Do not
expand adaptive scheduling when the strict SJF pass rule fails; report the
negative result or conduct a separate score-review study first.

Suggested paper sections: Methodology, Simulator Design, Workload Generation,
Feature Engineering, Oracle Labeling, Model Training, Experimental Setup,
Results, Discussion, Limitations, and Conclusion.

## Limitations

- Single simulated CPU only
- One algorithm selected before each workload; no mid-run switching
- Offline retraining only
- Synthetic workloads, not kernel traces
- No multicore affinity, deadlines, cache effects, or real context-switch cost
- Priority is not part of the weighted objective, so Priority Scheduling may
  rarely be the oracle winner

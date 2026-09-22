# AutoScheduler: Workload-Adaptive CPU Scheduling Simulator

AutoScheduler is a single-CPU research simulator that compares FCFS, SJF, SRTF,
Round Robin, Priority, and Priority-RR, then uses an offline-trained decision tree
to select one algorithm for a new workload.

The project is a simulator, not an operating-system kernel scheduler.

## Features

- Backward-compatible single CPU-burst processes
- Alternating CPU and I/O bursts with blocked-process events
- Deterministic FCFS, non-preemptive SJF, preemptive SRTF, Round Robin, Priority, and Priority-RR policies
- Interactive, batch, CPU-intensive, I/O-intensive, and mixed workloads
- Waiting, response, turnaround, utilization, throughput, idle-time, makespan,
  context-switch, switch-time, and maximum-wait metrics
- Consistent six-policy ML labels and static baseline evaluation
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

Open interactive presentation menu:

```bash
python main.py demo
```

Use `python main.py demo --no-color` for redirected output or terminals without
ANSI color support. Menu runs only short live comparisons and reads completed
research artifacts; it never starts full training or evaluation automatically.
Choose option `10` for an animated six-policy scheduler race on one generated
workload. Playback is shortened, but final metrics use complete timelines.

Run the original Phase 1 demonstration:

```bash
# Run the demo
python main.py

# Run the test suite
python -m unittest discover -s tests
```

Tune Priority-RR, generate 2,500 six-policy oracle labels, and train the model:

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

Evaluate fixed MLFQ and its decision latency:

```bash
python main.py mlfq-evaluate
python main.py mlfq-latency
```

Run a six-policy experiment without replacing historical results:

```bash
python main.py train --model results/six_policy/model.joblib --dataset results/six_policy/training.csv
python main.py evaluate --model results/six_policy/model.joblib --output results/six_policy
python main.py latency --model results/six_policy/model.joblib --score-summary results/six_policy/summary.json --output results/six_policy/full_latency
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
- `autoscheduler/benefit.py`: observed-state RR-to-SRTF benefit regression
- `autoscheduler/mlfq_experiment.py`: static MLFQ comparison and decision gates
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

ML training labels and held-out evaluation use the same six policies: FCFS,
SJF, SRTF, Round Robin, Priority, and Priority-RR. SJF chooses by total CPU
`burst_time` without preemption. SRTF chooses by the current CPU burst's
`remaining_time` and preempts only for a strictly shorter ready burst at a
new arrival or I/O completion. Priority-RR is tuned on deterministic
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
`latency.png`. It measures next-ready-process selection for SJF, SRTF, Round Robin,
Priority, and Priority-RR (including SRTF event preemption checks), and feature extraction plus model inference for
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

The historical corrected five-policy experiment is under `results/five_policy_consistent/`.
Six-policy results are stored separately under `results/six_policy/`; scores
cannot be compared directly across these sets because normalization depends on
the candidates. Previously saved models must be retrained for the new policy set. Root-level
results are historical four-policy/five-policy-mismatch artifacts and are not
the primary research evidence. Corrected evidence recommends Round Robin; the
adaptive selector does not beat it.

With six policies (training seed 42, 2,500 workloads; evaluation seed 2026,
1,000 workloads), Round Robin has mean score 0.13221, SRTF 0.16773, and
Adaptive 0.13188. The paired Adaptive-minus-frozen-static 95% interval crosses
zero, so the adaptive statistical gate remains false. Full six-policy latency
results are in `results/six_policy/full_latency/`: seed 3030, 20 measured
samples per profile, five warmups, and P99 below 10 ms for every measured
policy at every size. Large-workload P99 is 0.0611 ms for Round Robin and
6.5507 ms for Adaptive. Round Robin remains recommended. The separate
one-sample latency smoke artifacts remain in `results/six_policy/`.

## Dynamic Routing Experiment

`dynamic-train` creates traces with three distinct workload cohorts injected at
simulated times `0`, `20`, and `40`. Existing processes continue running, so a
policy change must preserve remaining CPU work, I/O events, priority, wait
history, and completed work. Reviews occur at fixed epochs but take effect only
at a dispatch boundary. SRTF can interrupt its own running burst at an
arrival or I/O return; policy changes still wait for a dispatch boundary.

The router starts with Round Robin. It observes ready and blocked queue state,
remaining CPU work, priorities, recent arrivals, and I/O returns. A decision
tree selects among all six policies. Low-confidence or dwell-time-blocked
decisions keep the active policy.

Training labels run a next-epoch counterfactual from the same state for every
static policy, then complete each trial with Round Robin. `dynamic-train` tunes
epoch length `{5, 10, 20}`, dwell time `{1, 2, 3}` epochs, and confidence
threshold `{0.0, 0.6, 0.8}` on seed-42 development traces. It selects lowest
P95 response among candidates whose paired weighted-score confidence interval
is not worse than Round Robin, then freezes the configuration.
Dynamic training and tuning now split by trace seed: all epochs from one trace
stay together across the 70/15/15 train, validation, and test trace groups.
The saved dynamic model predates this split and has not been retrained; its
reported accuracy and regret are not leakage-corrected evidence.

`dynamic-evaluate` writes `dynamic_evaluation.csv`, `dynamic_summary.json`, and
`dynamic_diagnostics.png`. Success requires a negative paired 95% confidence
interval for Adaptive-minus-RR P95 response, a non-positive upper confidence
limit for weighted-score difference, and a full routing-path P99 below 10 ms.
On the 1,000-trace six-policy evaluation (seed 2026), the P95 response gate
fails, so dynamic routing is ineligible despite passing the other two gates.

## RR-versus-SRTF Benefit Experiment

This conservative experiment starts with a development-tuned Round Robin
quantum, observes only runtime state for 5, 10, or 20 ticks, then either keeps
RR or switches once to SRTF. The decision-tree regressor predicts
`SRTF score - RR score`; SRTF is chosen only when the prediction clears the
validation-tuned safety margin. Features exclude future arrivals, declared
total CPU/I/O work, and true remaining burst time.

```bash
python main.py benefit-train
python main.py benefit-evaluate
python main.py benefit-latency
```

Training uses seed 42 with trace-disjoint 70/15/15 splits. Evaluation uses
1,000 unseen workloads from seed 4040 and 10,000 paired bootstrap samples from
seed 4041. Scores use bounds frozen by the original six static policies, so
adding the selector cannot change RR's normalized score. Latency uses 12, 100,
and 1,000-process workloads, 20 measured samples per profile, and five warmups.

The ML selector is eligible only if it lowers mean score by at least 1% versus
tuned RR, its paired 95% confidence interval is entirely below zero, and every
decision-latency P99 is below 10 ms. RR remains the recommendation when any
gate fails. Artifacts are written to `results/rr_srtf_benefit/`; prior static
and dynamic results are preserved.

Seed-4040 result: RR quantum 1, observation window 20, and margin 0.0025 were
selected. Mean score fell from 0.111959 for tuned RR to 0.037037 (66.92%);
the paired difference was -0.074922 with 95% CI [-0.077475, -0.072355]. The
largest measured P99 was 0.358896 ms, so all three gates pass. However, the
model selected SRTF for 98.1% of workloads. This proves the observed
RR-then-SRTF policy beats RR under the synthetic objective, but does not yet
prove ML is necessary; a fixed switch-at-20 hybrid is the next required
baseline.

## Static MLFQ Baseline

MLFQ uses three FIFO queues with quanta `(2, 4, 8)`. New and I/O-returning
processes enter the top queue. Full quantum use moves a process down; waiting
20 ticks moves it up. Higher queues preempt lower queues while preserving the
interrupted process's unused quantum.

`mlfq-evaluate` compares MLFQ with tuned RR, direct SRTF, and fixed
RR-for-20-ticks-then-SRTF. It uses 1,000 seed-6060 synthetic workloads with
randomized process counts and the original frozen six-policy score bounds.
These workloads are more varied synthetic tests, not real kernel traces.
`mlfq-latency` uses seed 6062, 20 samples per profile, five warmups, and
12/100/1,000-process workloads.

Seed-6060 result: RR-20-SRTF wins with mean score `0.089107`. Tuned RR scores
`0.124592`, MLFQ scores `0.131408`, and SRTF scores `0.174703`. MLFQ loses all
five profiles, has pooled P95 wait `448` versus RR's `446`, and therefore fails
score and fairness gates. All policies pass strict P99 `<10 ms`; MLFQ large
P99 is about `0.150 ms`. Result: keep RR-20-SRTF recommendation and do not add
ML for MLFQ queue or quantum prediction from this evidence.

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
- Static adaptive selection chooses once per workload; the separate dynamic
  experiment can switch at dispatch boundaries
- Offline retraining only
- Synthetic workloads, not kernel traces
- No multicore affinity, deadlines, cache effects, or burst prediction
- Switch cost is simulated only for Priority-RR; it is not kernel timing
- Priority is not part of the weighted objective, so Priority Scheduling may
  rarely be the oracle winner

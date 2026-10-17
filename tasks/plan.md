# Implementation Plan: Realistic ML Validation for AutoScheduler

## Overview

AutoScheduler will move from synthetic-only decision-tree experiments to a reproducible, realistic validation pipeline. Public production traces will calibrate arrivals, durations, workload mixtures, and resource demand. Locally captured Linux scheduler traces will provide wake-up, run, block, and context-switch behavior at OS level. A controlled model bake-off will compare simple and nonlinear models against the fixed RR-20-SRTF baseline using the same observed-only features, grouped splits, tuning budget, score anchors, fairness gates, and latency gates.

The final research claim is deliberately narrow:

> Can an observed-state model choose one RR-to-SRTF switch time from `{5, 10, 20, 40, never}` and outperform fixed RR-20-SRTF on unseen real workload families?

Synthetic workloads remain useful for unit tests, stress cases, and pretraining. They cannot provide the final real-world claim.

## Current Baseline

- Current system: Python single-CPU event-driven simulator.
- Current strongest static comparator: RR quantum `1`, then permanent SRTF at the first dispatch boundary after tick `20`.
- Current ML family: decision-tree classifiers and one decision-tree regressor.
- Missing evidence: cross-model comparison, public-trace ingestion, OS event capture, unseen real-application evaluation, and kernel execution.
- Existing success gates retained:
  - mean weighted score improves by at least `1%` over RR-20-SRTF;
  - paired 95% confidence interval for `ML - RR20-SRTF` is entirely below zero;
  - end-to-end decision P99 is strictly below `10 ms`;
  - fairness does not regress beyond a prespecified non-inferiority margin.

## Architecture Decisions

1. **Three evidence tiers**
   - Synthetic: deterministic correctness, rare cases, and optional pretraining.
   - Public production traces: realistic arrival and duration distributions.
   - Local Linux traces: OS-level wake-up, execution, blocking, and switching evidence.

2. **Public traces are not treated as kernel traces**
   - Azure, Google, and Alibaba traces describe production workloads but generally omit enough per-process scheduling detail to reconstruct every CPU burst and preemption.
   - They calibrate the generator and provide trace-driven arrivals; they do not independently prove kernel scheduling performance.

3. **One narrow ML decision**
   - Keep RR quantum fixed at `1`.
   - Choose one switch time from `{5, 10, 20, 40, never}`.
   - Fall back to fixed switch time `20` when confidence or input validity is insufficient.

4. **Predict scheduling cost, not only an oracle class**
   - Represent each decision snapshot with each candidate action.
   - Predict the final frozen weighted score or score delta for that action.
   - Select the action with the lowest predicted score, subject to a safety margin.
   - Classification accuracy remains secondary; system score and regret are primary.

5. **Small model bake-off**
   - No-ML fixed RR-20-SRTF.
   - Dummy mean predictor.
   - Ridge regression.
   - Decision-tree regressor.
   - Random-forest regressor.
   - Histogram gradient-boosting regressor.
   - Add neural networks or reinforcement learning only if all smaller models fail and evidence shows missing model capacity.

6. **Leakage-resistant evaluation**
   - Group by complete trace, workload family, application, capture session, and machine where available.
   - No rows from one trace may cross train, validation, or test.
   - The final real test set is sealed before tuning.

7. **Simulator before kernel**
   - First validate trace parsing and policy replay in the existing simulator.
   - Implement a `sched_ext` pilot only after the model beats RR-20-SRTF on a locked real-trace replay set.

## Dependency Graph

```text
Scientific contract
    |
    +-- Trace schema and provenance
    |       |
    |       +-- Public trace adapters
    |       +-- Linux trace collector
    |               |
    +---------------+-- Trace validation and replay
                            |
                            +-- Observed-state dataset and labels
                                    |
                                    +-- Cross-model bake-off
                                            |
                                            +-- Locked real evaluation
                                                    |
                                                    +-- sched_ext pilot
                                                            |
                                                            +-- Final report
```

## Phase 0: Freeze the Scientific Contract

### Goal

Prevent score, action, feature, and gate changes after results are visible.

### Deliverables

- `configs/real_ml_experiment.json`
- Dataset source policy and licensing notes.
- Frozen feature availability rules.
- Frozen model candidate list and equal tuning budget.

### Decisions to freeze

- Baseline: RR-20-SRTF.
- Actions: `{5, 10, 20, 40, never}`.
- Score: existing frozen six-policy normalization and weights.
- Primary outcome: paired weighted-score difference.
- Secondary outcomes: regret, response, P95/max wait, starvation, throughput, context switches, and utilization.
- Latency: feature extraction plus inference plus action selection.
- Default fairness margin: no starvation increase; no more than `2%` degradation in P95 waiting or post-I/O response. Any different margin must be justified before evaluation.

### Exit gate

- Experiment config is machine-readable, validated, and hashed into every result summary.

## Phase 1: Define the Real Trace Contract

### Goal

Create one canonical format that can represent synthetic, public, and Linux-captured traces without inventing unavailable fields.

### Tables

1. `trace_metadata`
   - trace ID, source, license, source URL, workload family, application, version, machine ID, kernel version, scheduler, capture session, start time, and anonymization state.
2. `events`
   - timestamp, CPU, process/thread ID, event type, priority, previous state, ready count, and optional wake-up source.
3. `processes`
   - process ID, arrival, completion, observed priority, parent/cgroup label, and application family.
4. `outcomes`
   - policy/action, repetition, waiting, response, turnaround, throughput, utilization, context switches, and decision latency.

### Event vocabulary

`arrival`, `wakeup`, `switch_in`, `switch_out`, `block`, `io_complete`, `exit`.

Unknown data stays `null`; it is never replaced by guessed CPU/I/O bursts.

### Exit gate

- Schema validation accepts a fixture from each source tier.
- Event timestamps are monotonic per trace.
- Every process has a valid lifecycle or an explicit truncated flag.
- Round-trip CSV/Parquet conversion preserves values and nulls.

## Phase 2: Import Public Production Traces

### Goal

Use real workload distributions without claiming that cluster traces are OS ready-queue traces.

### First adapters

1. **Azure Functions Invocation Trace 2021**
   - Use invocation completion timestamps and durations to derive arrivals and service-duration distributions.
2. **Alibaba microservice or cluster trace sample**
   - Use workload mixture, call rate, response time, resource utilization, and online/batch labels where available.
3. **Optional Google cluster trace sample**
   - Add only if it contributes fields not already covered by Azure and Alibaba.

### Storage policy

- Do not commit raw multi-gigabyte datasets.
- Commit download instructions, checksums, licenses, schemas, and tiny fixtures.
- Store generated processed datasets under ignored `data/processed/` paths.

### Exit gate

- Same input and adapter version produce identical processed trace hashes.
- Source lineage appears in every processed row.
- Distribution report compares public traces with the current synthetic generator.
- Missing OS-level fields are listed explicitly.

## Phase 3: Capture Local Linux Scheduler Traces

### Goal

Create the OS-level dataset that public cloud traces cannot provide.

### Capture method

- Use Linux scheduler tracepoints such as `sched_wakeup`, `sched_waking`, `sched_switch`, and process exit events.
- Pin the experiment to one CPU for simulator compatibility.
- Record kernel, CPU, power governor, background load, command version, and capture configuration.
- Anonymize command lines and identifiers before sharing.

### Workload suite

- CPU-heavy application.
- File or database I/O-heavy application.
- Interactive request/response service.
- Batch compilation or compression workload.
- Mixed concurrent workload.
- At least one standard benchmark family such as PARSEC.

### Repetition protocol

- Warm up before measurements.
- Run at least 10 measured repetitions per scenario and policy/action.
- Randomize action order within each scenario.
- Preserve complete runs as indivisible split groups.

### Exit gate

- Collector produces valid canonical traces for every workload family.
- Repeated idle calibration establishes tracing overhead.
- Missing or dropped events are detected and reported.
- Capture does not silently mix processes from outside the experiment cgroup.

## Phase 4: Validate Trace Replay and Generator Calibration

### Goal

Prove that imported data is interpreted correctly before training models.

### Replay validation

- Reconstruct observed runnable, running, and blocked intervals.
- Replay the observed policy where possible.
- Compare replayed and recorded makespan, utilization, response, and switch count.
- Report fidelity error rather than forcing exact equality when the source lacks detail.

### Generator calibration

- Fit empirical arrival, service-duration, burst-count, priority, and I/O-return distributions from the realistic traces.
- Add a `trace_calibrated` generator profile while preserving existing historical profiles.
- Keep calibration parameters versioned and source-linked.

### Exit gate

- Median replay error is below a frozen tolerance for each measurable metric.
- Trace-calibrated generation matches selected empirical quantiles within tolerance.
- Existing synthetic seeds and historical results remain unchanged.

## Phase 5: Build Observed-State Decision Data

### Goal

Create leakage-free rows for switch-time model training.

### Feature rules

Allowed examples:

- elapsed time;
- arrivals observed so far;
- current ready and blocked counts;
- completed CPU-run duration statistics;
- completed blocking-duration statistics;
- recent wake-up and I/O-return rate;
- waiting-time statistics;
- priority distribution;
- context switches so far;
- CPU busy/idle fraction observed so far.

Forbidden examples:

- future arrivals;
- declared total CPU or I/O work;
- future burst durations;
- true remaining total work;
- final metrics from the same run.

### Label strategy

- For simulator and replay experiments, evaluate all five candidate switch actions from the same decision state.
- Store one row per `(trace, decision snapshot, action)` with final weighted score and score delta from RR-20-SRTF.
- For real kernel evidence, rerun the same scenario under each action; do not pretend a single observed run gives exact counterfactual outcomes.

### Exit gate

- Automated leakage audit rejects forbidden columns.
- Same trace never crosses data splits.
- Every training row links to its source trace and action result.
- Workloads completing before a decision use the baseline result without inference.

## Phase 6: Run the Cross-Model Bake-Off

### Goal

Determine whether a decision tree is actually better than other small models.

### Candidate models

| Candidate | Purpose |
|---|---|
| Fixed RR-20-SRTF | Required no-ML comparator |
| Dummy mean regressor | Minimum ML sanity baseline |
| Ridge regression | Fast linear baseline |
| Decision-tree regressor | Current interpretable nonlinear baseline |
| Random-forest regressor | Stable nonlinear ensemble |
| Histogram gradient boosting | Strong compact tabular baseline |

### Fair tuning

- Same train/validation/test groups and features.
- Same maximum number of candidate configurations per model family.
- Tune on validation mean realized scheduler score, not prediction error alone.
- Refit the chosen candidate on train plus validation only after selection.
- Never inspect locked test outcomes during tuning.

### Reports

- Prediction MAE and rank correlation.
- Selected-action accuracy as a secondary diagnostic.
- Mean scheduler score and regret.
- Paired difference versus RR-20-SRTF.
- Switch-time distribution and fallback rate.
- Feature extraction, inference, and total decision latency.
- Model size and feature importance or coefficients.

### Exit gate

- One reproducible table compares every model under identical conditions.
- The chosen model passes all primary gates on internal real-trace test data.
- Simpler model wins ties within statistical uncertainty.

## Phase 7: Evaluate Generalization on a Locked Real Test Set

### Goal

Measure realistic external validity rather than generator-specific accuracy.

### Required test splits

1. Unseen runs of known applications.
2. Unseen applications from known workload families.
3. Unseen mixed workload combinations.
4. Preferably a second machine or capture session.
5. Synthetic stress fixtures reported separately, never merged into the headline real result.

### Statistical protocol

- Pair each model and baseline on the same trace/scenario.
- Use 10,000 trace-level bootstrap samples.
- Resample complete trace groups, not decision rows.
- Report overall and per-family confidence intervals.
- Correctly report negative, mixed, and profile-specific outcomes.

### Final ML acceptance gate

ML is accepted only when all are true:

1. Mean weighted score is at least `1%` lower than RR-20-SRTF.
2. Paired 95% CI upper bound is below zero.
3. Every workload-family result is reported; no family is silently excluded.
4. Starvation does not increase and P95 wait/post-I/O response stay within the frozen fairness margin.
5. End-to-end decision P99 is below `10 ms` at 12, 100, and 1,000-process scales.
6. The improvement survives an unseen-application split.

If any gate fails, RR-20-SRTF remains the recommendation.

## Phase 8: Implement a Minimal `sched_ext` Pilot

### Goal

Test whether the winning observed-state decision survives outside Python simulation.

### Scope

- Implement only RR, SRTF-like estimated-short-job behavior, and one safe RR-to-SRTF profile switch.
- Keep model inference outside the BPF fast path unless a compiled shallow model is demonstrably safe.
- Use confidence gating, minimum dwell time, stale-control fallback, and scheduler failure fallback.
- Record actual dispatch overhead, CPU overhead, stalls, and fallback events.

### Exit gate

- Static RR-20-SRTF and the winning ML controller run on the same real workloads.
- No scheduler watchdog or stalled-runnable-task failures.
- Kernel experiment reproduces the direction of the replay result.
- Full controller latency and CPU overhead are reported separately from Python inference latency.

## Phase 9: Reproducibility and Research Report

### Goal

Produce evidence that another researcher can inspect and reproduce.

### Required artifacts

- Dataset manifests, checksums, licenses, and adapters.
- Capture scripts and environment manifest.
- Frozen experiment configuration.
- Model search table and selected hyperparameters.
- Raw per-trace results.
- Summary JSON/CSV and plots.
- Synthetic-versus-real distribution comparison.
- Real held-out results and paired confidence intervals.
- Limitations and negative results.

### Exit gate

- Clean checkout can reproduce fixtures and small smoke experiments.
- Full data instructions reproduce the research tables when datasets are present.
- Report clearly separates synthetic, replay, and kernel evidence.

## CLI Target

The implementation should converge on these commands without removing existing ones:

```bash
python main.py trace-import --source azure --input DATA --output data/processed/azure
python main.py trace-validate --input data/processed/azure
python main.py trace-calibrate --input data/processed --output artifacts/trace_calibration.json
python main.py real-dataset --config configs/real_ml_experiment.json
python main.py model-bakeoff --config configs/real_ml_experiment.json
python main.py real-evaluate --config configs/real_ml_experiment.json
python main.py real-latency --config configs/real_ml_experiment.json
```

No command should automatically download large datasets or overwrite historical results.

## Checkpoints

### Checkpoint A: After Phases 0-2

- Contract, schema, fixtures, and public-trace provenance reviewed.
- No raw large dataset committed.
- Existing test suite remains green.

### Checkpoint B: After Phases 3-4

- Local Linux traces captured and validated.
- Replay fidelity and tracing overhead quantified.
- Human review before generating ML labels.

### Checkpoint C: After Phases 5-6

- Leakage audit passes.
- Cross-model table exists.
- Decision tree is described as best only if evidence proves it.

### Checkpoint D: After Phase 7

- Final real-trace gate result frozen.
- Continue to kernel pilot only if ML passes all gates.

### Checkpoint E: After Phases 8-9

- Kernel and replay evidence reconciled.
- Research report and reproducibility package complete.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Public traces lack CPU burst/I/O detail | High | Use them for calibration; collect Linux scheduler traces for OS evidence |
| Counterfactual labels from one real run are invalid | High | Rerun each scenario/action or clearly label simulator-only counterfactuals |
| Rows from the same trace leak across splits | High | Group splits by trace, application, session, and machine |
| Model wins because of unequal tuning | High | Fixed candidate budget and identical validation groups |
| ML learns generator quirks | High | Locked unseen-application real test set |
| Tracing changes workload behavior | Medium | Measure idle and workload tracing overhead; report it |
| Real runs are noisy | Medium | Warmups, randomized policy order, repetitions, paired analysis |
| Large datasets enter Git | Medium | Ignore raw/processed data; commit manifests, checksums, and tiny fixtures only |
| Kernel prototype expands scope too early | High | Require real replay gate before `sched_ext` implementation |
| Tree is chosen for convenience | High | Mandatory model-family bake-off and simplicity tie-break |

## Primary References

- Azure Public Dataset: https://github.com/Azure/AzurePublicDataset
- Alibaba Cluster Trace Program: https://github.com/alibaba/clusterdata
- Google Cluster Data: https://github.com/google/cluster-data
- Linux event tracing: https://docs.kernel.org/trace/events.html
- Linux `sched_ext`: https://docs.kernel.org/scheduler/sched-ext.html
- Scikit-learn grouped cross-validation: https://scikit-learn.org/stable/modules/cross_validation.html

## Definition of Done

This program is complete only when:

- realistic public and locally captured OS traces use one validated schema;
- models are compared under identical data, tuning, and latency conditions;
- final test applications are unseen during tuning;
- ML either passes every score, statistical, fairness, and latency gate or is rejected;
- any positive claim is reproduced in a minimal kernel pilot;
- synthetic-only evidence is never presented as real OS proof.

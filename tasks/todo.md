# AutoScheduler Realistic ML Validation Tasks

## Phase 0: Scientific Contract

### Task 1: Freeze the real-ML experiment configuration

**Description:** Add a machine-readable configuration containing the baseline, actions, score anchors, model families, split groups, fairness margins, seeds, and acceptance gates.

**Acceptance criteria:**
- [ ] Configuration validates and is included by hash in result summaries.
- [ ] Existing six-policy score weights and normalization remain unchanged.
- [ ] RR-20-SRTF and `{5,10,20,40,never}` are frozen before new results.

**Verification:**
- [ ] Focused config validation test passes.
- [ ] Existing full test suite passes.

**Dependencies:** None

**Files likely touched:** `configs/real_ml_experiment.json`, `autoscheduler/config.py`, `tests/test_real_config.py`

**Estimated scope:** Medium

## Phase 1: Trace Contract

### Task 2: Implement canonical trace schema and validators

**Description:** Represent metadata, scheduler events, process lifecycles, and outcomes without inventing missing values.

**Acceptance criteria:**
- [ ] Synthetic, public, and Linux fixtures validate.
- [ ] Unknown fields remain null.
- [ ] Monotonicity and lifecycle errors are reported with trace IDs.

**Verification:**
- [ ] Round-trip fixture tests pass.
- [ ] Invalid lifecycle fixtures fail deterministically.

**Dependencies:** Task 1

**Files likely touched:** `autoscheduler/traces/schema.py`, `autoscheduler/traces/io.py`, `tests/test_trace_schema.py`

**Estimated scope:** Medium

## Phase 2: Public Traces

### Task 3: Add Azure Functions trace adapter

**Description:** Convert Azure invocation timestamps and durations into canonical trace arrivals and service observations with source provenance.

**Acceptance criteria:**
- [ ] Tiny official-format fixture imports deterministically.
- [ ] Source URL, version, license, and checksum are retained.
- [ ] Unsupported OS fields remain null.

**Verification:**
- [ ] Adapter fixture and checksum tests pass.
- [ ] Import report lists unavailable scheduler fields.

**Dependencies:** Task 2

**Files likely touched:** `autoscheduler/traces/azure.py`, `tests/fixtures/traces/azure/`, `tests/test_azure_trace.py`

**Estimated scope:** Medium

### Task 4: Add one Alibaba trace adapter

**Description:** Import one selected Alibaba dataset that contributes workload mix, rates, response, or utilization beyond Azure.

**Acceptance criteria:**
- [ ] Dataset choice and field mapping are documented.
- [ ] Tiny fixture imports with provenance.
- [ ] No cluster-level field is mislabeled as an OS CPU burst.

**Verification:**
- [ ] Adapter fixture test passes.
- [ ] Schema mapping audit passes.

**Dependencies:** Task 2

**Files likely touched:** `autoscheduler/traces/alibaba.py`, `tests/fixtures/traces/alibaba/`, `tests/test_alibaba_trace.py`

**Estimated scope:** Medium

### Checkpoint A

- [ ] Tasks 1-4 complete.
- [ ] Full suite passes.
- [ ] Raw datasets are ignored; manifests and fixtures are committed.
- [ ] Human review approves field semantics.

## Phase 3: Linux OS Traces

### Task 5: Build a minimal Linux scheduler trace collector

**Description:** Capture scheduler wake-up, context-switch, block, and exit events plus reproducibility metadata for a process cgroup pinned to one CPU.

**Acceptance criteria:**
- [ ] Collector captures only the scoped workload group.
- [ ] Kernel, CPU, governor, workload, and collector versions are recorded.
- [ ] Dropped events are detectable.

**Verification:**
- [ ] Short CPU and sleep fixture produces expected lifecycle.
- [ ] Idle tracing overhead is measured.

**Dependencies:** Task 2

**Files likely touched:** `tools/capture_linux_trace.sh`, `autoscheduler/traces/linux.py`, `tests/test_linux_trace.py`

**Estimated scope:** Medium

### Task 6: Define and automate the realistic workload suite

**Description:** Add repeatable CPU, I/O, interactive, batch, mixed, and benchmark scenarios with one-core pinning and randomized policy order.

**Acceptance criteria:**
- [ ] Every scenario has a versioned command and expected duration range.
- [ ] At least 10 measured repetitions are supported.
- [ ] Complete runs receive stable group identifiers.

**Verification:**
- [ ] Smoke workload suite completes on a Linux host.
- [ ] Environment manifest is generated.

**Dependencies:** Task 5

**Files likely touched:** `workloads/real/manifest.json`, `tools/run_real_workloads.py`, `tests/test_real_workload_manifest.py`

**Estimated scope:** Medium

## Phase 4: Replay and Calibration

### Task 7: Add canonical trace replay

**Description:** Reconstruct ready, running, and blocked intervals and compare replay metrics with recorded outcomes.

**Acceptance criteria:**
- [ ] Replay reports fidelity error for makespan, utilization, response, and switches.
- [ ] Truncated or insufficient traces are rejected or explicitly downgraded.
- [ ] Existing simulator behavior remains unchanged.

**Verification:**
- [ ] Exact synthetic fixture replay passes.
- [ ] Real fixture produces bounded, reported error.

**Dependencies:** Tasks 3-6

**Files likely touched:** `autoscheduler/traces/replay.py`, `tests/test_trace_replay.py`

**Estimated scope:** Medium

### Task 8: Add trace-calibrated synthetic generation

**Description:** Fit versioned empirical distributions from processed traces and generate realistic stress workloads without replacing historical profiles.

**Acceptance criteria:**
- [ ] Calibration artifact records source hashes.
- [ ] Same artifact and seed produce identical workloads.
- [ ] Quantile comparison report is generated.

**Verification:**
- [ ] Reproducibility and quantile-tolerance tests pass.
- [ ] Historical workload tests remain unchanged.

**Dependencies:** Task 7

**Files likely touched:** `autoscheduler/calibration.py`, `autoscheduler/workloads.py`, `tests/test_calibrated_workloads.py`

**Estimated scope:** Medium

### Checkpoint B

- [ ] Tasks 5-8 complete.
- [ ] Full suite passes.
- [ ] Trace fidelity and tracing overhead are documented.
- [ ] Human review approves progression to label generation.

## Phase 5: Observed-State Dataset

### Task 9: Implement observed-only real feature extraction

**Description:** Extract runtime features from events seen before the decision boundary and reject future or final-state information.

**Acceptance criteria:**
- [ ] Feature timestamps never exceed decision time.
- [ ] Forbidden future/total fields are absent.
- [ ] Missing optional features are represented explicitly.

**Verification:**
- [ ] Leakage tests mutate future events without changing current features.
- [ ] Feature schema is versioned.

**Dependencies:** Task 7

**Files likely touched:** `autoscheduler/real_features.py`, `tests/test_real_features.py`

**Estimated scope:** Medium

### Task 10: Generate action-cost training rows

**Description:** Evaluate `{5,10,20,40,never}` from one decision state and store final frozen score and baseline delta per action.

**Acceptance criteria:**
- [ ] Every row links to trace, snapshot, action, and source result.
- [ ] Real counterfactuals are labeled replay or repeated-kernel-run evidence.
- [ ] Grouped 70/15/15 split is deterministic and disjoint.

**Verification:**
- [ ] Action rows reproduce direct policy results.
- [ ] Split-disjointness test passes.

**Dependencies:** Tasks 1, 7, 9

**Files likely touched:** `autoscheduler/real_dataset.py`, `tests/test_real_dataset.py`

**Estimated scope:** Medium

## Phase 6: Model Bake-Off

### Task 11: Add equal-budget model registry and tuning

**Description:** Compare dummy, Ridge, decision tree, random forest, and histogram gradient boosting with identical groups, features, and candidate budgets.

**Acceptance criteria:**
- [ ] Each family receives the same maximum candidate count.
- [ ] Validation selects lowest realized scheduler score.
- [ ] Simpler model wins statistically indistinguishable ties.

**Verification:**
- [ ] Controlled fixture can make each family win.
- [ ] Test rows remain untouched until final evaluation.

**Dependencies:** Task 10

**Files likely touched:** `autoscheduler/model_bakeoff.py`, `tests/test_model_bakeoff.py`

**Estimated scope:** Medium

### Task 12: Add model comparison reports and CLI

**Description:** Produce one table and artifact set covering prediction, scheduling, fairness, latency, model size, and action selection.

**Acceptance criteria:**
- [ ] `model-bakeoff` command writes JSON, CSV, and plots.
- [ ] Report distinguishes prediction accuracy from scheduler performance.
- [ ] Every candidate and fixed baseline appears.

**Verification:**
- [ ] CLI smoke test passes on fixtures.
- [ ] Result schema test validates all required metrics.

**Dependencies:** Task 11

**Files likely touched:** `autoscheduler/cli.py`, `autoscheduler/model_bakeoff.py`, `tests/test_model_bakeoff_cli.py`

**Estimated scope:** Medium

### Checkpoint C

- [ ] Tasks 9-12 complete.
- [ ] Full suite passes.
- [ ] Leakage audit passes.
- [ ] Cross-model comparison table exists.
- [ ] No “decision tree is best” claim without supporting results.

## Phase 7: Locked Real Evaluation

### Task 13: Run grouped unseen-application evaluation

**Description:** Evaluate the selected model on sealed real workload groups with paired trace-level bootstrap analysis.

**Acceptance criteria:**
- [ ] Test groups contain unseen applications or combinations.
- [ ] 10,000 grouped bootstrap samples are used.
- [ ] Overall and per-family results are saved.

**Verification:**
- [ ] Bootstrap reproducibility test passes.
- [ ] Test manifest hash matches the frozen experiment config.

**Dependencies:** Task 12

**Files likely touched:** `autoscheduler/real_evaluation.py`, `tests/test_real_evaluation.py`

**Estimated scope:** Medium

### Task 14: Measure full decision latency and fairness gates

**Description:** Measure feature extraction, model inference, action selection, P50/P95/P99, and the frozen fairness non-inferiority gates.

**Acceptance criteria:**
- [ ] Latency covers the complete decision path.
- [ ] 12, 100, and 1,000-process scales are reported.
- [ ] Score, confidence, fairness, and latency gate booleans are explicit.

**Verification:**
- [ ] Strict `<10 ms` boundary test passes.
- [ ] Missing fairness samples stay null, not zero.

**Dependencies:** Task 13

**Files likely touched:** `autoscheduler/real_latency.py`, `autoscheduler/fairness.py`, `tests/test_real_latency.py`

**Estimated scope:** Medium

### Checkpoint D

- [ ] Tasks 13-14 complete.
- [ ] Final real-trace result is frozen.
- [ ] RR-20-SRTF remains recommendation unless every ML gate passes.
- [ ] Human review decides whether kernel pilot is justified.

## Phase 8: Kernel Pilot

### Task 15: Implement minimal `sched_ext` RR-20-SRTF profiles

**Description:** Implement the static comparator and safe profile transition with fallback and diagnostics.

**Acceptance criteria:**
- [ ] Static baseline runs the realistic suite.
- [ ] Scheduler failure restores the default Linux scheduler.
- [ ] Stalls and fallback events are recorded.

**Verification:**
- [ ] Kernel smoke workload completes without watchdog failure.
- [ ] Static simulator and kernel behavior are compared.

**Dependencies:** Checkpoint D approval

**Files likely touched:** `kernel/`, `tools/run_sched_ext_experiment.py`

**Estimated scope:** Large; split into loader, scheduler, and runner tasks before implementation

### Task 16: Connect the winning model to the kernel pilot

**Description:** Apply the selected action through a bounded controller with confidence, dwell, stale-state, and fallback rules.

**Acceptance criteria:**
- [ ] ML and static baseline run identical real scenarios.
- [ ] Full controller overhead is measured.
- [ ] Kernel result reproduces or contradicts replay transparently.

**Verification:**
- [ ] Paired kernel experiment completes.
- [ ] Fallback injection test passes.

**Dependencies:** Task 15 and ML passing Checkpoint D

**Files likely touched:** `kernel/`, `controller/`, `tools/run_sched_ext_experiment.py`

**Estimated scope:** Large; split before implementation

## Phase 9: Research Package

### Task 17: Publish reproducibility artifacts and final report

**Description:** Document data lineage, environments, model comparison, real results, kernel results, limitations, and negative findings.

**Acceptance criteria:**
- [ ] Synthetic, public-trace, replay, and kernel evidence are separated.
- [ ] Commands and manifests reproduce reported tables.
- [ ] Every positive claim points to a passed gate.

**Verification:**
- [ ] Clean-checkout smoke reproduction passes.
- [ ] Documentation links and artifact hashes validate.

**Dependencies:** Tasks 13-16 as applicable

**Files likely touched:** `README.md`, `docs/`, `results/real_ml/`

**Estimated scope:** Medium

### Checkpoint E: Complete

- [ ] Every applicable task and gate is complete.
- [ ] Real held-out evidence supports the final recommendation.
- [ ] Kernel claim exists only if the kernel pilot passed.
- [ ] Results are ready for Methodology, Experimental Setup, Results, Discussion, Limitations, and Conclusion.

# AutoScheduler — Faculty Code Review Guide

| Rank | Priority | Implementation to open | Exact source / function | Why this ranks here |
|---:|---|---|---|---|
| 1 | P0 | [Cost regression proposes an action; it does not directly dispatch a process](#topic-1) | `autoscheduler/model.py:15` — `PolicyCostModel.predict / switch_allowed` | Defines what the active ML model actually predicts. |
| 2 | P0 | [The v5 controller accepts, blocks, and expires policy changes](#topic-2) | `autoscheduler/dynamic.py:508` — `run_dynamic / _tail_action / _protected` | Main contribution and most demanding safety explanation. |
| 3 | P0 | [Observed-state features and the boundary against future knowledge](#topic-3) | `autoscheduler/dynamic.py:422` — `extract_dynamic_features / _prediction` | Proves the realistic dynamic path excludes oracle features. |
| 4 | P0 | [Event-driven execution and preservation of state during switching](#topic-4) | `autoscheduler/dynamic.py:302` — `_dispatch / _new_state; simulator.engine.simulate` | Shows what actually executes CPU work. |
| 5 | P0 | [MLFQ feedback, aging and the tuned static comparator](#topic-5) | `simulator/engine.py:90` — `simulate.age_ready / take_ready / MLFQ requeue block` | Strong baseline and default safety destination. |
| 6 | P0 | [Classical policies, oracle policies and real preemption semantics](#topic-6) | `simulator/engine.py:103` — `simulate.take_ready` | Faculty can verify every algorithm by its selection key. |
| 7 | P0 | [Process invariants and CPU/I/O burst representation](#topic-7) | `simulator/process.py:28` — `Process.__post_init__ / reset` | All scheduling and metric accounting depends on these fields. |
| 8 | P0 | [Metric definitions, weighted score and what a win means](#topic-8) | `simulator/simulator.py:69` — `compute_metrics / run_simulation; score_result_against_reference` | Prevents confusing model agreement, score and actual outcomes. |
| 9 | P0 | [Which fitted model the current demo really loads](#topic-9) | `dashboard/adapter.py:89` — `_original_v5 / _run_v5 / simulation` | Separates active inference from historical metadata and dead branches. |
| 10 | P1 | [The original classifier: synthetic labels, fitting and choose-once scheduling](#topic-10) | `autoscheduler/dataset.py:21` — `build_dataset; train_model; run_adaptive` | Explains historical classifier research without conflating v5. |
| 11 | P1 | [Dynamic training labels, group splits and offline learning](#topic-11) | `autoscheduler/dynamic.py:565` — `_counterfactual_label; dynamic_training.build_training_data` | Hardest training explanation and main leakage boundary. |
| 12 | P1 | [Model selection, comparative evidence and safety gates](#topic-12) | `autoscheduler/dynamic_training.py:105` — `validation_metrics; dynamic_v5_experiment.run` | Justifies selection without claiming unsupported ML superiority. |
| 13 | P1 | [Azure reconstruction, bounded sampling and time-unit distortion](#topic-13) | `AzureWorkloads/scripts/convert_workloads.py:30` — `reconstruct; refine_workloads.sample_sources` | Defines what external data can and cannot validate. |
| 14 | P1 | [External Azure results: inspect the cohort, failures and tradeoffs](#topic-14) | `autoscheduler/azure_generalization_report.py:44` — `summarize; azure_generalization_evaluation.evaluate` | Highest risk of overstating the project's measured contribution. |
| 15 | P1 | [Tests as executable claims and limits of this inspection](#topic-15) | `tests/test_dynamic_contract.py:29` — `DynamicObservabilityTests.test_features_ignore_declared_work_and_unobserved_future` | Shows how to prove behavior rather than trust UI labels. |
| 16 | P2 | [Dashboard simulation requests, playback and dynamic visualization](#topic-16) | `dashboard/web/src/Simulation.jsx:46` — `Simulation / PolicyPlayback / Gantt` | Explains what is computed on request and what is only animation. |
| 17 | P2 | [Saved research panels, API routing and UI discrepancies](#topic-17) | `dashboard/adapter.py:54` — `catalog; Research.Intelligence / RealSourceDynamic` | Prevents treating saved JSON or build-time imports as fresh results. |
| 18 | P2 | [CLI, Linux trace tooling and the boundary before kernel claims](#topic-18) | `autoscheduler/real_dataset.py:136` — `build_development_action_rows; main.main` | Clarifies secondary functionality without claiming deployment. |

## Scope and how to use this guide

Inspected **21 October 2026**, local HEAD `9322bec`, including the current uncommitted dashboard/test edits. Source files, executable branches, saved artifacts and small saved-result tables were inspected directly. Line references describe this checkout and may shift after later edits. The guide contains **9 P0, 6 P1 and 3 P2 topics**, ordered by functional importance and claim risk rather than execution order.

Study P0 first, then training/evaluation in P1; use P2 for frontend and secondary tooling questions. Each topic includes a short spoken explanation, exact excerpts, key lines, call connections, an alternative with tradeoffs, questions and claims to avoid. Snippets are verbatim source slices, not pseudocode. “Interpretation” means a reasonable engineering justification, not an undocumented historical motivation.

The initial graph query executable was unavailable in this environment, so existing graph vocabulary and a read-only graph traversal were used for orientation. All implementation claims were then checked against current source; no graph files were regenerated. Checks were limited to existing-artifact loading, inspection of the original tree, four tiny in-memory demo executions and arithmetic over saved result rows. No training, dependency installation, settings changes, dataset regeneration, full test suite or expensive experiment was run. Only this guide is written.

**Central distinction:** the original offline classifier, the multi-output cost regressor, the dynamic controller, and static MLFQ are four different things. They are not a combined classifier–regression architecture. A working switching demonstration is not proof of scheduling superiority.

<a id="topic-1"></a>

### [P0] 1. Cost regression proposes an action; it does not directly dispatch a process

**A. WHAT TO SAY (15–30 seconds)**

> The tree predicts six scheduling-cost deltas from the observed state. We pick the lowest predicted cost, then check whether its advantage over staying is large enough. This gives a proposed policy, not a process ID, and the controller can still reject it.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/model.py` → `PolicyCostModel.predict / switch_allowed`.

**Chunk 1.** Focus on source lines **23–24 and 34–36**.

Source: [autoscheduler/model.py](../autoscheduler/model.py), lines **15–36**.

```python
class PolicyCostModel:
    """One small multi-output tree predicts the cost of each eligible policy."""

    regressor: object
    policies: tuple[str, ...]
    switch_margin: float = 0.005

    def predict(self, matrix):
        return [self.policies[min(range(len(costs)), key=lambda i: (costs[i], i))]
                for costs in self.regressor.predict(matrix)]

    def predict_benefits(self, matrix):
        """Expected score improvement relative to immediate MLFQ continuation."""
        return [dict(zip(self.policies, map(lambda cost: -float(cost), costs)))
                for costs in self.regressor.predict(matrix)]

    def switch_allowed(self, features, active, selected):
        from autoscheduler.dynamic import DYNAMIC_FEATURE_NAMES

        costs = self.regressor.predict([[features[name] for name in DYNAMIC_FEATURE_NAMES]])[0]
        baseline = "No Switch" if "No Switch" in self.policies else active
        return bool(costs[self.policies.index(baseline)] - costs[self.policies.index(selected)] >= self.switch_margin)
```

**C. EXPLAIN THE CODE**

**Chunk 1:** Input is a numeric matrix with 19 ordered features per row. The wrapped regressor returns six costs; predict returns one action string per row. Equal predictions use action order. switch_allowed predicts again and compares No Switch with the selected action using an absolute 0.005 margin; this is not 0.5% relative improvement. predict_benefits negates each cost relative to MLFQ continuation, whereas the admission margin compares against No Switch.

The original fitted artifact uses DecisionTreeRegressor, depth 3, with actions FCFS, Round Robin, Priority, Priority RR, MLFQ, No Switch. Targets are normalized score(action for a feasible horizon, then MLFQ) minus score(immediate MLFQ continuation). Negative means predicted improvement against that continuation. This is neither predicted raw waiting time nor a probability. _prediction calls model.predict; run_dynamic later calls switch_allowed, so one action prediction can involve two underlying tree predictions. Direct tree inspection found seven leaves and only three used inputs: completed_burst_variance, ready_count, arrival_quiet_ticks. Six leaves choose Priority; the all-zero leaf chooses FCFS by order. Neither raw RR nor raw MLFQ nor raw No Switch wins in this particular fitted tree; an FCFS tie has no margin for departure.

**D. WHY WE USED THIS APPROACH**

The code explicitly documents multi-output policy-cost prediction and the margin safeguard. A reasonable justification is that numerical costs express the size of a proposed gain, which a direct DecisionTreeClassifier label cannot. A classifier with probabilities is a valid alternative, but class probability is not scheduling benefit. A forest or boosted ensemble could fit richer interactions at higher inference and explanation cost; local comparisons do not establish that a tree is universally best. This is an interpretation of the tradeoff, not an invented historical motivation.

**E. FACULTY QUESTIONS**

- **Does the regressor output a scheduler name?** The underlying tree outputs costs; PolicyCostModel.predict converts their argmin to a name.
- **Why not always switch to the cheapest action?** The predicted gain may be too small or the action may violate dwell or response safeguards.
- **Is confidence 1.0 proof of certainty?** No. The non-classifier branch supplies 1.0 as an interface convention; the margin is separate.

**F. DON'T SAY THIS**

Do not call it a neural network, an accuracy predictor, a classifier–regressor hybrid, or a guarantee of improvement. Six supported actions do not mean this fitted tree proposes all six.

**G. CONNECTION**

autoscheduler/dynamic.py:_prediction (457–469), run_dynamic (481–554), _counterfactual_label (557–604); autoscheduler/model_bakeoff.py:_new_model (25–43).

<a id="topic-2"></a>

### [P0] 2. The v5 controller accepts, blocks, and expires policy changes

**A. WHAT TO SAY (15–30 seconds)**

> Dynamic means the active scheduling policy can change during one simulation. Reviews happen after an epoch is due, at the next dispatch boundary. We protect first service, require enough dwell, check arrival and I/O pressure, and return excursions to MLFQ.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/dynamic.py` → `run_dynamic / _tail_action / _protected`.

**Chunk 1.** Focus on source lines **508, 509, 530, 531, 532**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **508–532**.

```python
        if state.current_time >= next_epoch and state.ready:
            while next_epoch <= state.current_time:
                next_epoch += config.epoch_ticks
            started = perf_counter_ns()
            features = extract_dynamic_features(
                state, active, last_switch + config.dwell_epochs * config.epoch_ticks - state.current_time,
            )
            if model is None:
                if config.fallback_policy is None:
                    raise ValueError("an unavailable model requires an explicit fallback policy")
                selected, confidence = config.fallback_policy, 0.0
            else:
                selected, confidence = _prediction(model, features, dynamic_action_names(config))
                selected = _resolve_action(selected, active)
            fallback = config.fallback_policy is not None and (model is None or confidence < config.confidence_threshold)
            if fallback:
                selected = config.fallback_policy
            selected, safety_reason = _tail_action(features, active, selected, config)
            safety_return = safety_reason in {"excursion_expired", "first_response_return"}
            # Cost regressors use an absolute predicted advantage over the active
            # policy. This is a margin safeguard, not a calibrated probability.
            margin_ok = not hasattr(model, "switch_allowed") or model.switch_allowed(features, active, selected)
            dwell_elapsed = state.current_time - last_switch >= config.dwell_epochs * config.epoch_ticks
            protected = _protected(features, active, selected, config)
            accepted = selected != active and dwell_elapsed and not protected and (safety_return or fallback or (confidence >= config.confidence_threshold and margin_ok))
```

**Chunk 2.** Focus on source lines **107, 108, 120, 121, 122**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **103–123**.

```python
def _tail_action(features, active, selected, config):
    """Bound excursions to the training horizon; assess observed pressure only."""
    if not config.response_tail_protection:
        return selected, None
    if active != "MLFQ":
        if features["dwell_remaining_ticks"] <= 0:
            return "MLFQ", "excursion_expired"
        unserved = features["first_service_ready_count"]
        urgent = unserved > 0 and (
            unserved >= 2 or features["first_service_wait_max"] >= config.epoch_ticks
            or features["ready_wait_p95"] >= config.epoch_ticks or features["recent_arrivals"] > 0)
        return ("MLFQ", "first_response_return") if urgent else (selected, None)
    if selected != "MLFQ" and not features["first_service_ready_count"]:
        # One observed quiet dwell establishes a lull; v6 adds another before
        # committing to an excursion that cannot immediately react to arrivals.
        quiet_window = config.epoch_ticks * config.dwell_epochs * config.arrival_quiet_dwell_periods
        if features["arrival_quiet_ticks"] < quiet_window:
            return active, "arrival_risk"
        if features["io_returns"] > 0 and features["ready_count"] > 1 and features["ready_wait_p95"] >= config.epoch_ticks:
            return active, "io_ready_pressure"
    return selected, None
```

**Chunk 3.** Focus on source lines **542, 543, 547, 548, 549**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **542–554**.

```python
            if accepted:
                _switch_policy(state, active, selected)
                active = selected
                last_switch = state.current_time
                _rebuild_ready(state, active, rr_config)
            decisions.append(RoutingDecision(
                state.current_time, selected, active, confidence, accepted, reason, features,
                (perf_counter_ns() - started) / 1_000_000,
            ))
            state.recent_arrivals = state.io_returns = 0
        _dispatch(state, active, rr_config)
    return DynamicResult(_simulation(state, "Dynamic Adaptive"), config.initial_policy, active, decisions,
                         _percentile([decision.transition_ms for decision in decisions], 0.99))
```

**C. EXPLAIN THE CODE**

**Chunk 1:** At a due review, skipped epochs advance without replaying each missed review. Features include remaining dwell. Missing-model or low-confidence cases select an explicit fallback. The final Boolean combines a different action, elapsed dwell, first-service protection, and either a safety return, fallback, or confidence-plus-margin.

**Chunk 2:** _tail_action may replace the proposed action. Outside MLFQ, expiry asks to return; urgent unserved jobs also request return. Leaving MLFQ needs an observed quiet window, and recent I/O plus waiting pressure may veto it. These are observed conditions, not predictions of future arrivals.

**Chunk 3:** Accepted switches rebuild ready ordering and update last_switch. Every review records active policy, selected post-guard action, acceptance, reason, features and measured Python duration. Dispatch then executes under active.

Loaded v5 configuration: epoch_ticks=10, dwell_epochs=2 (minimum 20 ticks), confidence_threshold=0.8, initial/fallback/continuation MLFQ, explicit_no_switch=True, first_service_protection=True, response_tail_protection=True, quanta=(1,2,4), aging=40. arrival_quiet_dwell_periods defaults to 1 when absent from older metadata. No Switch resolves to active before final acceptance. _protected prevents leaving MLFQ while a ready job has never run. A safety return bypasses the cost margin, but NOT minimum dwell. Long non-preemptive bursts can delay the next review far beyond 10 ticks; the code does not interrupt a burst just because the review timer expired. Entering MLFQ resets ready jobs to its top level, preserving completed service and I/O state.

**D. WHY WE USED THIS APPROACH**

The dispatch-boundary rule and bounded-excursion intention are explicit in comments. Dwell reduces oscillation; first-service and quiet-period checks protect responsiveness using available history. A fixed MLFQ baseline avoids model overhead and prediction risk; a timer that immediately preempts would react faster but change the simulation contract and policy semantics. This rationale is partly engineering interpretation. The safeguards reduce risk, not prove starvation freedom or a hard response bound.

**E. FACULTY QUESTIONS**

- **Can an urgent return ignore dwell?** No. accepted still requires dwell_elapsed, so it can record response_dwell_blocked.
- **Is the decision period exactly 10 ticks?** It is a due-time interval; the next safe dispatch boundary determines the actual review time.
- **What if no model exists?** run_dynamic accepts None only with explicit fallback. The dashboard loader instead rejects a missing artifact before this fallback path.

**F. DON'T SAY THIS**

Do not claim instant switching, online learning, guaranteed bounded response, or that every logged selected action is the original tree proposal. selected is post-resolution/post-safety.

**G. CONNECTION**

autoscheduler/model.py:PolicyCostModel; autoscheduler/dynamic.py:_switch_policy (291–296), _dispatch (302–392); tests/test_dynamic_v5.py:TailProtectionTests.

<a id="topic-3"></a>

### [P0] 3. Observed-state features and the boundary against future knowledge

**A. WHAT TO SAY (15–30 seconds)**

> The controller gets queue counts, waiting times, past CPU service and completed bursts. It also knows its current policy and dwell state. The simulator knows the whole workload to execute it, but we do not pass future arrivals or remaining CPU work into this model.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/dynamic.py` → `extract_dynamic_features / _prediction`.

**Chunk 1.** Focus on source lines **426, 427, 438, 439, 440**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **422–440**.

```python
def extract_dynamic_features(
    state: _State, active_policy: str = "Round Robin", dwell_remaining_ticks: int = 0,
) -> dict[str, float]:
    """Read only execution history and currently observed queues, in simulator ticks."""
    candidates = [item.process for item in state.ready] + [process for _, process, _, _ in state.blocked]
    priorities = [process.priority for process in candidates]
    waits = [max(0, state.current_time - item.time) for item in state.ready]
    service: dict[str, int] = {}
    for pid, start, end in state.timeline:
        if pid != "CS":
            service[pid] = service.get(pid, 0) + end - start
    durations = state.completed_burst_durations
    first_waits = [max(0, state.current_time - item.time) for item in state.ready if item.process.pid not in service]
    return {
        "ready_count": float(len(state.ready)), "blocked_count": float(len(state.blocked)),
        "completed_burst_mean": mean(durations) if durations else 0.0,
        "completed_burst_variance": pvariance(durations) if durations else 0.0,
        "observed_service_mean": mean(service.values()) if service else 0.0,
        "observed_service_variance": pvariance(service.values()) if service else 0.0,
```

**Chunk 2.** Focus on source lines **447, 448, 451, 452, 453**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **441–454**.

```python
        "priority_mean": mean(priorities) if priorities else 0.0,
        "ready_wait_mean": mean(waits) if waits else 0.0,
        "ready_wait_max": float(max(waits, default=0)),
        "recent_arrivals": float(state.recent_arrivals),
        "io_returns": float(state.io_returns),
        "io_return_ratio": state.io_returns / max(1, state.recent_arrivals + state.io_returns),
        "active_policy_index": float(tuple(dict.fromkeys((*DYNAMIC_POLICY_NAMES, *ALGORITHMS))).index(active_policy)),
        "dwell_remaining_ticks": float(max(0, dwell_remaining_ticks)),
        "first_service_ready_count": float(len(first_waits)),
        "first_service_wait_max": float(max(first_waits, default=0)),
        "ready_wait_p50": _percentile(waits, .5), "ready_wait_p95": _percentile(waits, .95),
        "arrival_quiet_ticks": float(max(0, state.current_time - state.last_observed_arrival))
                               if state.last_observed_arrival is not None else 0.,
    }
```

**Chunk 3.** Focus on source lines **458, 459, 466, 467, 468**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **457–469**.

```python
def _prediction(model, features: dict[str, float], policies=DYNAMIC_POLICY_NAMES) -> tuple[str, float]:
    row = [[features[name] for name in DYNAMIC_FEATURE_NAMES]]
    selected = str(model.predict(row)[0])
    if selected not in policies:
        raise ValueError(f"model selected ineligible policy for this track: {selected}")
    if hasattr(model, "predict_proba") and hasattr(model, "classes_"):
        probabilities = model.predict_proba(row)[0]
        confidence = float(max(probabilities))
    else:
        # Deterministic selectors have no classifier probability. Cost-model
        # decisions are guarded separately by their predicted improvement margin.
        confidence = 1.0
    return selected, confidence
```

**C. EXPLAIN THE CODE**

**Chunk 1:** Ready and blocked queues supply observed membership and priorities. CPU service is reconstructed from past timeline entries, excluding CS. Completed bursts are accumulated only after completion; first_waits finds jobs with no service history.

**Chunk 2:** The vector contains recent arrivals/I/O returns, policy index, dwell, wait quantiles and time since the last released arrival. Wait here means time since this ready entry, not the process's total lifetime waiting.

**Chunk 3:** Feature names enforce one consistent input order. Ineligible actions raise an error. Classifiers use maximum predict_proba; deterministic cost models use the interface confidence 1.0.

There are 19 features in DYNAMIC_FEATURE_NAMES (26–33). _release records observed arrivals and I/O returns; run_dynamic resets those two recent counters after a review, so their window is since the previous review rather than an exact fixed wall-clock period. Service means include previously served processes, including completed ones. Integer active_policy_index is an ordinal encoding, not one-hot. Distinguish this from autoscheduler/features.py:extract_features, whose nine whole-workload inputs include total CPU bursts and all arrivals. Dashboard feature displays use that offline extractor but do not feed those values into v5.

**D. WHY WE USED THIS APPROACH**

An explicit feature tuple prevents column-order drift and is checked when loading the artifact. Past-service features make simulation inference plausibly observable. Alternative raw event sequences or per-process features preserve more information but enlarge the model and state handling; aggregates lose identity and temporal detail. One-hot policy encoding avoids artificial ordinal distance but requires a different saved schema. These are reasonable tradeoffs inferred from the implementation, not evidence of a completed design comparison.

**E. FACULTY QUESTIONS**

- **Is completed_burst_mean leaked future work?** No; it uses bursts already finished. The remaining_time field is not read here.
- **Why can the engine read pending arrivals?** The execution oracle needs input events; the model feature extractor is a separate boundary.
- **Does the tree use all 19 inputs?** The schema accepts all 19; this fitted v5 tree splits on only three.

**F. DON'T SAY THIS**

Do not call the old offline workload features real-time observable. Do not equate ready_wait_p95 with P95 first-response outcome. Do not claim the schema alone proves usefulness under distribution shift.

**G. CONNECTION**

tests/test_dynamic_contract.py:DynamicObservabilityTests (24–84); autoscheduler/features.py:extract_features; autoscheduler/dynamic.py:_release (236–255).

<a id="topic-4"></a>

### [P0] 4. Event-driven execution and preservation of state during switching

**A. WHAT TO SAY (15–30 seconds)**

> Execution jumps between dispatch, arrival, I/O and quantum boundaries instead of iterating through every empty tick. A selected process consumes part or all of its current CPU burst, then completes, blocks for I/O, or returns to the ready list. Switching policies changes ordering while keeping the same execution state.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/dynamic.py` → `_dispatch / _new_state; simulator.engine.simulate`.

**Chunk 1.** Focus on source lines **306, 307, 322, 323, 324**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **302–324**.

```python
def _dispatch(
    state: _State, policy: str, priority_rr_config: dict,
    decision_times_ns: list[int] | None = None,
) -> None:
    _release(state, state.current_time)
    if not state.ready:
        times = [process.arrival_time for process in state.pending]
        times.extend(wake_time for wake_time, *_ in state.blocked)
        if not times:
            return
        state.current_time = min(times)
        _release(state, state.current_time)
    started = perf_counter_ns()
    _rebuild_ready(state, policy, priority_rr_config)
    ready = state.ready.pop(0)
    if decision_times_ns is not None:
        decision_times_ns.append(perf_counter_ns() - started)
    process = ready.process
    switch_cost = priority_rr_config["context_switch_cost"] if policy == "Priority RR" else 0
    if state.last_pid is not None and state.last_pid != process.pid and switch_cost:
        state.timeline.append(("CS", state.current_time, state.current_time + switch_cost))
        state.current_time += switch_cost
        _release(state, state.current_time)
```

**Chunk 2.** Focus on source lines **331, 332, 344, 345, 346**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **330–346**.

```python
    while process.remaining_time:
        run_for = process.remaining_time
        if policy in {"Round Robin", "Priority RR"}:
            run_for = min(run_for, priority_rr_config["quantum"])
        elif policy == "MLFQ":
            run_for = min(run_for, state.mlfq_quanta[ready.queue_level] - ready.quantum_used)
            if ready.queue_level > 0:
                events = [state.pending[0].arrival_time] if state.pending else []
                events.extend(wake for wake, *_ in state.blocked)
                events.extend(item.aging_since + state.mlfq_aging_threshold for item in state.ready if item.queue_level > 0)
                if events:
                    run_for = min(run_for, max(0, min(events) - state.current_time))
        elif policy == "SRTF":
            next_events = [state.pending[0].arrival_time] if state.pending else []
            next_events.extend(wake_time for wake_time, *_ in state.blocked)
            if next_events:
                run_for = min(run_for, min(next_events) - state.current_time)
```

**Chunk 3.** Focus on source lines **379, 380, 390, 391, 392**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **375–392**.

```python
    if process.remaining_time:
        level, used = 0, 0
        if policy == "MLFQ":
            level, used = ready.queue_level, ready.quantum_used
            if used >= state.mlfq_quanta[level]:
                level, used = min(level + 1, 2), 0
        state.ready.append(_Ready(state.current_time, state.sequence, process, process.priority, False, level, used))
        state.sequence += 1
    else:
        state.completed_burst_durations.append(state.burst_service.pop(process.pid))
    if not process.remaining_time and process.burst_index < len(process.cpu_bursts) - 1:
        wake_time = state.current_time + process.io_bursts[process.burst_index]
        process.burst_index += 1
        process.remaining_time = process.cpu_bursts[process.burst_index]
        state.blocked.append((wake_time, process, max(1, process.priority - 1), True))
    elif not process.remaining_time:
        process.completion_time = state.current_time
        state.completed.append(process)
```

**C. EXPLAIN THE CODE**

**Chunk 1:** _dispatch receives the mutable state and active policy. It releases due events, jumps across idle time, rebuilds ordering and removes one ready entry. Priority RR alone receives a charged context-switch cost in this dynamic path.

**Chunk 2:** Non-preemptive execution starts with the whole current remaining burst. RR limits it by quantum, MLFQ by level budget and relevant events, and oracle SRTF by the next event.

**Chunk 3:** An unfinished process requeues; full MLFQ quantum demotes it. A completed CPU burst becomes history. Another burst schedules an I/O wakeup; final completion sets completion_time and appends exactly once.

_new_state deep-copies and resets Process inputs, sorts arrivals, and rejects duplicate PIDs. _State holds pending, ready, blocked, completed and timeline lists. _release orders arrival/wakeup events by time and PID and assigns a sequence. A timeline slice adds service and reduces remaining_time; state.current_time moves to its end. Termination is no pending, ready or blocked processes. The static wrappers use simulator/engine.py:simulate; the dynamic controller has its own stateful dispatch implementation. Both share Process, metric definitions and intended semantics, but it is inaccurate to say dynamic execution calls simulate for each dispatch.

**D. WHY WE USED THIS APPROACH**

List queues and the small-workload rationale are explicitly commented in simulator/engine.py:58. Lists make the behavior easy to inspect; deque/heaps would scale better but complicate several ordering keys. Event-driven execution skips idle ticks compared with tick-driven loops, but long bursts with tiny quanta still create many events. Separate dynamic state supports continuation across policy changes; duplicate execution logic introduces equivalence-maintenance risk.

**E. FACULTY QUESTIONS**

- **Does a policy change restart the simulation?** No; _switch_policy changes MLFQ bookkeeping only when entering it, retaining service and pending/blocked/completed state.
- **Is Python elapsed time simulated CPU time?** No. current_time is simulated ticks; perf_counter_ns measures host execution overhead separately.
- **Why can a peak workload time out?** Large burst proxies and small quanta generate many list operations, slices and reviews despite event-driven execution.

**F. DON'T SAY THIS**

Do not claim a real CPU, multiprocessing, kernel scheduling, or a single implementation body for both static and dynamic dispatch.

**G. CONNECTION**

simulator/engine.py:simulate (32–249); autoscheduler/dynamic.py:_switch_policy (291–296), _simulation (403–419); tests/test_azure_runtime_equivalence.py.

<a id="topic-5"></a>

### [P0] 5. MLFQ feedback, aging and the tuned static comparator

**A. WHAT TO SAY (15–30 seconds)**

> MLFQ gives new and returning jobs the top queue, then moves CPU-heavy jobs down when they consume a full quantum. Waiting jobs can move up through aging. The recommended tuned baseline uses quanta 1, 2 and 4, with aging 40; the default MLFQ uses 2, 4 and 8, with aging 20.

**B. WHAT CODE TO SHOW**

Open `simulator/engine.py` → `simulate.age_ready / take_ready / MLFQ requeue block`.

**Chunk 1.** Focus on source lines **94, 95, 98, 99, 100**.

Source: [simulator/engine.py](../simulator/engine.py), lines **90–101**.

```python
    def age_ready() -> None:
        nonlocal sequence
        if policy != "mlfq":
            return
        eligible = (item for item in ready if item.queue_level > 0
                    and current_time - item.aging_since >= (aging_threshold or 1))
        for item in sorted(eligible, key=lambda candidate: candidate.sequence):
            item.queue_level -= 1
            item.quantum_used = 0
            item.aging_since = current_time
            item.sequence = sequence
            sequence += 1
```

**Chunk 2.** Focus on source lines **173, 174, 182, 183, 184**.

Source: [simulator/engine.py](../simulator/engine.py), lines **168–184**.

```python
        while process.remaining_time:
            run_for = process.remaining_time
            if policy in {"rr", "priority_rr"}:
                run_for = min(run_for, quantum or run_for)
            elif policy == "mlfq":
                level_quantum = (queue_quanta or ())[ready_process.queue_level]
                run_for = min(run_for, level_quantum - ready_process.quantum_used)
                if ready_process.queue_level > 0:
                    next_events = ([pending[0].arrival_time] if pending else [])
                    next_events.extend(wake_time for wake_time, *_ in blocked)
                    next_events.extend(
                        item.aging_since + (aging_threshold or 1)
                        for item in ready
                        if item.queue_level > 0
                    )
                    if next_events:
                        run_for = min(run_for, max(0, min(next_events) - current_time))
```

**Chunk 3.** Focus on source lines **227, 228, 241, 242, 243**.

Source: [simulator/engine.py](../simulator/engine.py), lines **224–243**.

```python
        if process.remaining_time:
            if policy == "mlfq":
                level_quantum = (queue_quanta or ())[ready_process.queue_level]
                if ready_process.quantum_used >= level_quantum:
                    ready_process.queue_level = min(ready_process.queue_level + 1, len(queue_quanta or ()) - 1)
                    ready_process.quantum_used = 0
                ready.append(_Ready(
                    current_time, sequence, process, process.priority, False,
                    ready_process.queue_level, ready_process.quantum_used,
                ))
            else:
                ready.append(_Ready(current_time, sequence, process, process.priority, False))
            sequence += 1
            continue

        if process.burst_index < len(process.cpu_bursts) - 1:
            wake_time = current_time + process.io_bursts[process.burst_index]
            process.burst_index += 1
            process.remaining_time = process.cpu_bursts[process.burst_index]
            blocked.append((wake_time, process, max(1, process.priority - 1), True))
```

**C. EXPLAIN THE CODE**

**Chunk 1:** age_ready promotes an eligible waiting entry one level, clears its quantum use, refreshes aging time and assigns a new sequence. This is not a global simultaneous boost to the top queue.

**Chunk 2:** The active level supplies its remaining quantum. A lower-level job checks new arrivals, I/O wakeups and promotion times, allowing higher-level work to interrupt it.

**Chunk 3:** Exhausting the level quantum demotes by one level, capped at the bottom. Preemptions preserve unused quantum. I/O completion later creates a fresh ready entry at default level zero.

take_ready chooses (queue_level, sequence), so each level follows FIFO sequence. After an intermediate event, only a higher queue preempts; equal-level arrivals do not. A promoted or requeued entry receives new timing/sequence bookkeeping. scheduler/mlfq.py:mlfq passes settings to the static engine and optionally exposes ready-selection timings. Dynamic MLFQ mirrors these rules in _age_mlfq/_dispatch. The v5 experiment tunes nine combinations, then freezes one comparator before fitting/evaluating model families; inspect dynamic_v5_experiment.py:158–178 and static_selection.json.

**D. WHY WE USED THIS APPROACH**

Feedback exploits observed CPU consumption without knowing future burst sizes; FCFS is simpler but long bursts delay first service, while RR treats all runnable jobs uniformly. Aging mitigates long waits at lower levels. Compared with fixed RR, MLFQ adds state and parameter sensitivity; its response advantage may increase total waiting. Those behavior statements follow code; choosing these specific values is supported by the saved development selection, not by a universal optimality proof.

**E. FACULTY QUESTIONS**

- **Is tuned MLFQ learned online?** No. It is a fixed scheduler with development-selected parameters.
- **Does aging prove no starvation?** It is a mitigation mechanism. The project reports finite-workload diagnostics, not a general liveness theorem.
- **Is MLFQ free of context-switch overhead?** The wrapper supports a cost, but the current recommended baseline and v5 MLFQ use zero charged cost.

**F. DON'T SAY THIS**

Do not mix default and tuned parameters. Do not call the aging threshold an upper bound on a process's first response.

**G. CONNECTION**

scheduler/mlfq.py:9–24; configs/research_status.json:recommended_static; autoscheduler/dynamic.py:280–296, 334–381; tests/test_mlfq.py.

<a id="topic-6"></a>

### [P0] 6. Classical policies, oracle policies and real preemption semantics

**A. WHAT TO SAY (15–30 seconds)**

> The ready-selection key defines each classical policy. FCFS uses ready time, RR uses queue sequence, and Priority uses the smallest priority number. SJF and SRTF use declared CPU information, so they are oracle references here and are excluded from realistic v5 actions.

**B. WHAT CODE TO SHOW**

Open `simulator/engine.py` → `simulate.take_ready`.

**Chunk 1.** Focus on source lines **105, 106, 119, 120, 121**.

Source: [simulator/engine.py](../simulator/engine.py), lines **103–123**.

```python
    def take_ready() -> _Ready:
        age_ready()
        if policy == "rr":
            index = min(range(len(ready)), key=lambda i: ready[i].sequence)
        elif policy == "priority_rr":
            index = min(
                range(len(ready)),
                key=lambda i: (
                    1 if ready[i].priority <= 1 else max(1, ready[i].priority - (current_time - ready[i].time) // (aging_interval or 1)),
                    ready[i].sequence,
                ),
            )
        elif policy in {"sjf", "srtf"}:
            index = min(
                range(len(ready)),
                key=lambda i: (
                    ready[i].process.remaining_time if policy == "srtf" else ready[i].process.burst_time,
                    ready[i].time,
                    ready[i].process.pid,
                ),
            )
```

**Chunk 2.** Focus on source lines **124, 125, 134, 135, 136**.

Source: [simulator/engine.py](../simulator/engine.py), lines **124–137**.

```python
        elif policy == "priority":
            index = min(
                range(len(ready)),
                key=lambda i: (
                    ready[i].process.priority,
                    ready[i].time,
                    ready[i].process.pid,
                ),
            )
        elif policy == "mlfq":
            index = min(range(len(ready)), key=lambda i: (ready[i].queue_level, ready[i].sequence))
        else:
            index = min(range(len(ready)), key=lambda i: (ready[i].time, ready[i].process.pid))
        return ready.pop(index)
```

**Chunk 3.** Focus on source lines **22, 23, 34, 35, 36**.

Source: [autoscheduler/evaluation.py](../autoscheduler/evaluation.py), lines **18–36**.

```python
ALGORITHMS = {
    "FCFS": (fcfs, {}),
    "SJF": (sjf, {}),
    "SRTF": (srtf, {}),
    "Round Robin": (round_robin, {"quantum": 2}),
    "Priority": (priority_scheduling, {}),
    "Priority RR": (
        priority_round_robin,
        {"quantum": 2, "aging_interval": 8, "context_switch_cost": 1},
    ),
}

SELECTOR_ALGORITHMS = ALGORITHMS

# The historical six-policy simulation registry intentionally includes oracles.
DEPLOYABLE_ALGORITHMS = {
    name: ALGORITHMS[name] for name in ("FCFS", "Round Robin", "Priority", "Priority RR")
}
DEPLOYABLE_ALGORITHMS["MLFQ"] = (mlfq, {"quanta": (2, 4, 8), "aging_threshold": 20})
```

**C. EXPLAIN THE CODE**

**Chunk 1:** RR selects minimum sequence. Priority RR uses an aged effective priority with sequence as tie-breaker. SJF compares process.burst_time, which is total declared CPU across bursts; SRTF compares current remaining_time.

**Chunk 2:** Priority uses original process priority, then ready time and PID. MLFQ uses level and sequence. FCFS's fallback key is ready time then PID.

**Chunk 3:** The historical registry has six policies including SJF/SRTF. The realistic registry has FCFS, RR, Priority, Priority RR and MLFQ. Static RR quantum is 2; Priority RR also has aging 8 and cost 1.

FCFS/SJF/Priority are non-preemptive for the current CPU burst, not the entire multi-burst lifetime. RR requeues after its quantum; arrivals are released before the preempted job is reinserted. SRTF rechecks at arrival/I/O events and preempts only for strictly less remaining work. Priority RR rotates within priority order and does not instantly preempt mid-quantum for an arrival; its I/O-ready entry receives max(1, original priority−1). Priority 0 is accepted as neutral Azure input; do not assume every field starts at 1. An older RR20-SRTF experiment in autoscheduler/benefit.py:117–139 observes with RR then switches once to oracle SRTF; it is not the repeated realistic v5 controller.

**D. WHY WE USED THIS APPROACH**

Explicit ordering keys make policy differences and deterministic ties easy to test. A heap per priority or an estimated-burst SJF is an alternative. Estimated SJF would remove exact future-work dependence but introduce prediction error; it is not implemented here. Priority RR combines responsiveness and priority at the cost of aging bookkeeping and charged overhead. The static engine's SJF total-work semantics are deliberate in tests/test_schedulers.py:15–23, even though UI wording says next burst.

**E. FACULTY QUESTIONS**

- **What does SJF actually minimize?** Total declared CPU burst_time, not the next cpu_bursts element.
- **Can v5 dynamically choose SRTF?** Not in the realistic track. Only an explicit oracle_simulation configuration includes it.
- **Does ordinary Priority age jobs?** No. The aging formula belongs to Priority RR; ordinary Priority uses the original priority.

**F. DON'T SAY THIS**

Do not repeat the dashboard's 'shortest known next CPU burst' description for SJF. Do not describe every scheduler as preemptive or every PID change as an ML policy change.

**G. CONNECTION**

scheduler/fcfs.py, sjf.py, srtf.py, round_robin.py, priority.py, priority_rr.py wrap simulate; tests/test_schedulers.py:15–161.

<a id="topic-7"></a>

### [P0] 7. Process invariants and CPU/I/O burst representation

**A. WHAT TO SAY (15–30 seconds)**

> A Process stores its arrival, priority and total CPU demand. It can contain several CPU bursts separated by I/O durations. remaining_time tracks only the current CPU burst, while start and completion times record its first and final execution.

**B. WHAT CODE TO SHOW**

Open `simulator/process.py` → `Process.__post_init__ / reset`.

**Chunk 1.** Focus on source lines **30, 31, 36, 37, 38**.

Source: [simulator/process.py](../simulator/process.py), lines **28–38**.

```python
    pid: str
    arrival_time: int
    burst_time: int
    priority: int = 0
    cpu_bursts: Tuple[int, ...] | None = None
    io_bursts: Tuple[int, ...] = ()
    remaining_time: int = field(init=False)
    start_time: int = field(default=-1, init=False)
    completion_time: int = field(default=-1, init=False)
    burst_index: int = field(default=0, init=False)
    post_io_response_times: List[int] = field(default_factory=list, init=False)
```

**Chunk 2.** Focus on source lines **50, 51, 58, 59, 60**.

Source: [simulator/process.py](../simulator/process.py), lines **40–60**.

```python
    def __post_init__(self):
        if not self.pid:
            raise ValueError("pid must not be empty")
        if self.arrival_time < 0:
            raise ValueError("arrival_time must be non-negative")
        if self.burst_time <= 0:
            raise ValueError("burst_time must be positive")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")

        self.cpu_bursts = tuple(self.cpu_bursts or (self.burst_time,))
        self.io_bursts = tuple(self.io_bursts)
        if any(burst <= 0 for burst in self.cpu_bursts):
            raise ValueError("CPU bursts must be positive")
        if any(burst <= 0 for burst in self.io_bursts):
            raise ValueError("I/O bursts must be positive")
        if len(self.io_bursts) != len(self.cpu_bursts) - 1:
            raise ValueError("I/O bursts must occur between CPU bursts")
        if sum(self.cpu_bursts) != self.burst_time:
            raise ValueError("burst_time must equal the sum of CPU bursts")
        self.remaining_time = self.cpu_bursts[0]
```

**C. EXPLAIN THE CODE**

**Chunk 1:** Declared inputs are separate from mutable scheduling fields. start_time and completion_time begin at −1; burst_index points to the current CPU burst.

**Chunk 2:** Missing CPU burst tuples default to one burst. CPU and I/O durations must be positive, I/O count must be exactly one less than CPU burst count, and total CPU must equal burst_time.

Constructors are used by workload generators, dashboard.adapter.processes, Azure loading and replay tools. The engines copy inputs, call reset, and require unique PIDs across the workload. reset restores the first burst and clears post-I/O responses. total_io_time sums the declared blocked intervals for metric accounting. Dataclass annotations say int, but this constructor's comparisons do not enforce exact integer types; dataset validators have additional unit/integer checks. Process priority defaults to 0 even though the introductory docstring gives 1 as the highest example.

**D. WHY WE USED THIS APPROACH**

The CPU/I/O tuple representation directly supports ready→running→blocked→ready behavior with a small deterministic state. A single CPU burst would be simpler but omit blocking; a detailed device/event model would be richer but require more observations and assumptions. Input-copying makes repeated policy comparisons fair at memory cost. These are engineering interpretations; the validation code itself provides the invariant evidence.

**E. FACULTY QUESTIONS**

- **Why subtract I/O from waiting?** Blocked time is not waiting in the CPU ready queue.
- **Can two processes share a PID?** The Process constructor cannot know that; engine initialization rejects duplicate workload PIDs.

**F. DON'T SAY THIS**

Do not say remaining_time always equals total unfinished process CPU, or that type annotations alone enforce integer input.

**G. CONNECTION**

simulator/engine.py:58–63,239–247; autoscheduler/dynamic.py:_new_state; simulator/simulator.py:compute_metrics.

<a id="topic-8"></a>

### [P0] 8. Metric definitions, weighted score and what a win means

**A. WHAT TO SAY (15–30 seconds)**

> Response is arrival to first CPU service. Turnaround is arrival to completion. Waiting subtracts both CPU and I/O from turnaround. We compare several normalized metrics using a weighted score, but separately inspect response tails and starvation flags because a better average score can hide bad delays.

**B. WHAT CODE TO SHOW**

Open `simulator/simulator.py` → `compute_metrics / run_simulation; score_result_against_reference`.

**Chunk 1.** Focus on source lines **71–73**.

Source: [simulator/simulator.py](../simulator/simulator.py), lines **69–85**.

```python
    metrics = []
    for p in scheduled:
        turnaround = p.completion_time - p.arrival_time
        waiting    = turnaround - p.burst_time - p.total_io_time
        response   = p.start_time - p.arrival_time
        metrics.append(ProcessMetrics(
            pid             = p.pid,
            arrival_time    = p.arrival_time,
            burst_time      = p.burst_time,
            priority        = p.priority,
            start_time      = p.start_time,
            completion_time = p.completion_time,
            turnaround_time = turnaround,
            waiting_time    = waiting,
            response_time   = response,
            post_io_response_times=tuple(p.post_io_response_times),
        ))
```

**Chunk 2.** Focus on source lines **95, 96, 99, 100, 101**.

Source: [autoscheduler/evaluation.py](../autoscheduler/evaluation.py), lines **86–102**.

```python
def score_result_against_reference(
    result: SimulationResult,
    reference_results: dict[str, SimulationResult],
    reference_names=None,
) -> float:
    """Score one result using metric bounds frozen by reference policies."""
    names = tuple(reference_names or reference_results)
    score = 0.0
    for metric, weight in SCORE_WEIGHTS.items():
        values = [getattr(reference_results[name], metric) for name in names]
        low, high = min(values), max(values)
        if high == low:
            continue
        value = getattr(result, metric)
        normalized = ((high - value) if metric in {"cpu_utilization", "throughput"} else (value - low)) / (high - low)
        score += weight * normalized
    return score
```

**Chunk 3.** Focus on source lines **32, 33, 35, 36, 37**.

Source: [autoscheduler/fairness.py](../autoscheduler/fairness.py), lines **25–38**.

```python
def aggregate_fairness(metrics: list[ProcessMetrics]) -> dict[str, float | int | None]:
    """Aggregate pooled process fairness metrics without affecting scheduler scores."""
    waits = [item.waiting_time for item in metrics]
    priority_waits = [item.waiting_time for item in metrics if item.priority in {1, 2}]
    io_responses = [delay for item in metrics for delay in item.post_io_response_times]
    return {
        "max_waiting_time": max(waits, default=0),
        "p95_waiting_time": quantiles(waits, n=100, method="inclusive")[94] if len(waits) > 1 else (waits[0] if waits else 0),
        "starvation_count": sum(item.waiting_time > 3 * item.burst_time for item in metrics),
        "priority_mean_waiting_time": _mean_or_none(priority_waits),
        "priority_max_waiting_time": max(priority_waits) if priority_waits else None,
        "post_io_mean_response_time": _mean_or_none(io_responses),
        "post_io_max_response_time": max(io_responses) if io_responses else None,
    }
```

**C. EXPLAIN THE CODE**

**Chunk 1:** Completed Process records become ProcessMetrics. The actual waiting formula includes total_io_time, correcting the incomplete formula in the module's top docstring.

**Chunk 2:** Reference policies freeze metric bounds. Lower-is-better metrics normalize upward from the minimum; utilization and throughput reverse direction. A zero-range metric contributes nothing; scores are not clipped.

**Chunk 3:** Fairness aggregates completed-process samples. starvation_count flags waiting > 3×CPU burst_time; priority and post-I/O groups are separate summaries, with None for an absent group.

For process i: Tᵢ=Cᵢ−Aᵢ; Wᵢ=Tᵢ−Bᵢ−Iᵢ; Rᵢ=Sᵢ−Aᵢ. CPU utilization=non-CS timeline duration/makespan; throughput=completed count/makespan; idle=makespan−busy−CS. Makespan is the last timeline end measured from zero, so initial idle time counts. PID transitions count changes between non-CS slices, independently of charged overhead. P95 uses linear interpolation at 0.95(n−1), implemented in dynamic.py:_percentile (472–478). Mean workload P95 is not the P95 of all pooled processes. Score weights are waiting .30, response .25, turnaround .20, utilization .15, throughput .10. For minimizing metric m, n=(x−min)/(max−min); maximizing uses (max−x)/(max−min); score=Σwₘnₘ. Fixed-reference scores can leave [0,1]. Synthetic reports use six historical reference policies; current Azure generalization uses five deployable references. Costs from these scopes are not interchangeable.

**D. WHY WE USED THIS APPROACH**

Normalization combines differently scaled measures; frozen bounds prevent changing the measuring scale when a new candidate is added. A single objective such as P95 or a Pareto frontier is a valid alternative. Chosen weights express a project preference, not a universal optimum; correlated waiting/turnaround can double-emphasize similar effects. P95 and starvation are not weighted-score terms, motivating separate gates. The formulas and gates are explicit; the rationale is an interpretation.

**E. FACULTY QUESTIONS**

- **Is a negative action cost an impossible negative waiting time?** No; it is a score difference relative to MLFQ continuation.
- **Does starvation_count count processes that never finish?** No. It is a threshold diagnostic on completed processes.
- **Is inference latency included in simulated makespan?** No. Host-side timing is recorded separately; modeled CS ticks are the explicit simulated overhead.

**F. DON'T SAY THIS**

Do not use classifier accuracy as a scheduler speedup, compare scores across normalization scopes, or label average workload P95 as pooled P95.

**G. CONNECTION**

autoscheduler/evaluation.py:SCORE_WEIGHTS; autoscheduler/dynamic.py:_simulation; autoscheduler/dynamic_training.py:validation_metrics; dashboard/adapter.py:comparison.

<a id="topic-9"></a>

### [P0] 9. Which fitted model the current demo really loads

**A. WHAT TO SAY (15–30 seconds)**

> The dashboard explicitly loads the original v5 policy-cost artifact, checks its hash, and checks the feature and policy configuration. The ordinary demo workloads may stay on MLFQ. The selected illustrative workload really makes two policy transitions, but it is not independent evidence that v5 is better overall.

**B. WHAT CODE TO SHOW**

Open `dashboard/adapter.py` → `_original_v5 / _run_v5 / simulation`.

**Chunk 1.** Focus on source lines **93, 94, 105, 106, 107**.

Source: [dashboard/adapter.py](../dashboard/adapter.py), lines **89–107**.

```python
@lru_cache(maxsize=1)
def _original_v5():
    from autoscheduler.dynamic import DYNAMIC_FEATURE_NAMES, DynamicRouterConfig
    from autoscheduler.model import load_model, load_model_metadata
    path = ROOT / DYNAMIC_V5_ARTIFACT
    if not path.exists():
        raise ValueError('Original v5 artifact is unavailable; select a static policy.')
    expected = read_json('results/real_source_dynamic_review_20261020/dashboard.json')['model_sha256']
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Original v5 artifact hash differs from its verified report.')
    config = DynamicRouterConfig(**load_model_metadata(path)['dynamic_config'])
    model = load_model(path, DYNAMIC_FEATURE_NAMES, expected_dynamic_config=config)
    return model, config


def _run_v5(jobs):
    from autoscheduler.dynamic import run_dynamic
    model, config = _original_v5()
    return run_dynamic(jobs, model, config)
```

**Chunk 2.** Focus on source lines **25, 26, 35, 36, 37**.

Source: [tests/test_switching_demo.py](../tests/test_switching_demo.py), lines **23–37**.

```python
        self.assertEqual(len(data['reproducibility']['input_processes']), 14)
        self.assertEqual(data['reproducibility']['workload_id'], 'dynamic_response_advantage')
        events = data['policy_transitions']
        self.assertEqual([(e['effective_tick'], e['from_policy'], e['to_policy'], e['reason']) for e in events],
                         [(22, 'MLFQ', 'Priority', 'accepted'), (52, 'Priority', 'MLFQ', 'excursion_expired')])
        self.assertTrue(all(e['decision_tick'] == e['effective_tick'] for e in events))
        self.assertEqual(hashlib.sha256(json.dumps(data['timeline']).encode()).hexdigest(),
                         'cb2a66838b852c6aee164ffae4c2841d0a79215ab21e8d8da4dd092536943f80')
        comparison = data['response_comparison']
        dynamic, baseline = comparison['original_v5'], comparison['tuned_mlfq']
        for key, left, right in [('avg_response', 24/14, 31/14), ('p95_response', 4.35, 5.0),
                                 ('avg_waiting', 78.5, 90.71428571428571),
                                 ('weighted_score', 0.08660452383024976, 0.1601457426009788)]:
            self.assertAlmostEqual(dynamic[key], left, places=12)
            self.assertAlmostEqual(baseline[key], right, places=12)
```

**C. EXPLAIN THE CODE**

**Chunk 1:** _original_v5 caches a checked model/config pair. It checks existence and the saved report's SHA256, reconstructs config from metadata and uses load_model. _run_v5 passes this pair to the controller.

**Chunk 2:** This current local test specifies the selected 14-process scenario's two transitions and expected metric values. The transitions were also verified with a tiny in-memory run for this guide; test assertions alone are not presented as a fresh test-suite pass.

Verified artifact: artifacts/dynamic_v5_20261019/policy_cost/model.joblib, SHA256 a8783b65b60aaf381694910affd7e2c2acce4c7c871911b782514d8e37064a64. A read-only load passed, including dashboard hash/config checks. Four small in-memory simulations showed: short_jobs 2 reviews/0 switches, mixed_io 3/0, bursty 3/0, dynamic_response_advantage 24/2. The selected scenario runs MLFQ [0,22), Priority [22,52), MLFQ [52,254). The expiry return waits until tick 52 because dispatch can overrun the nominal horizon. Expected response metrics in the local test are 24/14 versus 31/14 average response and 4.35 versus 5.0 P95; these metric comparisons are test expectations, not newly rerun research results.

**D. WHY WE USED THIS APPROACH**

Explicit artifact identity and schema checking prevent silently substituting a different fitted model. An alternative is automatic discovery/fallback among artifacts, which is more convenient but can obscure provenance. Hash checking proves identity against the saved manifest, not training quality. Caching avoids repeated disk loads but requires server restart/cache clearing to notice replacements. These tradeoffs follow the implementation.

**E. FACULTY QUESTIONS**

- **What happens if the artifact is missing?** The dashboard raises ValueError and the API returns 404; it does not silently show invented predictions.
- **Is the experimental multi-policy model currently selectable?** No. Its helper and artifact remain, but dynamic_multi_policy is absent from WORKLOADS; processes rejects it before that branch runs.
- **Does v5 use the old classifier?** No. _original_v5 names the policy_cost artifact. A separate classifier exists and loads, but is not called here.

**F. DON'T SAY THIS**

Do not claim every preset switches, all five policies appear in the fitted model's trajectory, or the illustrative case proves external superiority.

**G. CONNECTION**

autoscheduler/model.py:load_model (314–362); tests/test_faculty_dashboard.py; dashboard/web/src/Simulation.jsx:PolicyPlayback; artifact inventory below.

<a id="topic-10"></a>

### [P1] 10. The original classifier: synthetic labels, fitting and choose-once scheduling

**A. WHAT TO SAY (15–30 seconds)**

> The original experiment generated synthetic workloads and ran each static policy to assign the lowest-score label. A decision-tree classifier learned to choose one scheduler from whole-workload statistics. That is a different experiment from v5's repeated observed-state cost decisions.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/dataset.py` → `build_dataset; train_model; run_adaptive`.

**Chunk 1.** Focus on source lines **24, 25, 31, 32, 33**.

Source: [autoscheduler/dataset.py](../autoscheduler/dataset.py), lines **21–36**.

```python
    rows = []
    for profile_index, profile in enumerate(PROFILES):
        for sample_index in range(samples_per_profile):
            workload_seed = seed * 10_000_000 + profile_index * 1_000_000 + sample_index
            workload = generate_workload(profile, workload_seed)
            label, scores = oracle_label(
                compare_algorithms(
                    workload.processes,
                    priority_rr_config,
                    algorithms=SELECTOR_ALGORITHMS,
                )
            )
            row = extract_features(workload.processes)
            row.update({"profile": profile, "seed": workload_seed, "label": label})
            row.update({f"score_{name.lower().replace(' ', '_')}": score for name, score in scores.items()})
            rows.append(row)
```

**Chunk 2.** Focus on source lines **181, 182, 186, 187, 188**.

Source: [autoscheduler/model.py](../autoscheduler/model.py), lines **179–188**.

```python
    def fit_candidate(matrix, labeled_rows, settings):
        depth, leaf, weight = settings
        if model_kind == "policy_cost":
            from autoscheduler.model_bakeoff import _new_model
            regressor = _new_model("Decision Tree", {"max_depth": depth, "min_samples_leaf": leaf}, random_state)
            regressor.fit(matrix, [[row[_score_column(policy)] for policy in policies] for row in labeled_rows])
            return PolicyCostModel(regressor, policies)
        return DecisionTreeClassifier(
            max_depth=depth, min_samples_leaf=leaf, class_weight=weight, random_state=random_state,
        ).fit(matrix, [row["label"] for row in labeled_rows])
```

**Chunk 3.** Focus on source lines **31, 32, 45, 46, 47**.

Source: [autoscheduler/features.py](../autoscheduler/features.py), lines **30–48**.

```python
    arrivals = [process.arrival_time for process in processes]
    cpu_totals = [process.burst_time for process in processes]
    priorities = [process.priority for process in processes]
    short_jobs = [mean(process.cpu_bursts) <= 4 for process in processes]
    total_cpu = sum(cpu_totals)
    total_io = sum(process.total_io_time for process in processes)
    arrival_span = max(arrivals) - min(arrivals) + 1

    return {
        "process_count": float(len(processes)),
        "arrival_rate": len(processes) / arrival_span,
        "burst_mean": mean(cpu_totals),
        "burst_variance": pvariance(cpu_totals),
        "short_job_ratio": sum(short_jobs) / len(processes),
        "priority_mean": mean(priorities),
        "priority_variance": pvariance(priorities),
        "io_frequency": mean(len(process.io_bursts) for process in processes),
        "io_cpu_ratio": total_io / total_cpu,
    }
```

**C. EXPLAIN THE CODE**

**Chunk 1:** Each profile/sample gets a deterministic seed. compare_algorithms runs the static registry; oracle_label supplies a winner and all scores. Feature and target columns become one row per workload.

**Chunk 2:** The same training entry point has separate branches: policy_cost fits a multi-output regressor to score columns, while classifier fits DecisionTreeClassifier to label strings. It does not compose them into a hybrid.

**Chunk 3:** Nine offline inputs summarize the complete declared workload, including CPU totals and I/O. This is valid for synthetic workload selection but not an observed-only kernel inference contract.

autoscheduler/adaptive.py:run_adaptive (30–43) extracts once, calls select_scheduler, then runs the selected static algorithm to completion. CLI _train (188–205) first tunes Priority RR, builds/saves the dataset, fits, then saves a report. train_model defaults to 70/15/15 splitting and validation regret selection, with depth 3/5/8/unlimited and leaf sizes 10/5/1; non-grouped splitting stratifies when class counts permit. The general path refits train+validation after a train-only internal test; v5 explicitly sets refit=False. The saved six-policy metadata records 2,500 workloads, validation accuracy 76.8%, test accuracy 73.0667%, depth 3, leaf 10. These historical percentages are traceable to results/six_policy/model.json and artifacts/demo_tree.json, not current v5 accuracy. The six-policy artifact loads; its fitted classes are FCFS, RR, SJF and SRTF, since not every eligible policy received training labels.

**D. WHY WE USED THIS APPROACH**

Direct classification is simple and predicts an action in one pass; cost regression preserves the magnitude of action differences and enables a gain margin. Classification can count a harmless tied-label disagreement as wrong while overlooking costly rare errors. The source explicitly prefers validation regret, rather than just accuracy. Describing why the original authors began with classification remains interpretation unless independently documented.

**E. FACULTY QUESTIONS**

- **Why research classification if v5 uses regression?** It establishes the earlier choose-once selector and a separate dynamic-family comparison; the later controller needs numerical action costs.
- **Was 76% scheduling improvement achieved?** No. 76.8% is a historical validation label accuracy; it says nothing directly about runtime improvement.
- **Is the historical classifier unavailable?** A compatible six-policy binary exists locally. The dashboard still displays metadata only and hardcodes an unavailable message; matching provenance must not be assumed solely from equal metrics.

**F. DON'T SAY THIS**

Do not describe whole-workload feature knowledge as realistic online observation. Do not carry historical accuracy percentages into Azure or regression claims.

**G. CONNECTION**

autoscheduler/adaptive.py:select_scheduler (23–27); autoscheduler/model.py:_split_indexes,train_model; results/six_policy/model.json; dashboard/adapter.py:60–61.

<a id="topic-11"></a>

### [P1] 11. Dynamic training labels, group splits and offline learning

**A. WHAT TO SAY (15–30 seconds)**

> Offline training clones an execution state and tries each allowed action for the feasible horizon, followed by MLFQ to completion. The resulting score differences become regression targets. Complete trace seeds stay in one split, and an extra pilot rollout adds states only to training.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/dynamic.py` → `_counterfactual_label; dynamic_training.build_training_data`.

**Chunk 1.** Focus on source lines **567, 568, 575, 576, 577**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **565–578**.

```python
    config = config or DynamicRouterConfig(epoch_ticks=epoch_ticks)
    results = {}
    expiry = state.current_time + config.effective_label_horizon
    boundary = ((expiry + config.epoch_ticks - 1) // config.epoch_ticks) * config.epoch_ticks
    continuation = config.label_continuation
    features = extract_dynamic_features(state, active_policy)
    for action in dict.fromkeys((*policies, continuation)):
        policy = _resolve_action(action, active_policy)
        policy, _ = _tail_action(features, active_policy, policy, config)
        if _protected(features, active_policy, policy, config):
            policy = active_policy
        trial = copy.deepcopy(state)
        _switch_policy(trial, active_policy, policy)
        while (trial.pending or trial.ready or trial.blocked) and trial.current_time < boundary:
```

**Chunk 2.** Focus on source lines **590, 591, 601, 602, 603**.

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **589–604**.

```python
            _dispatch(trial, policy, priority_rr_config)
        _switch_policy(trial, policy, continuation)
        _run_to_completion(trial, continuation, priority_rr_config)
        results[action] = _simulation(trial, action)
    if references is None:
        # Direct callers still get one fixed reference scale, never per-action
        # normalization. Dataset generation supplies full-workload static bounds.
        references = results
    baseline = score_result_against_reference(results[continuation], references)
    scores = {policy: score_result_against_reference(results[policy], references) - baseline for policy in policies}
    label = min(policies, key=lambda policy: (scores[policy], policies.index(policy)))
    if "No Switch" in scores and scores["No Switch"] <= scores[label] + 1e-12:
        label = "No Switch"
    elif active_policy in scores and scores[active_policy] <= scores[label] + 1e-12:
        label = active_policy
    return label, scores
```

**Chunk 3.** Focus on source lines **41, 42, 49, 50, 51**.

Source: [autoscheduler/dynamic_training.py](../autoscheduler/dynamic_training.py), lines **38–53**.

```python
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    train_rows = [rows[index] for index in indexes[0]]
    pilot = DecisionTreeClassifier(max_depth=5, min_samples_leaf=10, random_state=seed).fit(
        [[row[name] for name in DYNAMIC_FEATURE_NAMES] for row in train_rows],
        [row["label"] for row in train_rows],
    )
    on_policy = build_dynamic_dataset(
        traces, seed, config, priority_rr_config, behavior_model=pilot,
        trace_indexes=[trace_seed - seed * 1_000_000 for trace_seed in groups["train"]],
        development=development,
    )
    assert {row["seed"] for row in on_policy} <= set(groups["train"])
    rows += on_policy
    return rows, {**manifest, "mixed_rows": len(rows) - len(on_policy), "on_policy_rows": len(on_policy)}
```

**C. EXPLAIN THE CODE**

**Chunk 1:** The labeler sets an expiry and review boundary, applies the same tail/first-service constraints, then deep-copies state for each action. This offline trial knows the synthetic continuation; those future values are target-generation information.

**Chunk 2:** After the action interval it resumes the continuation policy to completion and scores every outcome on fixed reference bounds. It subtracts continuation cost and prefers No Switch, then active, when optimal scores tie.

**Chunk 3:** The grouped manifest is written before fitting. A train-only pilot classifier generates extra on-policy occupancy from training trace seeds only. This pilot is an offline data-generation device, not a classifier preceding v5 regression at runtime.

build_dynamic_dataset (662–711) obtains mixed static/exploration states, extracts observed features, and records seed, epoch, label and score_<policy> targets. _training_states collects only states with no remaining dwell. For v5, the experiment uses the six-family v4 development generator, 144 training traces (seed 9701), 84 external development-validation workloads (9702), and 240 fresh audit workloads (9703). The saved training table has 7,282 rows; internal grouped counts are 100/22/22 traces, including train-only occupancy augmentation. _split_indexes uses GroupShuffleSplit for 70/30 then half of holdout; row percentages need not be exactly 70/15/15. The separately generated 84 validation workloads select realized scheduling behavior; they are not the same thing as the internal 22 validation trace groups.

**D. WHY WE USED THIS APPROACH**

Whole-trace groups prevent nearby states from the same workload appearing in both fitting and assessment. Trial actions with the runtime horizon align labels with feasible control rather than unlimited static policies. Alternatives include random row splits (leakage risk), static full-run labels (wrong action semantics), or online reinforcement learning (different implementation and risk). The code explicitly labels this synthetic development only; the rest is a reasonable technical justification.

**E. FACULTY QUESTIONS**

- **Does future information leak into features?** Label generation uses complete simulation futures offline; extract_dynamic_features supplies only observed inputs. These roles must be separated.
- **Is the model learning as the simulation runs?** No fit call occurs in run_dynamic; it performs inference on a previously fitted tree.
- **Is the pilot classifier the hybrid architecture?** No. It samples training states offline and is not part of the active v5 inference chain.

**F. DON'T SAY THIS**

Do not say labels are Linux measurements, every cost is a whole-run static-policy score, or trace-level split percentages imply equal row proportions.

**G. CONNECTION**

autoscheduler/model.py:76–101,134–155,179–188; autoscheduler/dynamic_v5_experiment.py:136–214; artifacts/dynamic_v5_20261019/split.json.

<a id="topic-12"></a>

### [P1] 12. Model selection, comparative evidence and safety gates

**A. WHAT TO SAY (15–30 seconds)**

> We judge a candidate by the schedule it actually produces and by safety gates, not just label accuracy. The v5 cost tree was selected in development, but its later audit did not pass every requirement. Tuned MLFQ remains the recommendation.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/dynamic_training.py` → `validation_metrics; dynamic_v5_experiment.run`.

**Chunk 1.** Focus on source lines **107, 108, 115, 116, 117**.

Source: [autoscheduler/dynamic_training.py](../autoscheduler/dynamic_training.py), lines **105–120**.

```python
    intervals = {name: (paired_bootstrap_ci(values) if min(values) != max(values) else
                 {"mean": values[0], "ci_low": values[0], "ci_high": values[0]}) for name, values in differences.items()}
    gates = {"score": intervals["score"]["ci_high"] < 0,
             "p95_response": intervals["p95_response"]["ci_high"] <= 0,
             "starvation": intervals["starvation"]["mean"] <= 0,
             "latency": max(latencies) < 10,
             "original_rr_score": intervals["rr_score"]["ci_high"] <= 0,
             "original_rr_p95": intervals["rr_p95_response"]["ci_high"] < 0}
    return {
        "validation_schedule_score": mean(scores),
        "validation_schedule_p95_response": mean(responses),
        "validation_schedule_starvation": mean(starvations),
        "validation_schedule_eligible": all(gates.values()),
        "validation_schedule_gates": gates, "validation_schedule_intervals": intervals,
        "validation_schedule_max_workload_p99_ms": max(latencies),
    }
```

**Chunk 2.** Focus on source lines **187, 188, 196, 197, 198**.

Source: [autoscheduler/dynamic_v5_experiment.py](../autoscheduler/dynamic_v5_experiment.py), lines **183–198**.

```python
    for family in ("classifier", "policy_cost"):
        print(f"Comparing constrained {family} trees", flush=True)
        path = artifacts / family / "model.joblib"
        settings = [(d, 10, w) for d in (3, 5, 8) for w in ((None, "balanced") if family == "classifier" else (None,))]
        report = train_model(rows, path, train_seed, feature_names=DYNAMIC_FEATURE_NAMES,
            metadata={"dynamic_config": config.__dict__, "static_baseline": static_validation["static_baseline"],
                      "primary_baseline": primary, "response_tail_protocol": "observed_quiet_gate_and_minimum_dwell_excursion"},
            model_kind=family, candidate_settings=settings, refit=False,
            scheduler_validation=lambda model: validation_metrics(model, cases, config, baseline_results=baselines))
        models[family] = load_model(path, DYNAMIC_FEATURE_NAMES, expected_dynamic_config=config)
        validation[family] = {k: v for k, v in report.items() if k.startswith("validation_schedule_")}
        _write(output / f"{family}_training.json", report)
    selected = select_eligible_family(validation)
    _write(output / "frozen_selection.json", {"selected": selected, "fallback": primary,
        "diagnostic_models": [name for name in models if not validation[name]["validation_schedule_eligible"]],
        "validation": validation})
```

**Chunk 3.** Focus on source lines **33, 34, 40, 41, 42**.

Source: [autoscheduler/model_bakeoff.py](../autoscheduler/model_bakeoff.py), lines **25–43**.

```python
def _new_model(family: str, settings: dict[str, Any], random_state: int):
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeRegressor

    if family == "Dummy":
        return DummyRegressor(**settings)
    if family == "Ridge":
        return make_pipeline(StandardScaler(), Ridge(**settings))
    if family == "Decision Tree":
        return DecisionTreeRegressor(**settings, random_state=random_state)
    if family == "Random Forest":
        return RandomForestRegressor(**settings, random_state=random_state, n_jobs=1)
    if family == "Histogram Gradient Boosting":
        return HistGradientBoostingRegressor(**settings, random_state=random_state)
    raise ValueError(f"unknown model family: {family}")
```

**C. EXPLAIN THE CODE**

**Chunk 1:** Paired differences get confidence intervals. Score must improve strictly; P95 and mean starvation must not regress; maximum workload controller P99 must stay below 10 ms; additional RR comparisons also apply. Eligibility requires every gate.

**Chunk 2:** Classifier and policy_cost families are trained separately with a realized-schedule validation callback and refit=False. select_eligible_family chooses only eligible families; failed candidates remain diagnostic artifacts.

**Chunk 3:** The separate regression comparison factory supports Dummy, scaled Ridge, Decision Tree, Random Forest and Histogram Gradient Boosting. These are alternative experiments, not simultaneous v5 runtime components.

The v5 protocol tries classifier depths 3/5/8 with leaf 10 and balanced/unweighted classes, and cost-tree depths 3/5/8 with leaf 10. Its research_summary.json says development_selected=policy_cost but accepted_after_audit=null and recommendation=Tuned MLFQ. Internal cost-action agreement is 50/262=19.08397%, while saved tie-aware agreement is 83.2061%; neither is a scheduler improvement. The dynamic classifier's internal test accuracy is 70.9924%, also a different model. Paired bootstrap uses 10,000 resamples with seed 2027 (experiments.py:39–55), sampled at workload/group unit rather than individual decision rows.

**D. WHY WE USED THIS APPROACH**

Scheduling validation catches cases where accurate labels or small MAE fail to improve trajectories. A single accuracy ranking is cheaper but ignores severity and safety; a multi-objective gate can reject an otherwise good mean score. That selection intent is explicit in code/docstrings. Small trees are interpretable and cheap, but the current repository does not prove global superiority over alternative models.

**E. FACULTY QUESTIONS**

- **Did a Decision Tree beat every other method?** No. In the saved decision-tree-demo replay comparison, Ridge was selected; Decision Tree and Random Forest tie its zero locked cost, and only two locked traces exist versus 60 required.
- **What is the difference between MAE and policy regret?** MAE measures numerical prediction error; policy regret measures the cost of the selected action versus a reference best action. Neither alone proves full-trajectory improvement.
- **Did v6 solve the problem?** It remains unpromoted; saved fixed-baseline sensitivity reports a response regression. Read each cohort separately.

**F. DON'T SAY THIS**

Do not cite the folder name decision-tree-demo as proof a tree won. Do not call a failed or insufficient-data gate deployment approval. The later Azure prediction comparison selection.json has chosen=null.

**G. CONNECTION**

results/dynamic_v5_20261019/research_summary.json; results/real_desktop_ml/decision-tree-demo/summary.json; results/dynamic_v5_azure_prediction_comparison_20261020/selection.json; configs/research_status.json.

<a id="topic-13"></a>

### [P1] 13. Azure reconstruction, bounded sampling and time-unit distortion

**A. WHAT TO SAY (15–30 seconds)**

> Azure provides observed invocation counts and daily function-duration summaries, not CPU scheduling traces. We reconstruct within-minute arrivals and use the daily wall-clock mean as a CPU-demand proxy. High-load hours are sampled into bounded workloads, with provenance and sampling fractions retained.

**B. WHAT CODE TO SHOW**

Open `AzureWorkloads/scripts/convert_workloads.py` → `reconstruct; refine_workloads.sample_sources`.

**Chunk 1.** Focus on source lines **31, 32, 37, 43, 44**.

Source: [AzureWorkloads/scripts/convert_workloads.py](../AzureWorkloads/scripts/convert_workloads.py), lines **30–44**.

```python
            minute = source['start_minute'] + index + 1  # original 1..1440 column name
            identity = ':'.join(map(str, [seed,source['day'],*(source[k] for k in KEY),minute]))
            rng = random.Random(int.from_bytes(hashlib.sha256(identity.encode()).digest(), 'big'))
            if source.get('sampling_method') == 'minute_stratified_without_replacement':
                ordinals = source['sampled_ordinals'][index]
                if len(ordinals)!=len(set(ordinals)) or any(i<1 or i>count for i in ordinals):
                    raise ValueError('Invalid sampled invocation ordinal')
                pairs = [(ordinal,int.from_bytes(hashlib.sha256(f'{identity}:{ordinal}'.encode()).digest(),'big')%60000) for ordinal in ordinals]
            elif source.get('sampling_method') == 'contiguous_uniform_snapshot':
                if index != source['snapshot']['minute_index']:
                    continue
                from common import snapshot_offsets
                pairs = snapshot_offsets(source,seed)
            else:
                pairs = list(enumerate(sorted(rng.randrange(60000) for _ in range(int(count))),1))
```

**Chunk 2.** Focus on source lines **46, 47, 49, 50, 55**.

Source: [AzureWorkloads/scripts/convert_workloads.py](../AzureWorkloads/scripts/convert_workloads.py), lines **45–55**.

```python
            for ordinal, offset in pairs:
                absolute = (source['day']-1)*86400000 + (minute-1)*60000 + offset
                arrival = index*60000+offset if origin_ms is None else absolute-origin_ms
                jobs.append(dict(workload_id=workload_id,
                    pid=f'{workload_id}:r{source["source_row"]}:m{minute}:i{ordinal}',
                    arrival_time=arrival, burst_time=math.ceil(average), priority=0,
                    absolute_arrival_time=absolute,
                    day=source['day'], source_minute=minute, invocation_ordinal=ordinal,
                    source_row=source['source_row'], duration_row=source['duration_row'],
                    **{key: source[key] for key in KEY}, Trigger=source['Trigger'], Average=average,
                    duration_method='ceil_daily_wall_clock_mean_ms', time_unit='ms'))
```

**Chunk 3.** Focus on source lines **47, 48, 52, 53, 54**.

Source: [AzureWorkloads/scripts/refine_workloads.py](../AzureWorkloads/scripts/refine_workloads.py), lines **42–55**.

```python
def sample_sources(sources, budget, seed):
    result=copy.deepcopy(sources)
    if sum(sum(s['counts']) for s in sources)<=budget:
        return result
    # Stable identity ordering makes quotas invariant to caller source ordering.
    result.sort(key=lambda s:(s['day'],*(s[k] for k in KEY)))
    allocations=apportion(np.array([s['counts'] for s in result]),budget,seed)
    for source,quotas in zip(result,allocations):
        rng=random.Random(source_seed(source,seed,'ordinal_sample'))
        source['sampling_method']='minute_stratified_without_replacement'
        source['sampled_counts']=list(map(int,quotas))
        source['sampled_ordinals']=[sorted(rng.sample(range(1,int(n)+1),int(k))) for n,k in zip(source['counts'],quotas)]
        source['within_minute_inclusion_fractions']=[int(k)/int(n) if n else None for n,k in zip(source['counts'],quotas)]
    return result
```

**C. EXPLAIN THE CODE**

**Chunk 1:** A stable seed plus day/function/minute identity controls arrival reconstruction. Stratified samples keep chosen invocation ordinals and hash them into the minute. Unsampled controls generate reproducible uniform millisecond offsets. Snapshot reconstruction takes a separate branch.

**Chunk 2:** Absolute/source-relative timestamps are calculated in milliseconds; burst_time=ceil(Average), priority=0. Source identifiers and the declared conversion method remain attached to job records.

**Chunk 3:** Sources are copied and stably ordered; apportion distributes bounded quotas over source-minute cells. Sampling is without replacement within cells, and each cell records its inclusion fraction.

The existing package has 510 workloads/520,408 jobs, each at most 2,000 processes. Old selection had 286/72,408; its 2,000-per-hour cap excluded source hours containing 94.37136% of recorded invocations. Refined cohorts retain original controls and add stratified high-load hours, mixed functions and contiguous reconstructed-rank peak snapshots. Full-hour thinning preserves minute-scale shape approximately but lowers arrival intensity; short snapshots preserve local reconstructed rate under the uniform-arrival assumption, not an entire observed hour. Source overlap means jobs are not all distinct across workloads. Descriptive statistics report only 0.00416145% of recorded invocation occurrences actually sampled after refinement; zero cap-only ineligibility does not mean complete coverage.

**D. WHY WE USED THIS APPROACH**

Bounded workloads make controlled simulator comparison feasible. Entire-hour exclusion caused volume bias; proportional quotas plus local snapshots expose high-load contexts while preserving controls. Alternatives are full replay (expensive), uniform thinning (loses local rate), or time compression (changes scheduling semantics). These reconstruction choices are explicit in source and metadata. Their fidelity is limited by the source's minute aggregation and use of a mean duration.

**E. FACULTY QUESTIONS**

- **Is one tick one millisecond here?** Yes, for this Azure mapping. Generic synthetic ticks are not automatically physical milliseconds.
- **How much rounding error does ceil add?** For positive μ, 0≤ceil(μ)−μ<1 ms. The saved report found all 651,505 positive published means integral, so added pipeline error is zero; upstream submillisecond quantization is unknown.
- **What about published zero durations?** 11,417 published zero means remain in duration observations but cannot supply positive Process bursts. The pipeline does not silently floor them to one.

**F. DON'T SAY THIS**

Do not call wall-clock duration a measured CPU burst, reconstructed timestamps observed event times, or 510 workloads a representative random population sample. Hypothetical 0.1→1 ms adds 900%; current integer means do not prove absence of upstream distortion.

**G. CONNECTION**

AzureWorkloads/scripts/refine_workloads.py:apportion (17–39), snapshot_source (58–75); AzureWorkloads/reports/descriptive_statistics.json and workload_statistics.md; metadata.json; autoscheduler/azure_generalization.py:load.

<a id="topic-14"></a>

### [P1] 14. External Azure results: inspect the cohort, failures and tradeoffs

**A. WHAT TO SAY (15–30 seconds)**

> The completed Azure cohort shows a tradeoff. Original v5 reduces average waiting and turnaround, but worsens first response, P95 response and the weighted score against tuned MLFQ. Several selected workloads timed out, so these means describe only the common completed subset.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/azure_generalization_report.py` → `summarize; azure_generalization_evaluation.evaluate`.

**Chunk 1.** Focus on source lines **48, 49, 55, 56, 57**.

Source: [autoscheduler/azure_generalization_report.py](../autoscheduler/azure_generalization_report.py), lines **44–58**.

```python
    policies = list(dict.fromkeys(r['policy'] for r in rows))
    by_id = defaultdict(dict)
    for row in rows:
        by_id[row['workload_id']][row['policy']] = row
    common = [wid for wid, values in by_id.items()
              if len(values) == len(policies) and all(v['status'] == 'COMPLETE' for v in values.values())]

    def averages(subset):
        return {metric: mean([r[metric] for r in subset if r.get(metric) is not None])
                if any(r.get(metric) is not None for r in subset) else None for metric in METRICS}

    policy_summary = {p: {'completed': sum(r['status'] == 'COMPLETE' for r in rows if r['policy'] == p),
                          'timeouts': sum(r['status'] == 'TIMEOUT' for r in rows if r['policy'] == p),
                          'common_complete_means': averages([by_id[wid][p] for wid in common])}
                      for p in policies}
```

**Chunk 2.** Focus on source lines **131, 132, 147, 148, 149**.

Source: [autoscheduler/azure_generalization_evaluation.py](../autoscheduler/azure_generalization_evaluation.py), lines **130–149**.

```python
                dispatch=[];start=time.monotonic();router=None
                signal.alarm(20)
                try:
                    if name=='Dynamic v5':
                        model.predict=action_predict;model.regressor.predict=cost_predict
                        router=run_dynamic(jobs,model,config);result=router.simulation
                    else:
                        if name=='Tuned MLFQ':fn,kwargs=mlfq,manifest['tuned_mlfq']
                        else:fn,kwargs=DEPLOYABLE_ALGORITHMS[name]
                        timing={'decision_times_ns':dispatch} if 'decision_times_ns' in inspect.signature(fn).parameters else {}
                        result=run_simulation(name,fn,jobs,**kwargs,**timing)
                    signal.alarm(0)
                    results[name]=result;fair=aggregate_fairness(result.process_metrics)
                    row.update(status='COMPLETE',avg_waiting_ms=result.avg_waiting_time,avg_response_ms=result.avg_response_time,
                        p95_response_ms=_percentile([p.response_time for p in result.process_metrics],.95),avg_turnaround_ms=result.avg_turnaround_time,
                        throughput_jobs_per_ms=result.throughput,utilization_fraction=result.cpu_utilization,starvation=fair['starvation_count'],
                        context_switches=result.context_switches,context_switch_cost_ms=result.context_switch_time,makespan_ms=result.makespan,
                        accepted_switches=sum(d.accepted for d in router.decisions) if router else 0,
                        decision_p99_ms=router.transition_p99_ms if router else (_percentile(dispatch,.99)/1e6 if dispatch else None),
                        latency_scope='instrumented routing including features/model/guards' if router else ('static ready selection only' if dispatch else 'not instrumented'))
```

**C. EXPLAIN THE CODE**

**Chunk 1:** Rows are grouped by workload. common includes only workloads with all policies complete; policy means use that same subset. The saved report corrects unavailable static timing measurements to null earlier in summarize.

**Chunk 2:** The harness enforces a 20-second per-policy limit, runs unchanged v5 or static policies and records outcomes. Routing P99 includes feature extraction/model/guards; static timings, where supported, cover ready selection only.

The saved baseline has 17 selected workloads/9,413 processes; 12 workloads/3,135 processes complete all seven policies, with 8 policy timeouts over 119 attempts. Recomputing means from baseline_rows.json during this inspection reproduced v5 score 0.1320428718 versus tuned MLFQ 0.0760815724; average waiting 16,304.7827 versus 32,262.4934 ms; average first response 991.3553 versus 0.301921 ms; mean workload P95 2,197.9083 versus 2.9125 ms; turnaround 20,058.3127 versus 36,016.0234 ms. Waiting is about 49.46% lower, but that is not overall improvement. The saved weighted-score paired-difference CI is [−0.0454472, 0.1993452], failing strict improvement; P95 difference CI [257.8686, 5092.2399] shows worse tails on completed pairs. Completion coverage and final-holdout improvement gates are false.

**D. WHY WE USED THIS APPROACH**

Matched workloads and fixed five-policy bounds make the comparison interpretable; retaining timeouts avoids hiding difficult cases. Alternative completion-only reporting without failures is biased, while assigning arbitrary performance penalties to timeouts would introduce a different metric. These choices are documented in the harness. Distribution shift and non-preemptive Priority excursions plausibly explain poor response: long proxy bursts delay future dispatch/review opportunities. This is supported by dispatch behavior and diagnostics, but it is not a universal causal proof from aggregate means.

**E. FACULTY QUESTIONS**

- **Does ML contribute if results match MLFQ?** Model calls and accepted transitions prove execution influence, not performance benefit. Low contention can make different policies produce the same schedule.
- **How many original v5 transitions were recorded?** The saved completed-run evidence records 25,132 reviews, 5,932 accepted transitions and 19,200 nonaccepted switching reviews. Accepted counts include mandatory MLFQ returns.
- **Did Azure retraining beat MLFQ?** The separate six-workload development result matched tuned MLFQ, with two accepted switches and no strict score improvement. It is not the 12-workload cohort.

**F. DON'T SAY THIS**

Do not present the 12 complete workloads as all 510, interpret timeouts as scheduler completion times, or combine independent cohorts into one percentage. The 73-group genuinely untouched reserve is not an evaluated success.

**G. CONNECTION**

results/dynamic_azure_generalization/{baseline_rows.json,baseline_decisions.json,summary.json,untouched_holdout_manifest.json}; results/real_source_dynamic_review_20261020/dashboard.json; results/dynamic_v5_azure_retrained_20261020/results.json.

<a id="topic-15"></a>

### [P1] 15. Tests as executable claims and limits of this inspection

**A. WHAT TO SAY (15–30 seconds)**

> We have tests for selection order, CPU/I/O accounting, MLFQ feedback, feature leakage and switching guards. A useful test changes hidden future information and checks that the model features do not change. Tests also compare dynamic dispatch with static behavior and verify the demo's accepted transitions.

**B. WHAT CODE TO SHOW**

Open `tests/test_dynamic_contract.py` → `DynamicObservabilityTests.test_features_ignore_declared_work_and_unobserved_future`.

**Chunk 1.** Focus on source lines **38, 39, 48, 49, 50**.

Source: [tests/test_dynamic_contract.py](../tests/test_dynamic_contract.py), lines **29–50**.

```python
    def test_features_ignore_declared_work_and_unobserved_future(self):
        state = _new_state([
            Process("ready", 0, 10, priority=2),
            Process("io", 0, 8, priority=1, cpu_bursts=(2, 6), io_bursts=(8,)),
            Process("future", 100, 5, priority=1),
        ])
        _release(state, 0)
        # Finish a known two-tick burst and observe the subsequent I/O block.
        _dispatch(state, "Priority", ALGORITHMS["Priority RR"][1])
        observed = extract_dynamic_features(state)
        altered = copy.deepcopy(state)
        for ready in altered.ready:
            ready.process.remaining_time = 999
            ready.process.burst_time = 2000
            ready.process.cpu_bursts = (2000,)
        for _, process, _, _ in altered.blocked:
            process.remaining_time = 777
            process.burst_time = 1554
            process.cpu_bursts = (777, 777)
            process.io_bursts = (999,)
        altered.pending = [Process("unseen", 10000, 99999, priority=99)]
        self.assertEqual(extract_dynamic_features(altered), observed)
```

**C. EXPLAIN THE CODE**

**Chunk 1:** The test observes a real partial execution, then changes declared remaining work, CPU/I/O descriptions and pending future arrivals on a copy. Equality of extracted features checks the intended observability boundary. It does not prove a Linux implementation exists.

Open tests/test_schedulers.py for SJF total-burst semantics (15–23), RR arrival-before-requeue (81–94), I/O blocking (133–146), and overhead (117–131). tests/test_mlfq.py checks demotion, high-queue preemption, equal-queue nonpreemption and aging at 20 rather than 19 ticks. tests/test_dynamic_v5.py checks quiet admission, urgent-return/dwell behavior, feature history and training/runtime actionable-state equivalence. tests/test_dynamic_contract.py:114 checks static/dynamic MLFQ agreement and 180 onward checks persistence contracts. tests/test_switching_demo.py checks model identity, events, timeline hash and selected-case comparison. tests/test_azure_runtime_equivalence.py compares preserved and current engines.

**D. WHY WE USED THIS APPROACH**

Small deterministic examples isolate important invariants better than a screenshot or one aggregate benchmark. Property-based randomized tests are an alternative with broader state-space coverage but harder-to-explain failures; a full research rerun is expensive and answers a different question. Test names and assertions demonstrate intended contracts, not a proof of universal correctness.

**E. FACULTY QUESTIONS**

- **Were all tests rerun for this guide?** No. This task was documentation-only. Artifact loading and four tiny in-memory demo runs were checked; no training, heavy evaluation or full test suite was run.
- **Which code proves features exclude future work?** Open the mutation-and-equality test shown here alongside extract_dynamic_features.
- **Can passing tests prove scheduler superiority?** No. They verify implementation behavior; comparative performance needs a well-designed evaluation and completed coverage.

**F. DON'T SAY THIS**

Do not turn the existence of a test into a claimed fresh pass. Some tests fit models or write temporary artifacts, so the full suite was deliberately not invoked here.

**G. CONNECTION**

tests/test_dynamic_v5.py; tests/test_mlfq.py; tests/test_faculty_dashboard.py; tests/test_azure_runtime_equivalence.py; AzureWorkloads/tests/test_refinement.py.

<a id="topic-16"></a>

### [P2] 16. Dashboard simulation requests, playback and dynamic visualization

**A. WHAT TO SAY (15–30 seconds)**

> Changing the preset or scheduler requests a complete backend simulation. Start, pause and speed controls only move through the returned frames. Dynamic policy strips come from accepted backend decisions, while the ready display reconstructs membership rather than the scheduler's internal queue order.

**B. WHAT CODE TO SHOW**

Open `dashboard/web/src/Simulation.jsx` → `Simulation / PolicyPlayback / Gantt`.

**Chunk 1.** Focus on source lines **48–50**.

Source: [dashboard/web/src/Simulation.jsx](../dashboard/web/src/Simulation.jsx), lines **46–50**.

```jsx
export function Simulation({data,workload,setWorkload}) {
  const [algorithm,setAlgorithm]=useState('Round Robin'),[result,setResult]=useState(null),[error,setError]=useState(''),[tick,setTick]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[retry,setRetry]=useState(0);
  useEffect(()=>{ const abort=new AbortController(); setResult(null);setError('');setTick(0);setPlaying(false);api(`/api/simulation?workload=${encodeURIComponent(workload)}&algorithm=${encodeURIComponent(algorithm)}`,abort.signal).then(setResult).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>abort.abort(); },[workload,algorithm,retry]);
  useEffect(()=>{if(!playing||!result)return; if(tick>=result.metrics.makespan){setPlaying(false);return;} const timer=setTimeout(()=>setTick(t=>Math.min(t+1,result.metrics.makespan)),500/speed);return()=>clearTimeout(timer);},[playing,tick,speed,result]);
  const frame=result?.frames[tick],done=result&&tick===result.metrics.makespan;
```

**Chunk 2.** Focus on source lines **213, 214, 221, 222, 223**.

Source: [dashboard/adapter.py](../dashboard/adapter.py), lines **210–229**.

```python
    periods, transitions = [], []
    if router:
        active, start = router.initial_policy, 0
        for index, decision in enumerate(router.decisions):
            if decision.accepted:
                periods.append({"start": start, "end": decision.time, "policy": active})
                transitions.append({"decision_tick": decision.time, "effective_tick": decision.time,
                    "from_policy": active, "to_policy": decision.active, "reason": decision.reason,
                    "predicted_benefit": router.recorded_predictions[index]['predicted_policy_benefits'][decision.active] if demo else None})
                active, start = decision.active, decision.time
        periods.append({"start": start, "end": result.makespan, "policy": active})
        for frame in frames:
            frame["active_policy"] = next((p["policy"] for p in periods
                if p["start"] <= frame["tick"] < p["end"]), active)
    return {"workload": workload, "algorithm": algorithm, "metrics": data,
        "response_comparison": response_comparison,
        "timeline": result.timeline, "processes": [asdict(m) for m in result.process_metrics],
        "frames": frames, "features": extract_features(jobs),
        "policy_timeline": periods, "policy_transitions": transitions,
        "routing_decisions": [{**asdict(d), **(router.recorded_predictions[i] if demo else {})} for i, d in enumerate(router.decisions)] if router else [],
```

**C. EXPLAIN THE CODE**

**Chunk 1:** React fetches on workload/algorithm/retry changes and cancels obsolete requests. The timer advances tick through already returned frames; playback speed cannot change scheduling.

**Chunk 2:** Only accepted decisions create transition events and policy periods. Each frame gets the policy active during its interval. Regular v5 decisions do not contain a separately recorded raw proposal or full predicted-cost vector.

main.jsx:App (23–41) loads /api/catalog, selects one of four pages and holds workload state. WorkloadSelect uses catalog entries; selecting a dynamic_ preset chooses Dynamic ML (v5). Simulation renders Gantt, ready/blocked membership, per-process frame metrics and final full-run aggregate metrics. _frames (adapter.py:140–185) reconstructs service and I/O intervals from the timeline and declared small workloads, then creates one frame per tick. This frame generation is tick-based playback, not the event-driven scheduler itself. simulation is cached at 24 entries; comparison at 3. Browser communication is ui.jsx:api, a fetch/JSON helper, with Vite /api proxy configuration.

**D. WHY WE USED THIS APPROACH**

Separate playback makes stepping reproducible and avoids coupling simulation decisions to browser timing. A streaming simulator/WebSocket could reveal decisions as they happen, but adds synchronization and would be a different product behavior. Reconstruction avoids exposing engine internals but cannot promise actual queue order or per-level MLFQ contents. These are documented in the adapter's module comments and inferred architectural tradeoffs.

**E. FACULTY QUESTIONS**

- **Does pressing Start begin CPU scheduling?** The request has already computed the full result; Start begins playback.
- **Are the green metrics live at the cursor?** The frame metrics follow the cursor; the full-run performance panel displays final outcomes even before playback finishes.
- **Does the policy strip prove a switch occurred?** Its source is accepted RoutingDecision records, verified against the tiny workload trajectory—not a decorative animation.

**F. DON'T SAY THIS**

Do not call playback live OS scheduling or label reconstructed ready membership as policy queue order. Do not claim original v5 raw proposed costs are shown: they are explicitly Not recorded.

**G. CONNECTION**

dashboard/web/src/main.jsx:App; dashboard/web/src/ui.jsx:api; dashboard/adapter.py:simulation,_frames; dashboard/app.py:get_simulation.

<a id="topic-17"></a>

### [P2] 17. Saved research panels, API routing and UI discrepancies

**A. WHAT TO SAY (15–30 seconds)**

> The research panels mostly display saved result files. Some arrive through the catalog API and some are bundled into the frontend at build time. The simulation page is computed on request, but opening a research panel does not rerun training or the Azure evaluation.

**B. WHAT CODE TO SHOW**

Open `dashboard/adapter.py` → `catalog; Research.Intelligence / RealSourceDynamic`.

**Chunk 1.** Focus on source lines **60, 61, 71, 72, 73**.

Source: [dashboard/adapter.py](../dashboard/adapter.py), lines **54–73**.

```python
def catalog():
    metadata_path = "artifacts/demo_tree.json"
    metadata = read_json(metadata_path) if (ROOT / metadata_path).exists() else None
    return {"workloads": [{"id": key, "name": value["name"], "description": value["description"], "count": len(value["jobs"])}
                          for key, value in WORKLOADS.items()],
        "algorithms": list(ALGORITHMS) + ["MLFQ", "Tuned MLFQ", DYNAMIC_V5_NAME], "score_weights": SCORE_WEIGHTS,
        "offline": {"source": metadata_path, "metadata": metadata, "inference_available": False,
            "message": "Verified saved metadata is available. The matching fitted six-policy binary is not available; live predictions are not fabricated."},
        "research": read_json("configs/research_status.json"),
        "azure_adapted": read_json("results/azure_adapted_20261020/dashboard.json")
            if (ROOT / "results/azure_adapted_20261020/dashboard.json").exists() else None,
        "real_source_dynamic": read_json("results/real_source_dynamic_review_20261020/dashboard.json")
            if (ROOT / "results/real_source_dynamic_review_20261020/dashboard.json").exists() else None,
        "dynamic_v5_evaluation": read_json("results/dynamic_v5_review/analysis.json")
            if (ROOT / "results/dynamic_v5_review/analysis.json").exists() else None,
        "azure_external": {"source": "results/azure_external_pilot/summary.json",
            "summary": read_json("results/azure_external_pilot/summary.json")}
            if (ROOT / "results/azure_external_pilot/summary.json").exists() else None,
        "bakeoff": {"source": "results/real_desktop_ml/decision-tree-demo/summary.json",
                    "summary": read_json("results/real_desktop_ml/decision-tree-demo/summary.json")}}
```

**Chunk 2.** Focus on source lines **30, 31, 41, 42, 43**.

Source: [dashboard/app.py](../dashboard/app.py), lines **25–43**.

```python
@app.get("/api/catalog")
def get_catalog():
    return catalog()


@app.get("/api/simulation")
def get_simulation(workload: str = "short_jobs", algorithm: str = "Round Robin"):
    try:
        return simulation(workload, algorithm)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


@app.get("/api/comparison")
def get_comparison(workload: str = "short_jobs"):
    try:
        return comparison(workload)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
```

**Chunk 3.** Focus on source lines **5–7**.

Source: [dashboard/web/src/RealSourceDynamic.jsx](../dashboard/web/src/RealSourceDynamic.jsx), lines **1–7**.

```jsx
import React from 'react';
import { Badge, Metric, number, Source } from './ui.jsx';
import { compareMetric, metrics as comparedMetrics } from './comparisons.js';
import './review.css';
import retrained from '../../../results/dynamic_v5_azure_retrained_20261020/results.json';
import retrainedProtocol from '../../../results/dynamic_v5_azure_retrained_20261020/protocol.json';
import originalPrediction from '../../../results/original_v5_azure_prediction_20261020/metrics.json';
```

**C. EXPLAIN THE CODE**

**Chunk 1:** catalog reads metadata, research status, original Azure results, old pilot results and a separate replay bake-off summary. inference_available=False and its classifier-unavailable message are constants, not a discovery test of every local model.

**Chunk 2:** GET handlers forward parameters to adapter functions and translate ValueError into 404. Unexpected exceptions use the generic handler at 14–17. No endpoint here trains or captures kernel traces.

**Chunk 3:** Azure-retrained results, their protocol and original-v5 prediction metrics are static module imports. They are baked into the frontend bundle, unlike catalog JSON read by the backend.

Current Intelligence (Research.jsx:40) renders RealSourceDynamic, AzureRetrainedV5, a collapsible original-v5 synthetic table, and Offline classifier metadata. SyntheticDynamic (16–32) exists but is not mounted there. ArchivedRealSourceDynamic likewise exists but is not the exported active panel. Review (Research.jsx:57 onward) presents the old Azure pilot and separate offline-replay model comparison. The original-v5 Azure regression panel reads 0.012602638 MAE, 0.019537636 RMSE, R² −3161.553846 from a saved development partition; these are numerical-fit metrics, not classification accuracy or a new scheduling cohort. Small target variance amplifies negative R², and the saved dummy outperforms it.

**D. WHY WE USED THIS APPROACH**

Saved results protect reproducibility and keep the UI responsive; live recomputation would be expensive and could alter research state. The tradeoff is stale builds and possible stale text. This is a code-grounded interpretation. app.py serves web/dist when present; current source does not establish that an already built bundle matches the locally edited JSX. No build or browser session was run for this guide.

**E. FACULTY QUESTIONS**

- **Are any results fabricated constants?** The workloads and explanatory labels are hand-defined. Research measurements come from named saved JSON; simulation outputs come from the engine. Several explanatory strings are hardcoded and can be stale.
- **Is the classifier binary absent?** The UI says so, but a compatible results/six_policy/model.joblib loads locally and shares headline report metrics. The page still performs no classifier inference.
- **Which UI text should I correct verbally?** SJF's next-burst wording is wrong; the provenance footer says no matched tuned-MLFQ comparison even when the selected-case table above shows one.

**F. DON'T SAY THIS**

Do not claim every imported/exported component is visible. Do not call saved original-v5 Azure fit metrics the synthetic internal-test metrics; analysis.json explicitly leaves the latter MAE/RMSE/R² unrecorded.

**G. CONNECTION**

dashboard/web/src/Research.jsx:40,57; dashboard/web/src/RealSourceDynamic.jsx:50–103; dashboard/app.py:46–48; dashboard/web/src/Simulation.jsx:7,22,30.

<a id="topic-18"></a>

### [P2] 18. CLI, Linux trace tooling and the boundary before kernel claims

**A. WHAT TO SAY (15–30 seconds)**

> The command line exposes demos, experiments and Linux trace preparation. Linux events can be cleaned and converted into observed features and offline replay labels, but that pipeline does not install an ML scheduler in Linux. The real-data track still requires its own grouped validation and acceptance gates.

**B. WHAT CODE TO SHOW**

Open `autoscheduler/real_dataset.py` → `build_development_action_rows; main.main`.

**Chunk 1.** Focus on source lines **139, 140, 142, 143, 144**.

Source: [main.py](../main.py), lines **136–148**.

```python
def main():
    import sys

    if len(sys.argv) == 1:
        demo()
        return
    from autoscheduler.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
```

**Chunk 2.** Focus on source lines **71, 72, 76, 77, 78**.

Source: [autoscheduler/real_features.py](../autoscheduler/real_features.py), lines **69–78**.

```python
    arrivals_seen = wakeups = context_switches = io_returns = 0

    for item in trace["events"]:
        timestamp = item["timestamp_ns"]
        if timestamp >= decision_timestamp_ns:
            break
        pid, event_type, cpu = item["pid"], item["type"], item.get("cpu")
        if item.get("priority") is not None:
            priorities[pid] = item["priority"]
        in_window = timestamp >= window_start
```

**Chunk 3.** Focus on source lines **46, 47, 60, 61, 62**.

Source: [autoscheduler/real_dataset.py](../autoscheduler/real_dataset.py), lines **46–63**.

```python
        results = _results(replay.processes)
        scores = score_results(results)
        fairness = {action: aggregate_fairness(result.process_metrics) for action, result in results.items()}
        snapshots = extract_feature_rows(
            [trace], control["initial_observation_ms"], control["feature_window_ms"],
            control["decision_interval_ms"],
        )
        accepted += 1
        for snapshot in snapshots:
            for action, cost in scores.items():
                rows.append({
                    **snapshot,
                    "action": action,
                    "policy_cost": cost,
                    **fairness[action],
                    "source_result": f"{metadata['trace_id']}:{action}",
                    "label_provenance": provenance,
                })
```

**C. EXPLAIN THE CODE**

**Chunk 1:** With no arguments, main runs the older hardcoded scheduling demo. With arguments it delegates to autoscheduler.cli. The web dashboard is a separate entry point.

**Chunk 2:** Feature extraction stops before the decision timestamp and tracks events inside its history window. This real-trace schema is distinct from v5's 19 synthetic dynamic inputs.

**Chunk 3:** The replay is simulated under static actions once; each snapshot receives those action scores and fairness values. They are whole-replay development labels repeated across snapshots, not measured per-state counterfactual kernel costs.

autoscheduler/cli.py:main (614–616) parses and calls the registered handler. _demo (442–445) calls the terminal menu; _train, _dynamic_train and _model_bakeoff are writing/training commands, not read-only presentation helpers. real-trace-clean anonymizes/validates input before sharing; real-features alone supplies no policy-cost labels. real_split.py:37–58 shuffles complete metadata groups; configs/real_desktop_ml.json freezes application/scenario/capture_session grouping and gates. real_dataset.py sets pilot_offline_replay_development_only or synthetic_development_only provenance. The separate RR benefit model is a single oracle-oriented switching experiment, not the current v5 demonstration. No production kernel controller is invoked by the dashboard or simulator.

**D. WHY WE USED THIS APPROACH**

Offline replay makes policy experiments reproducible without modifying the OS, but omits multicore/cache/affinity and causal interactions of a real scheduler. Direct kernel integration is a valid future alternative with much stronger instrumentation and validation requirements. The research boundary is explicitly documented in AGENTS.md and OFFLINE_REPLAY_CONTRACT.md; no implementation claim should exceed it.

**E. FACULTY QUESTIONS**

- **Where was training performed?** Offline Python/sklearn entry points write saved artifacts; the exact physical machine for every historical fit is not established by source inspection. No fitting occurs in the demo.
- **Does real-features train a model?** No. It extracts observed inputs; labels, grouped split and fitting are separate steps.
- **Is sched_ext implemented?** The current path does not deploy a sched_ext controller; project instructions defer that work until locked real-trace gates pass.

**F. DON'T SAY THIS**

Do not call simulator milliseconds measured Linux response, synthetic trace-shaped fixtures observed Linux captures, or replay-only labels validated kernel performance.

**G. CONNECTION**

autoscheduler/cli.py:48–178,442–616; autoscheduler/demo.py:run_demo; autoscheduler/real_replay.py:build_replay_workload; configs/real_desktop_ml.json; tools/run_firefox_probe.sh.

## Model artifacts and loadability audit

This was a read-only load check with the existing `.venv`, with Python bytecode writing disabled. No model was fitted or saved. “Deserializes” and “passes current contract” are different checks. All 17 discovered `.joblib` files under `artifacts/` and `results/` deserialized without warnings in this environment.

| Exact artifact path | What is inside | Current use / compatibility |
|---|---|---|
| `artifacts/dynamic_v5_20261019/policy_cost/model.joblib` | PolicyCostModel + depth-3 DecisionTreeRegressor, 19 inputs, 6 outputs | Passes current loader and dashboard hash check; active original-v5 demo. |
| `artifacts/dynamic_v5_20261019/classifier/model.joblib` | DecisionTreeClassifier, 19 inputs | Passes current dynamic loader; separate comparison family, not active v5 demo. |
| `results/six_policy/model.joblib` | DecisionTreeClassifier, 9 inputs, depth 3 | Passes current static loader; not wired to live dashboard classifier inference. |
| `results/five_policy_consistent/model.joblib` | Historical DecisionTreeClassifier, 9 inputs | Deserializes; rejected by current policy-set contract. |
| `results/six_policy/dynamic_model.joblib` | Historical DecisionTreeClassifier, 8 inputs | Deserializes; rejected by current dynamic feature schema. |
| `results/rr_srtf_benefit/model.joblib` | DecisionTreeRegressor, 17 inputs | Its own `autoscheduler/benefit.py:load_benefit_model` (305–311) passes; not a v5 model. |
| `artifacts/dynamic_v2_20261019/candidates/classifier/model.joblib` | Historical classifier, 14 inputs | Rejected by current dynamic schema. |
| `artifacts/dynamic_v2_20261019/candidates/policy_cost/model.joblib` | Historical cost tree, 14 inputs, 5 outputs | Rejected by current dynamic schema. |
| `artifacts/dynamic_v3_20261019/candidates/classifier/model.joblib` | Historical classifier, 14 inputs | Rejected by current dynamic schema. |
| `artifacts/dynamic_v3_20261019/candidates/policy_cost/model.joblib` | Historical cost tree, 14 inputs, 5 outputs | Rejected by current dynamic schema. |
| `artifacts/dynamic_v4_20261019/classifier/model.joblib` | Historical classifier, 18 inputs | Rejected by current dynamic schema. |
| `artifacts/dynamic_v4_20261019/policy_cost/model.joblib` | Historical cost tree, 18 inputs, 6 outputs | Rejected by current dynamic schema. |
| `artifacts/dynamic_v6_20261019/classifier/model.joblib` | Classifier, 19 inputs | Passes with its own saved config; not active original-v5 demo. |
| `artifacts/dynamic_v6_20261019/policy_cost/model.joblib` | Depth-5 cost regressor, 19 inputs | Passes with its own config; not promoted or substituted for v5. |
| `artifacts/dynamic_multi_policy_demo_20261020/model.joblib` | Depth-8 cost regressor, 19 inputs, 6 outputs | Passes current loader; helper exists, but workload ID is absent from current catalog. |
| `artifacts/dynamic_v5_azure_retrained/model.joblib` | Depth-2 cost regressor, 19 inputs, 6 outputs | Passes current loader; separately reported experiment, not selectable dashboard scheduler. |
| `artifacts/dynamic_azure_adapted_20261020/model.joblib` | Depth-3 four-output cost regressor with separate metadata bundle | Deserializes; generic loader rejects missing feature schema. Its dedicated experimental code loads the bundle directly; not the original v5 route. |

The default-looking paths `artifacts/model.joblib`, `artifacts/demo_tree.joblib` and `artifacts/dynamic_model.joblib` are absent. Therefore a default CLI path can fail even though a compatible historical binary exists elsewhere. The UI's metadata-unavailable-inference statement is hardcoded, not a scan of these paths.

`artifacts/demo_tree.json` and `results/six_policy/model.json` share headline accuracy, feature importance, settings and most common fields; their candidate-metrics records differ. Do not assert byte-identical provenance or silently substitute one artifact based solely on the shared headline numbers.

## Saved evidence: compare within one cohort

### Original v5 synthetic audit — 240 development workloads

Source: `results/dynamic_v5_20261019/research_summary.json`, `audit` entries. These are saved results, not rerun here.

| Policy | Mean weighted score ↓ | Mean workload P95 ↓ | Mean starvation flags ↓ |
|---|---:|---:|---:|
| Original v5 cost tree | 0.135887305 | 7.645000 | 13.679167 |
| Tuned MLFQ | 0.167563610 | 7.487292 | 14.066667 |
| Default MLFQ | 0.181475007 | 18.118542 | 14.545833 |

The cost tree improves score against tuned MLFQ but slightly worsens mean P95; final audit acceptance is null. Never compare these six-reference synthetic scores directly with Azure five-reference scores.

### Original v5 Azure development baseline — 12 common completed workloads

Source: `results/dynamic_azure_generalization/baseline_rows.json`, aggregated by `autoscheduler/azure_generalization_report.py:summarize` (44–84). Score, waiting and P95 means were independently recalculated from the saved rows during this inspection; no workload evaluation was rerun.

| Metric | Original v5 | Tuned MLFQ | Interpretation |
|---|---:|---:|---|
| Weighted score ↓ | 0.132042872 | 0.076081572 | Tuned MLFQ lower |
| Average waiting, ms ↓ | 16304.782740 | 32262.493432 | v5 lower |
| Average first response, ms ↓ | 991.355316 | 0.301921 | Tuned MLFQ lower |
| Mean workload P95, ms ↓ | 2197.908333 | 2.912500 | Tuned MLFQ lower |
| Average turnaround, ms ↓ | 20058.312740 | 36016.023432 | v5 lower |
| Utilization fraction | 0.113453851 | 0.113453851 | Tie |
| Throughput, jobs/ms | 0.0000787051 | 0.0000787051 | Tie |
| Mean starvation flags | 44.166667 | 73.333333 | v5 fewer diagnostic flags |

17 selected workloads, 12 complete across all policies, 8 policy timeouts. These are conditional development results with incomplete coverage; 73 genuinely untouched provenance groups remain reserved according to `untouched_holdout_manifest.json`. “ms” denotes the Azure simulator mapping, not measured kernel latency.

### Azure-retrained v5 — a separate six-workload development cohort

Source: `results/dynamic_v5_azure_retrained_20261020/results.json`.

| Policy | Weighted score ↓ | Average waiting, ms ↓ | Mean workload P95, ms ↓ | Total accepted switches |
|---|---:|---:|---:|---:|
| Original v5 | 0.041666667 | 9.047170 | 86.066667 | 190 |
| Azure-retrained v5 | 0.027529164 | 18.100629 | 0 | 2 |
| Tuned MLFQ | 0.027529164 | 18.100629 | 0 | 0 |

The retrained result improves score/response relative to original v5 on these previously examined development workloads, but matches MLFQ and worsens waiting relative to original v5. No strict improvement over tuned MLFQ; no promotion.

### Separate model comparison — do not borrow its accuracy for v5

Source: `results/real_desktop_ml/decision-tree-demo/summary.json`.

| Regressor family | Validation realized cost | Locked realized cost | Action agreement | Recorded decision P99 ms | Selected in pilot |
|---|---:|---:|---:|---:|---|
| Dummy | 0.685690 | 0.75 | 0% | 0.089667 | No |
| Ridge | 0 | 0 | 100% | 0.520542 | Yes |
| Decision Tree | 0 | 0 | 100% | 0.109417 | No |
| Random Forest | 0 | 0 | 100% | 5.758875 | No |
| Histogram Gradient Boosting | 0 | 0.000048588 | 95.7627% | 10.824083 | No |

These are saved per-family table values, not a fresh benchmark. Only 2 locked traces exist versus 60 required; status is INSUFFICIENT_DATA, improvement and confidence gates fail. Action agreement is not original-classifier accuracy. The separately reported overall gate timing and family-comparison timing need not be identical measurements.

The later `results/dynamic_v5_azure_prediction_comparison_20261020/selection.json` has `chosen: null` and an empty eligible list. It does not support a new winning model claim.

### Three different quantities to keep separate

- **Classification/action agreement:** fraction of predicted labels equal to the selected reference label; sensitive to ties and class imbalance.
- **Predicted scheduling cost:** model output before running the candidate trajectory; may be badly calibrated under shift.
- **Observed scheduling performance:** metrics calculated from the completed simulator execution; still not measured OS performance.

For numerical cost predictions, MAE = mean(|prediction−target|), RMSE = sqrt(mean((prediction−target)²)), and R² compares squared error with target-mean variance. The saved original-v5 Azure prediction partition has 72 decision states in 6 provenance groups, MAE 0.012602638, RMSE 0.019537636 and pooled R² −3161.553846. This development fit check is separate from both scheduling cohorts above. `results/dynamic_v5_review/analysis.json` leaves synthetic internal-test numerical-fit metrics unrecorded; do not fill them with the Azure values.

## Critical discrepancies to explain honestly

1. **SJF UI wording:** `dashboard/web/src/Simulation.jsx:7` and a Research.jsx explanation say “next burst”; `simulator/engine.py:119` and `tests/test_schedulers.py:15–23` use total `burst_time`.
2. **Classifier availability:** `dashboard/adapter.py:60–61` claims the matching fitted six-policy binary is unavailable without checking paths. A compatible `results/six_policy/model.joblib` exists and loads; dashboard classifier inference is still disabled. Exact identity to the displayed metadata is not conclusively established by shared scores.
3. **Contradictory demo footer:** `Simulation.jsx:22` shows a matched selected-case comparison, while line 30 still says no matched tuned-MLFQ comparison is claimed. Describe the shown comparison as illustrative, not independent research.
4. **Unreachable experimental branch:** `adapter.py:191` checks `dynamic_multi_policy` after `processes(workload)`, but that ID is absent from `WORKLOADS` (26–40). The experimental artifact and helpers are not the current catalog demo.
5. **Shared-engine shorthand:** static wrappers use `simulator/engine.py:simulate`; dynamic execution uses `autoscheduler/dynamic.py:_dispatch`. Tests check equivalence; one shared dispatcher body is not implemented.
6. **Incomplete metric docstring:** `simulator/simulator.py:11` omits I/O from waiting; executable line 72 subtracts it.
7. **Raw proposal versus selected:** ordinary `RoutingDecision.selected` has already passed action resolution and tail rewriting. Original-v5 playback correctly says raw costs/proposals are not recorded; do not infer them from selected.
8. **Supported action set versus fitted behavior:** original v5's seven leaves choose Priority or tied FCFS, not all five eligible schedulers. Returning to MLFQ often comes from controller logic.
9. **Saved/source/build distinction:** current locally modified JSX is the basis of this guide. A pre-existing `web/dist` bundle may not match; this was not rebuilt or browser-verified.
10. **No online self-learning or model promotion:** code performs offline fitting and runtime inference. The current result supports a research controller and a tuned-MLFQ recommendation, not universal ML superiority.

## Faculty question bank — 25 code-oriented questions

### Q1. How does regression choose a scheduling policy?

The tree emits six action-cost deltas and PolicyCostModel.predict selects their minimum, breaking ties by action order. The controller then applies dwell, pressure and benefit checks before changing active policy.

**Open:** `autoscheduler/model.py:22–36; autoscheduler/dynamic.py:520–545`.

**Caveat:** A proposal is not an accepted transition.

### Q2. Why use regression instead of classification?

Regression estimates how much better an action might be, enabling the absolute cost-margin check. Classification predicts a label, and its probability does not quantify scheduling benefit.

**Open:** `autoscheduler/model.py:31–36,179–188`.

**Caveat:** Regression error can still choose a harmful action; this is a tradeoff, not proof of superiority.

### Q3. Why did you research a classifier if the demo uses regression?

The original classifier selects one static policy per whole workload, and a separate dynamic classifier was compared during development. The current dashboard explicitly loads the v5 policy_cost artifact; the classifier is not a runtime stage before it.

**Open:** `autoscheduler/adaptive.py:30–43; autoscheduler/dynamic_v5_experiment.py:183–198; dashboard/adapter.py:90–107`.

**Caveat:** A train-only pilot classifier also samples offline training states; it is not a hybrid deployment.

### Q4. What exactly is dynamic?

The active policy and ready ordering can change within the same unfinished execution state. Completed CPU work, I/O blocking and process identity persist across transitions.

**Open:** `autoscheduler/dynamic.py:291–296,542–552`.

**Caveat:** Tree parameters do not change during simulation.

### Q5. What triggers a policy review and switch?

A review becomes due at the configured epoch and runs at the next dispatch boundary with ready work. A different selected action must pass dwell and protection, then qualify through safety return, explicit fallback or confidence plus margin.

**Open:** `autoscheduler/dynamic.py:508–532`.

**Caveat:** The loaded v5 has 10-tick epochs and a 20-tick minimum dwell, not guaranteed 10-tick reaction time.

### Q6. Why can a lower predicted cost be rejected?

The benefit may be below 0.005, a job may still await first service, recent arrivals/I/O may make departure risky, or minimum dwell may not have elapsed. The reason is recorded with the post-guard selected and active actions.

**Open:** `autoscheduler/dynamic.py:94–123,529–550`.

**Caveat:** The ordinary demo record does not retain the raw prediction before guards.

### Q7. How does the simulator execute a process?

It releases due events, selects a ready entry and advances time by a current burst, quantum or event-limited duration. It then requeues unfinished service, blocks for I/O or records completion.

**Open:** `autoscheduler/dynamic.py:302–392; simulator/engine.py:139–249`.

**Caveat:** This is discrete-event bookkeeping, not a hardware or OS CPU execution.

### Q8. How are waiting, response and turnaround computed?

Turnaround is completion minus arrival; response is first start minus arrival. Waiting is turnaround minus total CPU minus total I/O, because blocked I/O is not ready-queue waiting.

**Open:** `simulator/simulator.py:69–85`.

**Caveat:** The introductory waiting formula omits I/O; show the executable formula.

### Q9. How is P95 calculated and aggregated?

The percentile interpolates between sorted responses at index 0.95(n−1). Research summaries often average each workload's P95 rather than pool all process responses.

**Open:** `autoscheduler/dynamic.py:472–478; autoscheduler/dynamic_v5_experiment.py:93–110`.

**Caveat:** Do not swap mean-of-percentiles with pooled P95.

### Q10. Why compare against tuned MLFQ?

MLFQ uses observed CPU service and aging to provide a strong response baseline without a prediction model. The v5 experiment selected static parameters on development validation before comparing learned families.

**Open:** `autoscheduler/dynamic_v5_experiment.py:158–178; scheduler/mlfq.py:9–24`.

**Caveat:** (1,2,4), aging 40 is the frozen recommendation, not a proven universal optimum.

### Q11. Why did v5 perform poorly on Azure response tails?

Azure wall-clock mean proxies can create long non-preemptive Priority dispatches that postpone later arrivals' first service and the next controller review. The saved diagnostics also show distribution shift and a tree whose admitted departures largely favor Priority.

**Open:** `autoscheduler/dynamic.py:330–346,508–510; results/dynamic_azure_generalization/model_tree_audit.json; baseline_decisions.json`.

**Caveat:** This is a code-supported explanation with cohort evidence, not a causal proof for all workloads.

### Q12. How do you know the ML model actually participates?

The loader identifies a real fitted artifact, and _prediction invokes it at reviews. The selected tiny demo produced an accepted Priority departure and the saved external diagnostics record predictions and accepted events.

**Open:** `dashboard/adapter.py:90–107; autoscheduler/dynamic.py:457–469; tests/test_switching_demo.py:25–27`.

**Caveat:** Participation is not proof of benefit; mandatory safety returns also count as transitions.

### Q13. Where and when is training performed?

Offline Python/sklearn routines generate labeled tables and save joblib artifacts; inference loads those artifacts. The source identifies the training entry points and saved protocol, but not the physical host for every historical run.

**Open:** `autoscheduler/cli.py:188–205; autoscheduler/model.py:179–245; autoscheduler/dynamic_v5_experiment.py:136–214`.

**Caveat:** Do not invent a cloud platform, GPU requirement or online retraining loop.

### Q14. Can features read future arrivals or true remaining work?

The realistic dynamic extractor reads released queues and accumulated service/history, not pending work or remaining_time. The engine and offline target labeler have full workload information for execution and counterfactual labels.

**Open:** `autoscheduler/dynamic.py:422–454,557–604; tests/test_dynamic_contract.py:29–50`.

**Caveat:** The historical nine-feature classifier uses declared workload information and must be described separately.

### Q15. How do the splits prevent leakage?

Dynamic training groups rows by complete trace seed; real Linux splitting groups complete metadata tuples. Azure selection also builds connected provenance groups so related function observations can be kept together.

**Open:** `autoscheduler/model.py:76–101,134–138; autoscheduler/real_split.py:37–58; autoscheduler/azure_generalization_evaluation.py:24–35`.

**Caveat:** Previously inspected development partitions are not a fresh final holdout.

### Q16. What does cost zero mean?

A zero target means equal weighted score to the chosen MLFQ continuation reference under the label protocol. It does not mean zero delay or zero CPU cost.

**Open:** `autoscheduler/dynamic.py:590–603`.

**Caveat:** Some ties arise from safety-projected actions or normalization; strict label agreement can understate equivalent actions.

### Q17. Does confidence 0.8 make the regressor calibrated?

No. That threshold is meaningful for classifier probabilities; _prediction supplies confidence 1.0 for the cost wrapper. The regressor's numerical safeguard is the predicted cost margin.

**Open:** `autoscheduler/dynamic.py:462–468,527–532`.

**Caveat:** Do not describe regressor confidence 1.0 as 100% certainty.

### Q18. Which policies can current v5 switch among?

Its contract supports FCFS, RR, Priority, Priority RR and MLFQ plus No Switch. Inspecting the actual original tree's leaves shows raw winners only Priority or tied FCFS; guards and fallback can return MLFQ.

**Open:** `autoscheduler/evaluation.py:33–36; autoscheduler/dynamic.py:86–100; artifacts/dynamic_v5_20261019/policy_cost/model.joblib`.

**Caveat:** Eligibility and actual fitted behavior are different; SJF/SRTF are excluded from realistic routing.

### Q19. What happens if the model is unavailable?

Core run_dynamic can use an explicit fallback policy and still enforce dwell. The dashboard _original_v5 raises on a missing/hash-mismatched model before calling the controller, so the UI asks for a static policy instead.

**Open:** `autoscheduler/dynamic.py:515–532; dashboard/adapter.py:93–100; dashboard/app.py:30–35`.

**Caveat:** There is no blanket automatic recovery from every prediction or compatibility exception.

### Q20. Does context-switch overhead exist?

The engine can insert CS intervals on PID changes when a nonzero cost is configured. Current Priority RR uses one tick; the recommended tuned MLFQ uses zero, while PID transitions are still counted.

**Open:** `simulator/engine.py:153–162; autoscheduler/dynamic.py:320–324; simulator/simulator.py:122–129`.

**Caveat:** Python inference time and ML policy-transition duration are not automatically charged to simulated time.

### Q21. Does SJF choose the shortest next CPU burst?

No, the implementation compares total burst_time across the process's CPU bursts. It runs the current burst non-preemptively, whereas SRTF compares the current remaining burst.

**Open:** `simulator/engine.py:115–123; tests/test_schedulers.py:15–23`.

**Caveat:** Dashboard wording and an old explanatory answer say next burst; use the code's actual semantics.

### Q22. What do the Azure results actually support?

Across the 12 all-policy-complete workloads, v5 reduces average waiting but has a higher weighted score and much worse response tails than tuned MLFQ. Eight policy timeouts and incomplete high-load coverage prevent a population-wide success claim.

**Open:** `results/dynamic_azure_generalization/baseline_rows.json; autoscheduler/azure_generalization_report.py:44–84`.

**Caveat:** The later Azure-retrained six-workload result matches MLFQ, not surpasses it.

### Q23. Are displayed results live?

The tiny simulation is computed on request and then played back, with caching. Research panels use saved JSON via catalog or build-time imports; their statistics are not recomputed when you open the page.

**Open:** `dashboard/adapter.py:54–73,188–238; dashboard/web/src/Simulation.jsx:46–50; dashboard/web/src/RealSourceDynamic.jsx:5–7`.

**Caveat:** The current served dist bundle may differ from edited source; no rebuild was performed here.

### Q24. Which tests should I open to defend the implementation?

Show the hidden-future mutation test, the MLFQ quantum/aging tests, and the selected demo's transition assertions. Together they target input observability, policy behavior and integration without relying on a screenshot.

**Open:** `tests/test_dynamic_contract.py:29–50; tests/test_mlfq.py:9–49; tests/test_switching_demo.py:8–51`.

**Caveat:** Their existence is verified; a fresh full-suite pass is not claimed for this documentation task.

### Q25. What is the main limitation and honest conclusion?

The system demonstrates learned policy proposals and constrained switching in a single-CPU simulator, but original v5 does not beat tuned MLFQ overall on the completed external Azure cohort. Proxy durations, reconstructed arrivals, synthetic bias, incomplete coverage and no validated kernel integration limit real-world claims.

**Open:** `configs/research_status.json; autoscheduler/real_dataset.py:15–16,46–63; results/dynamic_azure_generalization/summary.json`.

**Caveat:** Recommend tuned static MLFQ for this simulator; do not claim production or kernel superiority.

## Claim verification table

VERIFIED means supported within the stated scope. PARTIALLY VERIFIED means a narrower behavior is supported. NOT IMPLEMENTED also marks a proposed capability/claim absent from the inspected path; it is not a claim that every similarly named experiment is absent. UNKNOWN means the inspection does not establish the fact.

| Proposed claim | Status | Evidence | Safe wording | What not to claim |
|---|---|---|---|---|
| Original v5 uses a fitted decision-tree regressor | VERIFIED | autoscheduler/model.py:15–36; dashboard/adapter.py:90–107; loaded original artifact | The dashboard loads the original depth-3 multi-output cost tree. | A neural network or classifier–regressor hybrid. |
| The classifier and regressor are integrated at runtime | NOT IMPLEMENTED | autoscheduler/model.py:179–188; autoscheduler/dynamic_training.py:41–51; dashboard/adapter.py:104–107 | They are separate families; a pilot classifier only augments offline training. | A classifier selects a regressor or both vote during v5 execution. |
| All model artifacts work with the current loader | PARTIALLY VERIFIED | autoscheduler/model.py:314–362; inventory below | v5/v6 and several current bundles load; historical schemas are rejected. | A deserialized artifact is automatically runtime compatible. |
| The historical classifier binary is unavailable | PARTIALLY VERIFIED | dashboard/adapter.py:60–61; results/six_policy/model.joblib | The panel is metadata-only, but a compatible binary exists elsewhere locally. | The hardcoded missing-binary sentence is a complete artifact inventory. |
| Dynamic switching actually occurs | VERIFIED | autoscheduler/dynamic.py:542–549; selected demo in-memory check; results/dynamic_azure_generalization/baseline_decisions.json | The selected tiny demo switches twice; external logs also record transitions. | Every preset switches or each accepted return is a learned decision. |
| All five dynamic policies are proposed by original v5 | NOT IMPLEMENTED | Original artifact's seven leaf argmins; autoscheduler/model.py:23 | The action contract allows five policies; fitted raw winners are Priority/FCFS. | A multi-policy eligibility list proves diverse learned behavior. |
| The controller uses observed-only features | VERIFIED | autoscheduler/dynamic.py:422–454; tests/test_dynamic_contract.py:29–50 | The realistic dynamic extractor excludes declared remaining/future work. | The offline nine-feature classifier also satisfies this contract. |
| Safety checks guarantee response bounds | PARTIALLY VERIFIED | autoscheduler/dynamic.py:94–123,508–532 | Guards and minimum dwell constrain accepted switches. | Immediate reaction, proven starvation freedom or a hard response upper bound. |
| Missing models always fall back automatically | PARTIALLY VERIFIED | autoscheduler/dynamic.py:515–532; dashboard/adapter.py:93–100 | Core explicit-None fallback exists; dashboard load failure is an error. | All schema, hash or prediction failures transparently recover. |
| The original classifier has around 73%/76% accuracy | VERIFIED | results/six_policy/model.json; artifacts/demo_tree.json | Historical test 73.0667%, validation 76.8% on synthetic labels. | Those values are v5 regression accuracy or scheduler improvement. |
| Decision Tree won every model comparison | NOT IMPLEMENTED | results/real_desktop_ml/decision-tree-demo/summary.json | Ridge was selected in this separate pilot; data sufficiency failed. | The folder name proves Decision Tree superiority. |
| v5 improves Azure scheduling overall | PARTIALLY VERIFIED | results/dynamic_azure_generalization/baseline_rows.json; results/dynamic_azure_generalization/summary.json; recomputed complete-subset means | Waiting/turnaround improve, weighted score and response tails worsen. | An overall baseline win or final validation success. |
| Azure-retrained v5 beats tuned MLFQ | NOT IMPLEMENTED | results/dynamic_v5_azure_retrained_20261020/results.json | It matches MLFQ on six examined development workloads. | An independent external or final-holdout win. |
| Azure observations are actual CPU bursts and OS arrivals | NOT IMPLEMENTED | AzureWorkloads/scripts/convert_workloads.py:30–55; metadata.json | Counts and daily duration summaries are observed; scheduler inputs are proxies/reconstructions. | Measured Linux CPU scheduling traces. |
| Refinement covers all Azure invocations | NOT IMPLEMENTED | AzureWorkloads/reports/descriptive_statistics.json:coverage | High-load hours are eligible; actual sampled occurrence coverage is about 0.00416%. | 0% cap-only exclusion means 100% replay coverage. |
| Ceiling adds no distortion to these published means | VERIFIED | AzureWorkloads/reports/workload_statistics.md:43–57; AzureWorkloads/scripts/convert_workloads.py:50 | Positive published means are integral, so measured added pipeline error is zero. | No upstream quantization or daily-mean information loss. |
| The project trains online during demo execution | NOT IMPLEMENTED | dashboard/adapter.py:104–107; autoscheduler/dynamic.py:481–554 | Training is offline; simulation performs inference. | Self-learning means a continuous runtime fit loop. |
| Dashboard metrics are all freshly computed | PARTIALLY VERIFIED | dashboard/adapter.py:54–73,188–238; dashboard/web/src/RealSourceDynamic.jsx:5–7 | Tiny simulations are request-computed/cached; research panels read saved outputs. | Opening a panel reruns experiments. |
| SJF uses next CPU burst | NOT IMPLEMENTED | simulator/engine.py:119; tests/test_schedulers.py:15–23 | This implementation uses total declared CPU burst_time. | The misleading Simulation.jsx:7 wording. |
| There is one shared dispatch implementation | PARTIALLY VERIFIED | simulator/engine.py:simulate; autoscheduler/dynamic.py:_dispatch | Static wrappers share an engine; dynamic has a separate stateful dispatcher and equivalence tests. | Every active scheduler calls one common dispatch body. |
| The current browser bundle matches edited JSX | UNKNOWN | dashboard/app.py:46–48; web/dist; local dirty JSX | This guide describes current source; bundle/browser freshness was not checked. | The visible running UI must already include local edits. |
| A deployable ML Linux scheduler is validated | NOT IMPLEMENTED | autoscheduler/real_dataset.py:15–16,46–63; configs/research_status.json | Offline trace/replay tooling exists; no ML model is promoted. | Kernel speedups, deployed sched_ext, or multicore validation. |
| Physical training host and original runtime are established | UNKNOWN | Saved experiment protocols and artifacts | Entry points, seeds, settings and artifacts are inspectable. | An invented training machine, cloud provider or wall-clock duration. |

## Final rapid revision

### A. Top 10 code chunks

These are the excerpts to rehearse first. The surrounding explanations and limitations remain in the matching topics above.

#### 1. Regressor action proposal — `PolicyCostModel.predict / switch_allowed`

Source: [autoscheduler/model.py](../autoscheduler/model.py), lines **22–36**.

```python
    def predict(self, matrix):
        return [self.policies[min(range(len(costs)), key=lambda i: (costs[i], i))]
                for costs in self.regressor.predict(matrix)]

    def predict_benefits(self, matrix):
        """Expected score improvement relative to immediate MLFQ continuation."""
        return [dict(zip(self.policies, map(lambda cost: -float(cost), costs)))
                for costs in self.regressor.predict(matrix)]

    def switch_allowed(self, features, active, selected):
        from autoscheduler.dynamic import DYNAMIC_FEATURE_NAMES

        costs = self.regressor.predict([[features[name] for name in DYNAMIC_FEATURE_NAMES]])[0]
        baseline = "No Switch" if "No Switch" in self.policies else active
        return bool(costs[self.policies.index(baseline)] - costs[self.policies.index(selected)] >= self.switch_margin)
```

**Say:** The model predicts costs, converts their minimum into an action, and requires a numerical gain over staying. The controller still makes the final acceptance decision.

#### 2. Final acceptance condition — `run_dynamic`

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **522–532**.

```python
            fallback = config.fallback_policy is not None and (model is None or confidence < config.confidence_threshold)
            if fallback:
                selected = config.fallback_policy
            selected, safety_reason = _tail_action(features, active, selected, config)
            safety_return = safety_reason in {"excursion_expired", "first_response_return"}
            # Cost regressors use an absolute predicted advantage over the active
            # policy. This is a margin safeguard, not a calibrated probability.
            margin_ok = not hasattr(model, "switch_allowed") or model.switch_allowed(features, active, selected)
            dwell_elapsed = state.current_time - last_switch >= config.dwell_epochs * config.epoch_ticks
            protected = _protected(features, active, selected, config)
            accepted = selected != active and dwell_elapsed and not protected and (safety_return or fallback or (confidence >= config.confidence_threshold and margin_ok))
```

**Say:** Fallback and tail guards can rewrite the action. Dwell and first-service protection still apply before a policy change is accepted.

#### 3. Observed feature inputs — `extract_dynamic_features`

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **422–434**.

```python
def extract_dynamic_features(
    state: _State, active_policy: str = "Round Robin", dwell_remaining_ticks: int = 0,
) -> dict[str, float]:
    """Read only execution history and currently observed queues, in simulator ticks."""
    candidates = [item.process for item in state.ready] + [process for _, process, _, _ in state.blocked]
    priorities = [process.priority for process in candidates]
    waits = [max(0, state.current_time - item.time) for item in state.ready]
    service: dict[str, int] = {}
    for pid, start, end in state.timeline:
        if pid != "CS":
            service[pid] = service.get(pid, 0) + end - start
    durations = state.completed_burst_durations
    first_waits = [max(0, state.current_time - item.time) for item in state.ready if item.process.pid not in service]
```

**Say:** Features use released queues and the timeline so far. Completed bursts are history; remaining burst lengths and future arrivals do not enter this extractor.

#### 4. Dispatch and idle jump — `_dispatch`

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **306–324**.

```python
    _release(state, state.current_time)
    if not state.ready:
        times = [process.arrival_time for process in state.pending]
        times.extend(wake_time for wake_time, *_ in state.blocked)
        if not times:
            return
        state.current_time = min(times)
        _release(state, state.current_time)
    started = perf_counter_ns()
    _rebuild_ready(state, policy, priority_rr_config)
    ready = state.ready.pop(0)
    if decision_times_ns is not None:
        decision_times_ns.append(perf_counter_ns() - started)
    process = ready.process
    switch_cost = priority_rr_config["context_switch_cost"] if policy == "Priority RR" else 0
    if state.last_pid is not None and state.last_pid != process.pid and switch_cost:
        state.timeline.append(("CS", state.current_time, state.current_time + switch_cost))
        state.current_time += switch_cost
        _release(state, state.current_time)
```

**Say:** The simulator jumps to the next event when idle, picks a ready process and applies the configured modeled overhead. It does not advance an empty CPU one tick at a time.

#### 5. MLFQ aging — `simulate.age_ready`

Source: [simulator/engine.py](../simulator/engine.py), lines **90–101**.

```python
    def age_ready() -> None:
        nonlocal sequence
        if policy != "mlfq":
            return
        eligible = (item for item in ready if item.queue_level > 0
                    and current_time - item.aging_since >= (aging_threshold or 1))
        for item in sorted(eligible, key=lambda candidate: candidate.sequence):
            item.queue_level -= 1
            item.quantum_used = 0
            item.aging_since = current_time
            item.sequence = sequence
            sequence += 1
```

**Say:** Waiting lower-level jobs move up one level and get a fresh quantum budget. This mitigates long waits without proving a general response-time bound.

#### 6. Core metric formulas — `compute_metrics`

Source: [simulator/simulator.py](../simulator/simulator.py), lines **69–85**.

```python
    metrics = []
    for p in scheduled:
        turnaround = p.completion_time - p.arrival_time
        waiting    = turnaround - p.burst_time - p.total_io_time
        response   = p.start_time - p.arrival_time
        metrics.append(ProcessMetrics(
            pid             = p.pid,
            arrival_time    = p.arrival_time,
            burst_time      = p.burst_time,
            priority        = p.priority,
            start_time      = p.start_time,
            completion_time = p.completion_time,
            turnaround_time = turnaround,
            waiting_time    = waiting,
            response_time   = response,
            post_io_response_times=tuple(p.post_io_response_times),
        ))
```

**Say:** Waiting excludes both CPU service and blocked I/O. Response is measured only to the first CPU service, while turnaround lasts until completion.

#### 7. Eligible policies — `ALGORITHMS / DEPLOYABLE_ALGORITHMS`

Source: [autoscheduler/evaluation.py](../autoscheduler/evaluation.py), lines **24–36**.

```python
    "Priority RR": (
        priority_round_robin,
        {"quantum": 2, "aging_interval": 8, "context_switch_cost": 1},
    ),
}

SELECTOR_ALGORITHMS = ALGORITHMS

# The historical six-policy simulation registry intentionally includes oracles.
DEPLOYABLE_ALGORITHMS = {
    name: ALGORITHMS[name] for name in ("FCFS", "Round Robin", "Priority", "Priority RR")
}
DEPLOYABLE_ALGORITHMS["MLFQ"] = (mlfq, {"quanta": (2, 4, 8), "aging_threshold": 20})
```

**Say:** The historical registry contains oracle references. The realistic dynamic set keeps only FCFS, RR, Priority, Priority RR and MLFQ.

#### 8. Active fitted artifact — `_original_v5 / _run_v5`

Source: [dashboard/adapter.py](../dashboard/adapter.py), lines **90–107**.

```python
def _original_v5():
    from autoscheduler.dynamic import DYNAMIC_FEATURE_NAMES, DynamicRouterConfig
    from autoscheduler.model import load_model, load_model_metadata
    path = ROOT / DYNAMIC_V5_ARTIFACT
    if not path.exists():
        raise ValueError('Original v5 artifact is unavailable; select a static policy.')
    expected = read_json('results/real_source_dynamic_review_20261020/dashboard.json')['model_sha256']
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Original v5 artifact hash differs from its verified report.')
    config = DynamicRouterConfig(**load_model_metadata(path)['dynamic_config'])
    model = load_model(path, DYNAMIC_FEATURE_NAMES, expected_dynamic_config=config)
    return model, config


def _run_v5(jobs):
    from autoscheduler.dynamic import run_dynamic
    model, config = _original_v5()
    return run_dynamic(jobs, model, config)
```

**Say:** The dashboard checks the original artifact's hash and schema before execution. It does not silently substitute the Azure-retrained or experimental model.

#### 9. Training action-cost targets — `_counterfactual_label`

Source: [autoscheduler/dynamic.py](../autoscheduler/dynamic.py), lines **589–604**.

```python
            _dispatch(trial, policy, priority_rr_config)
        _switch_policy(trial, policy, continuation)
        _run_to_completion(trial, continuation, priority_rr_config)
        results[action] = _simulation(trial, action)
    if references is None:
        # Direct callers still get one fixed reference scale, never per-action
        # normalization. Dataset generation supplies full-workload static bounds.
        references = results
    baseline = score_result_against_reference(results[continuation], references)
    scores = {policy: score_result_against_reference(results[policy], references) - baseline for policy in policies}
    label = min(policies, key=lambda policy: (scores[policy], policies.index(policy)))
    if "No Switch" in scores and scores["No Switch"] <= scores[label] + 1e-12:
        label = "No Switch"
    elif active_policy in scores and scores[active_policy] <= scores[label] + 1e-12:
        label = active_policy
    return label, scores
```

**Say:** Offline trials end in MLFQ continuation and share one metric scale. Targets are score differences, with explicit no-switch tie handling.

#### 10. Schedule validation gates — `validation_metrics`

Source: [autoscheduler/dynamic_training.py](../autoscheduler/dynamic_training.py), lines **105–120**.

```python
    intervals = {name: (paired_bootstrap_ci(values) if min(values) != max(values) else
                 {"mean": values[0], "ci_low": values[0], "ci_high": values[0]}) for name, values in differences.items()}
    gates = {"score": intervals["score"]["ci_high"] < 0,
             "p95_response": intervals["p95_response"]["ci_high"] <= 0,
             "starvation": intervals["starvation"]["mean"] <= 0,
             "latency": max(latencies) < 10,
             "original_rr_score": intervals["rr_score"]["ci_high"] <= 0,
             "original_rr_p95": intervals["rr_p95_response"]["ci_high"] < 0}
    return {
        "validation_schedule_score": mean(scores),
        "validation_schedule_p95_response": mean(responses),
        "validation_schedule_starvation": mean(starvations),
        "validation_schedule_eligible": all(gates.values()),
        "validation_schedule_gates": gates, "validation_schedule_intervals": intervals,
        "validation_schedule_max_workload_p99_ms": max(latencies),
    }
```

**Say:** A good mean prediction metric is not enough. The candidate must satisfy score, response, starvation and latency conditions on realized development schedules.

### B. One-minute technical overview

> AutoScheduler is a single-CPU simulator with classical policies and an experimental ML controller. Static schedulers use an event-driven engine; the dynamic path preserves its own execution state across policy changes. Original v5 loads a small decision-tree regressor, observes 19 history and queue features, and predicts six action costs. The controller considers the lowest cost, but applies a benefit margin, first-service protection, arrival-pressure rules and minimum dwell. Changes occur at dispatch boundaries, and excursions return to MLFQ. Training happens offline using synthetic counterfactual labels; inference does not retrain. We calculate waiting, turnaround, first response and a weighted score, then separately examine response tails and starvation flags. The selected demo really switches, but the completed Azure-derived evaluation shows worse score and response tails despite lower waiting. Tuned MLFQ remains the simulator recommendation, and no kernel-performance claim is established.

### C. Model differences

| Component | Input | Output / behavior | Learning and role |
|---|---|---|---|
| Original offline DecisionTreeClassifier | 9 whole-workload statistics including declared CPU work | One scheduler label before the run | Offline synthetic label learning; separate historical selector |
| Original v5 PolicyCostModel / DecisionTreeRegressor | 19 observed-state inputs; fitted tree uses 3 | Six action-cost deltas; wrapper chooses argmin | Offline synthetic fitting; active original-v5 demonstration |
| Dynamic v5 controller | Model proposal, observed pressure, current policy, dwell | Accept/hold/return, then dispatch under active policy | Rule-based control around inference; does not itself fit a model |
| Tuned MLFQ | Ready entries, service/quantum history, aging | Next runnable process using fixed feedback rules | Static parameters (1,2,4), aging 40; no ML inference |
| Azure-retrained v5 | Same 19-input dynamic contract | Separately fitted depth-2 cost outputs | Development-only experiment; not the selectable original-v5 artifact |
| Historical RR-benefit regressor | Separate 17-input schema | One decision between RR and oracle SRTF | Separate one-switch experiment, not v5 |

### D. Five high-risk questions

1. **“Is this a classifier–regressor hybrid?”** No. Runtime v5 uses the cost regressor and controller safeguards. A pilot classifier is used only to gather offline training states; a separate classifier family is compared independently.
2. **“Does a policy switch mean ML improved performance?”** No. Original v5's selected demo has two accepted events, but the external completed cohort regresses in weighted score and first-response tails. Returns to MLFQ are partly controller-mandated.
3. **“Can you claim 73% or 76% accuracy for v5?”** No. The traceable historical classifier values are 73.0667% test and 76.8% validation. V5 has different strict/tie-aware action agreement and numerical cost-error measures, none of which equals scheduler improvement.
4. **“Are these genuine Azure CPU schedules?”** No. Observed invocation counts and daily wall-clock means become reconstructed arrivals and CPU-demand proxies. They support controlled external-source simulation with explicit limitations.
5. **“Do the safeguards guarantee prompt response?”** No. They check observed pressure at dispatch boundaries; a long non-preemptive dispatch and minimum dwell can delay a return. The observed response-tail regression is precisely why no overall promotion is claimed.

### E. Code navigation cheat sheet

| Source file | Function / class | Purpose | What to say |
|---|---|---|---|
| `autoscheduler/model.py:15` | PolicyCostModel | Numerical action proposal and margin | “Costs first, label second, guards afterward.” |
| `autoscheduler/dynamic.py:481` | run_dynamic | Review and acceptance loop | “Switch only when due and feasible.” |
| `autoscheduler/dynamic.py:103` | _tail_action | Admission pressure / forced return | “Observed safety rules constrain excursions.” |
| `autoscheduler/dynamic.py:422` | extract_dynamic_features | Observed-only input vector | “History and released queues, not future work.” |
| `autoscheduler/dynamic.py:302` | _dispatch | Stateful dynamic CPU execution | “Consume service, block, requeue or complete.” |
| `simulator/engine.py:32` | simulate | Shared static-policy engine | “Ordering and quantum rules define the policy.” |
| `simulator/process.py:12` | Process | CPU/I/O state and invariants | “Total CPU and current burst are distinct.” |
| `simulator/simulator.py:54` | compute_metrics | Per-process outcome formulas | “Waiting excludes CPU and I/O.” |
| `autoscheduler/evaluation.py:86` | score_result_against_reference | Fixed-scale weighted comparison | “Lower score is relative to fixed policy bounds.” |
| `autoscheduler/dynamic.py:557` | _counterfactual_label | Offline action-cost labels | “Trial action then MLFQ continuation.” |
| `autoscheduler/dynamic_training.py:18` | build_training_data | Grouped data and train-only pilot | “Split traces, not nearby state rows.” |
| `autoscheduler/model.py:116` | train_model | Separate classifier/regressor fitting | “Offline fit, save, then load for inference.” |
| `autoscheduler/dynamic_training.py:82` | validation_metrics | Realized schedule gates | “Accuracy is not the final criterion.” |
| `AzureWorkloads/scripts/convert_workloads.py:21` | reconstruct | Azure observations to simulator inputs | “Reconstructed times and duration proxies.” |
| `autoscheduler/azure_generalization_report.py:17` | summarize | Cohort means and paired comparisons | “Retain failures and report the denominator.” |
| `dashboard/adapter.py:90` | _original_v5 | Artifact identity and loading | “This exact fitted model is used.” |
| `dashboard/adapter.py:189` | simulation | Request-computed result and playback payload | “Compute once, then replay returned frames.” |
| `dashboard/web/src/Research.jsx:40` | Intelligence | Saved evidence panels | “Original and retrained results stay separate.” |
| `autoscheduler/real_dataset.py:23` | build_development_action_rows | Offline replay-only labels | “Not measured kernel counterfactuals.” |

### F. Implementation limitations

- No runtime retraining, classifier–regressor hybrid, validated kernel controller or multicore/cache/affinity model in the reviewed scheduling path.
- Static and dynamic dispatch are separate bodies; equivalence is a tested contract, not guaranteed by sharing one function.
- The original cost tree uses only three of nineteen accepted features and proposes Priority or a tied FCFS action. Potential policy diversity exceeds observed fitted behavior.
- Dispatch-boundary review and minimum dwell delay reactions; non-preemptive excursions can harm first-response tails. Guards do not establish a formal response or starvation bound.
- Weighted objectives depend on chosen weights/reference policies, omit P95 directly and can reward waiting gains despite response regressions.
- Original v5 synthetic score improvement is accompanied by a tuned-baseline P95 regression; original v5 external Azure score/response gates fail. V6 is not promoted; Azure-retrained v5 only matches MLFQ on its six-workload development cohort.
- Azure arrivals are reconstructed, wall-clock means proxy CPU demand, priorities are neutral, I/O is unobserved, and sampled source contexts overlap. Zero added ceiling error in published integer means does not remove source quantization uncertainty.
- High-load eligibility is improved, but actual sampled traffic remains tiny and selected heavy evaluations have timeouts. Completion-only estimates are conditional; no population-wide or untouched-holdout superiority is shown.
- The separate replay prototype has only two locked traces against a 60-trace requirement. Its whole-replay action labels repeated across snapshots are development evidence, not state-specific measured kernel effects.
- Python controller P99, static selection timing, simulated milliseconds and OS latency are different measurements. Inference time is not automatically charged into simulated makespan.
- Historical model schemas and default artifact locations are not interchangeable. The dashboard can fail closed on missing or incompatible artifacts despite the core's explicit fallback option.
- Some UI descriptions are stale; saved panels and build-time JSON are not live experiments. The exact running browser bundle and physical historical training host remain UNKNOWN in this source-only review.
- The selected tiny scenario demonstrates real switching and has favorable expected comparison metrics, but its deliberate selection makes it illustrative rather than independent performance evidence.

This guide is a snapshot of the inspected implementation. No claims of new model fitting, full-suite validation, new research results or deployment approval are made.


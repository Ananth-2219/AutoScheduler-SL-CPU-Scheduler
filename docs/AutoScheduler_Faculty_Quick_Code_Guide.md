# AutoScheduler — Faculty Quick Code Review Guide

**Short answers. Real code. No unnecessary theory.**  |  Based on the detailed guide inspected on **21 October 2026** (local HEAD `9322bec`).

> **Use it like this:** If she asks, say the **What to say** line, open **Code to show**, explain the **2–3 key lines**, then stop. Only use the extra answer if she asks a follow-up.

> **Accuracy note:** Snippets below are copied from the supplied source guide, which inspected the repository. This shorter document does not recheck later code changes. Line numbers can shift.

## 30-second overview

> AutoScheduler is a CPU scheduling simulator. We implemented classical scheduling policies, then a dynamic controller that uses a trained regression tree to estimate the cost of possible policies. The controller can change the active policy during one simulation, subject to safeguards. We compare scheduling results with tuned MLFQ, including tests using Azure-derived workloads.

## Priority map — learn these first

| Priority | # | Topic | Code to open |
|---|---:|---|---|
| P0 · Must know | [1](#topic-1) | How regression chooses a policy | `autoscheduler/model.py` |
| P0 · Must know | [2](#topic-2) | How Dynamic v5 actually switches | `autoscheduler/dynamic.py` |
| P0 · Must know | [3](#topic-3) | What the 19 workload features mean | `autoscheduler/dynamic.py` |
| P0 · Must know | [4](#topic-4) | How the simulator runs a process | `autoscheduler/dynamic.py` |
| P0 · Must know | [5](#topic-5) | Why MLFQ is our baseline | `simulator/engine.py` |
| P0 · Must know | [6](#topic-6) | Where FCFS, RR, Priority, SJF and SRTF differ | `simulator/engine.py` |
| P0 · Must know | [7](#topic-7) | What a Process object stores | `simulator/process.py` |
| P0 · Must know | [8](#topic-8) | How waiting, response and score are calculated | `simulator/simulator.py` |
| P0 · Must know | [9](#topic-9) | Which fitted model the dashboard loads | `dashboard/adapter.py` |
| P1 · If asked | [10](#topic-10) | What our original Decision Tree Classifier did | `autoscheduler/dataset.py` |
| P1 · If asked | [11](#topic-11) | Where regression training targets come from | `autoscheduler/dynamic.py` |
| P1 · If asked | [12](#topic-12) | How we judged and selected models | `autoscheduler/dynamic_training.py` |
| P1 · If asked | [13](#topic-13) | What the Azure workload data really is | `AzureWorkloads/scripts/convert_workloads.py` |
| P1 · If asked | [14](#topic-14) | What the Azure evaluation actually showed | `autoscheduler/azure_generalization_report.py` |
| P1 · If asked | [15](#topic-15) | Tests that prove particular behaviors | `tests/test_dynamic_contract.py` |
| P2 · Optional | [16](#topic-16) | What the dashboard animation actually does | `dashboard/web/src/Simulation.jsx` |
| P2 · Optional | [17](#topic-17) | Which dashboard results are saved | `dashboard/app.py` |
| P2 · Optional | [18](#topic-18) | What our Linux trace and CLI code does | `autoscheduler/real_dataset.py` |

---

<a id="topic-1"></a>
## P0 · 1. How regression chooses a policy

**A. What to say:** “The regression tree predicts a cost for each possible action. We choose the lowest-cost action, but switch only if the controller allows it.”

**B. Code to show:** `autoscheduler/model.py` → `PolicyCostModel.predict / switch_allowed` (source lines 15–36).

**Code chunk 1** — show these exact source lines:
```python
    def predict(self, matrix):
        return [self.policies[min(range(len(costs)), key=lambda i: (costs[i], i))]
                for costs in self.regressor.predict(matrix)]
```

**Code chunk 2** — show these exact source lines:
```python
    def switch_allowed(self, features, active, selected):
        from autoscheduler.dynamic import DYNAMIC_FEATURE_NAMES

        costs = self.regressor.predict([[features[name] for name in DYNAMIC_FEATURE_NAMES]])[0]
        baseline = "No Switch" if "No Switch" in self.policies else active
        return bool(costs[self.policies.index(baseline)] - costs[self.policies.index(selected)] >= self.switch_margin)
```

**C. Explain the code:** predict() selects the lowest predicted cost. switch_allowed() checks whether that cost is sufficiently better than staying.

**D. Why this approach:** Costs show the possible benefit of changing policies, not just a label. **Alternative:** A classifier directly gives a policy name, but does not give a comparable cost difference.

**E. If she asks — Does regression itself switch algorithms?** No. It recommends an action; the controller decides whether to apply it.

**F. Don’t say:** Do not say it predicts a process ID, guarantees a better policy, or forms a classifier–regressor hybrid.

**G. Connected code:** `autoscheduler/dynamic.py → _prediction(), run_dynamic()`

---

<a id="topic-2"></a>
## P0 · 2. How Dynamic v5 actually switches

**A. What to say:** “Every few simulated ticks, the controller reviews the current workload. It switches only after checking timing, safety, and predicted benefit.”

**B. Code to show:** `autoscheduler/dynamic.py` → `run_dynamic / _tail_action` (source lines 508–554; 103–123).

**Code chunk 1** — show these exact source lines:
```python
            selected, safety_reason = _tail_action(features, active, selected, config)
            safety_return = safety_reason in {"excursion_expired", "first_response_return"}
            # Cost regressors use an absolute predicted advantage over the active
            # policy. This is a margin safeguard, not a calibrated probability.
            margin_ok = not hasattr(model, "switch_allowed") or model.switch_allowed(features, active, selected)
            dwell_elapsed = state.current_time - last_switch >= config.dwell_epochs * config.epoch_ticks
            protected = _protected(features, active, selected, config)
            accepted = selected != active and dwell_elapsed and not protected and (safety_return or fallback or (confidence >= config.confidence_threshold and margin_ok))
```

**Code chunk 2** — show these exact source lines:
```python
    if active != "MLFQ":
        if features["dwell_remaining_ticks"] <= 0:
            return "MLFQ", "excursion_expired"
        unserved = features["first_service_ready_count"]
        urgent = unserved > 0 and (
            unserved >= 2 or features["first_service_wait_max"] >= config.epoch_ticks
            or features["ready_wait_p95"] >= config.epoch_ticks or features["recent_arrivals"] > 0)
```

**C. Explain the code:** The code gets features, asks the model, applies safety rules, and sets accepted only when the conditions pass.

**D. Why this approach:** These checks prevent changing policies too frequently or leaving new jobs waiting unnecessarily. **Alternative:** Always switching to the predicted best policy is simpler but can be unstable.

**E. If she asks — Does it switch exactly every 10 ticks?** No. Reviews are due every 10 ticks, but execute at a dispatch boundary; the minimum dwell is 20 ticks.

**F. Don’t say:** Never claim instant switching or guaranteed response-time limits.

**G. Connected code:** `autoscheduler/model.py → switch_allowed(); autoscheduler/dynamic.py → _dispatch()`

---

<a id="topic-3"></a>
## P0 · 3. What the 19 workload features mean

**A. What to say:** “We use 19 values describing ready jobs, I/O, past CPU execution, waiting, arrivals and the current policy. We do not give the model future arrivals.”

**B. Code to show:** `autoscheduler/dynamic.py` → `extract_dynamic_features` (source lines 422–454).

**Code chunk 1** — show these exact source lines:
```python
    """Read only execution history and currently observed queues, in simulator ticks."""
    candidates = [item.process for item in state.ready] + [process for _, process, _, _ in state.blocked]
    priorities = [process.priority for process in candidates]
    waits = [max(0, state.current_time - item.time) for item in state.ready]
    service: dict[str, int] = {}
    for pid, start, end in state.timeline:
        if pid != "CS":
            service[pid] = service.get(pid, 0) + end - start
    durations = state.completed_burst_durations
```

**Code chunk 2** — show these exact source lines:
```python
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
```

**C. Explain the code:** The code reads the ready and blocked lists plus execution history, then returns a dictionary of feature values.

**D. Why this approach:** The model needs a quick summary of the current workload to estimate policy costs. **Alternative:** Feeding full process histories would preserve more details but be more complex.

**E. If she asks — What are the features?** Queue counts, completed-burst statistics, CPU service, priorities, waiting statistics, arrival/I/O activity, policy state and first-service waits.

**F. Don’t say:** The trained tree accepts 19 inputs but uses only 3 for splits: completed_burst_variance, ready_count and arrival_quiet_ticks.

**G. Connected code:** `autoscheduler/dynamic.py → _prediction()`

---

<a id="topic-4"></a>
## P0 · 4. How the simulator runs a process

**A. What to say:** “The simulator selects a ready process, runs it for a burst or time slice, then completes it, blocks it for I/O or sends it back to ready.”

**B. Code to show:** `autoscheduler/dynamic.py` → `_dispatch` (source lines 302–392).

**Code chunk 1** — show these exact source lines:
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
```

**Code chunk 2** — show these exact source lines:
```python
    while process.remaining_time:
        run_for = process.remaining_time
        if policy in {"Round Robin", "Priority RR"}:
            run_for = min(run_for, priority_rr_config["quantum"])
        elif policy == "MLFQ":
            run_for = min(run_for, state.mlfq_quanta[ready.queue_level] - ready.quantum_used)
```

**C. Explain the code:** When CPU is idle, time jumps to the next arrival or I/O return. The selected scheduling policy controls the next process.

**D. Why this approach:** An event-based simulator avoids stepping through every empty tick. **Alternative:** A tick-by-tick simulator is easier to picture, but may do more unnecessary work.

**E. If she asks — Does switching restart processes?** No. It changes scheduling order while preserving execution progress.

**F. Don’t say:** This is simulated CPU scheduling, not Linux kernel scheduling.

**G. Connected code:** `simulator/process.py → Process; autoscheduler/dynamic.py → _switch_policy()`

---

<a id="topic-5"></a>
## P0 · 5. Why MLFQ is our baseline

**A. What to say:** “MLFQ keeps multiple priority queues. CPU-heavy jobs move down after using their time slice, and long-waiting jobs can move up.”

**B. Code to show:** `simulator/engine.py` → `simulate.age_ready / MLFQ selection` (source lines 90–101; 168–243).

**Code chunk 1** — show these exact source lines:
```python
        if policy != "mlfq":
            return
        eligible = (item for item in ready if item.queue_level > 0
                    and current_time - item.aging_since >= (aging_threshold or 1))
        for item in sorted(eligible, key=lambda candidate: candidate.sequence):
            item.queue_level -= 1
            item.quantum_used = 0
            item.aging_since = current_time
```

**Code chunk 2** — show these exact source lines:
```python
                run_for = min(run_for, quantum or run_for)
            elif policy == "mlfq":
                level_quantum = (queue_quanta or ())[ready_process.queue_level]
                run_for = min(run_for, level_quantum - ready_process.quantum_used)
                if ready_process.queue_level > 0:
                    next_events = ([pending[0].arrival_time] if pending else [])
```

**C. Explain the code:** age_ready() promotes waiting jobs; the CPU quantum and queue level control how long a job runs.

**D. Why this approach:** MLFQ is a strong fixed baseline that adapts to CPU usage without requiring ML predictions. **Alternative:** Round Robin is simpler but gives every runnable job the same time slice.

**E. If she asks — What is tuned MLFQ?** The fixed version selected in development: queue quanta (1, 2, 4) and aging threshold 40.

**F. Don’t say:** Do not say MLFQ is ML or that aging guarantees no starvation.

**G. Connected code:** `scheduler/mlfq.py; autoscheduler/dynamic.py → _age_mlfq()`

---

<a id="topic-6"></a>
## P0 · 6. Where FCFS, RR, Priority, SJF and SRTF differ

**A. What to say:** “Each algorithm uses a different rule to select the next process: arrival order, queue order, priority, or CPU burst length.”

**B. Code to show:** `simulator/engine.py` → `simulate.take_ready` (source lines 103–137).

**Code chunk 1** — show these exact source lines:
```python
        if policy == "rr":
            index = min(range(len(ready)), key=lambda i: ready[i].sequence)
```

**Code chunk 2** — show these exact source lines:
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

**C. Explain the code:** take_ready() calculates a selection key for each scheduling policy, then removes the chosen ready process.

**D. Why this approach:** Different selection rules let us compare traditional algorithms fairly on the same workload. **Alternative:** A shared priority heap could scale better but is harder to inspect than these small lists.

**E. If she asks — Can Dynamic v5 choose SJF or SRTF?** No. They are oracle-style reference policies here, not part of the realistic dynamic action set.

**F. Don’t say:** This implementation’s SJF uses total declared burst_time, not the next CPU burst.

**G. Connected code:** `autoscheduler/evaluation.py → DEPLOYABLE_ALGORITHMS`

---

<a id="topic-7"></a>
## P0 · 7. What a Process object stores

**A. What to say:** “Each process has an ID, arrival time, CPU work and priority. It can also have multiple CPU bursts separated by I/O.”

**B. Code to show:** `simulator/process.py` → `Process / __post_init__` (source lines 28–60).

**Code chunk 1** — show these exact source lines:
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

**Code chunk 2** — show these exact source lines:
```python
        if any(burst <= 0 for burst in self.io_bursts):
            raise ValueError("I/O bursts must be positive")
        if len(self.io_bursts) != len(self.cpu_bursts) - 1:
            raise ValueError("I/O bursts must occur between CPU bursts")
        if sum(self.cpu_bursts) != self.burst_time:
            raise ValueError("burst_time must equal the sum of CPU bursts")
        self.remaining_time = self.cpu_bursts[0]
```

**C. Explain the code:** The class stores inputs and runtime values like remaining_time, start_time and completion_time. Validation rejects invalid burst lists.

**D. Why this approach:** One clear process structure makes it easier to reuse the same workload across schedulers. **Alternative:** Using only one CPU burst would be simpler, but could not demonstrate I/O blocking.

**E. If she asks — Is remaining_time total unfinished CPU?** No. It refers to the current CPU burst in this implementation.

**F. Don’t say:** Do not claim this class alone checks duplicate process IDs; the simulator does that.

**G. Connected code:** `simulator/engine.py; autoscheduler/dynamic.py → _new_state()`

---

<a id="topic-8"></a>
## P0 · 8. How waiting, response and score are calculated

**A. What to say:** “Response is arrival to first CPU execution. Turnaround is arrival to completion. Waiting excludes time spent running and doing I/O.”

**B. Code to show:** `simulator/simulator.py` → `compute_metrics` (source lines 69–85).

**Code chunk 1** — show these exact source lines:
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

**Code chunk 2** — show these exact source lines:
```python
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

**C. Explain the code:** The code computes the three values from each finished process. Another function combines normalized metrics into a weighted score.

**D. Why this approach:** We need numbers to compare policies instead of relying only on the animation. **Alternative:** A single metric would be simpler, but might hide poor performance in other areas.

**E. If she asks — Is a lower weighted score better?** Yes, within the same reference set; the score combines five normalized metrics.

**F. Don’t say:** The score is not classification accuracy. P95 response is checked separately.

**G. Connected code:** `autoscheduler/evaluation.py → score_result_against_reference()`

---

<a id="topic-9"></a>
## P0 · 9. Which fitted model the dashboard loads

**A. What to say:** “The demo loads the saved v5 cost-regression model. It verifies the file and its saved configuration before running the controller.”

**B. Code to show:** `dashboard/adapter.py` → `_original_v5 / _run_v5` (source lines 89–107).

**Code chunk 1** — show these exact source lines:
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

**C. Explain the code:** The loader checks the model path, SHA256 hash and feature schema, then gives the model to run_dynamic().

**D. Why this approach:** Checking the exact artifact avoids silently showing results from a different model. **Alternative:** Loading whichever model file is found first would be easier but less reliable.

**E. If she asks — Does the demo use our old classifier?** No. The active v5 route loads the regression model; classifiers are separate experiments.

**F. Don’t say:** Not every demo preset actually causes a policy switch.

**G. Connected code:** `autoscheduler/model.py → load_model(); tests/test_switching_demo.py`

---

<a id="topic-10"></a>
## P1 · 10. What our original Decision Tree Classifier did

**A. What to say:** “Our first ML approach learned to choose one scheduling policy for a whole workload. That is different from v5 changing policies during execution.”

**B. Code to show:** `autoscheduler/dataset.py` → `build_dataset / run_adaptive` (source lines 21–36).

**Code chunk 1** — show these exact source lines:
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

**C. Explain the code:** We simulated each workload with different policies, labeled the lowest-score result, then trained a classifier on workload statistics.

**D. Why this approach:** Direct classification was a simple starting point for ML scheduling. **Alternative:** Regression later gave us numerical cost differences for switching decisions.

**E. If she asks — What does 76% accuracy mean?** It is historical classifier label accuracy, not a 76% scheduling improvement.

**F. Don’t say:** The classifier is not combined with v5 regression during the current demo.

**G. Connected code:** `autoscheduler/model.py → train_model(); autoscheduler/adaptive.py → run_adaptive()`

---

<a id="topic-11"></a>
## P1 · 11. Where regression training targets come from

**A. What to say:** “During offline training, we try different scheduling actions on copied states, measure their outcomes and use score differences as targets.”

**B. Code to show:** `autoscheduler/dynamic.py` → `_counterfactual_label` (source lines 565–604).

**Code chunk 1** — show these exact source lines:
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
```

**Code chunk 2** — show these exact source lines:
```python
    baseline = score_result_against_reference(results[continuation], references)
    scores = {policy: score_result_against_reference(results[policy], references) - baseline for policy in policies}
    label = min(policies, key=lambda policy: (scores[policy], policies.index(policy)))
    if "No Switch" in scores and scores["No Switch"] <= scores[label] + 1e-12:
        label = "No Switch"
    elif active_policy in scores and scores[active_policy] <= scores[label] + 1e-12:
        label = active_policy
    return label, scores
```

**C. Explain the code:** The training code clones a state, tests an action for a limited interval, then finishes using MLFQ.

**D. Why this approach:** This teaches the regressor estimated action costs without retraining during the demo. **Alternative:** Online reinforcement learning would be different and more complex; we did not implement it here.

**E. If she asks — Does training know future work?** Offline simulation uses the full workload to create labels; live feature extraction does not.

**F. Don’t say:** Do not describe these targets as measured Linux scheduling outcomes.

**G. Connected code:** `autoscheduler/dynamic_training.py → build_training_data()`

---

<a id="topic-12"></a>
## P1 · 12. How we judged and selected models

**A. What to say:** “We did not select a model only because its predictions looked accurate. We also checked the actual schedules and whether response and safety metrics passed.”

**B. Code to show:** `autoscheduler/dynamic_training.py` → `validation_metrics` (source lines 105–120).

**Code chunk 1** — show these exact source lines:
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

**C. Explain the code:** The evaluation checks score, P95 response, starvation and controller latency against reference policies.

**D. Why this approach:** A scheduling model must be judged by what happens after its decisions, not just by prediction accuracy. **Alternative:** Choosing the highest-accuracy classifier alone could still produce poor scheduling.

**E. If she asks — Did v5 pass every final gate?** No. The saved final audit did not approve it over tuned MLFQ.

**F. Don’t say:** Do not claim Decision Tree was proven best across all models or datasets.

**G. Connected code:** `autoscheduler/dynamic_v5_experiment.py → run()`

---

<a id="topic-13"></a>
## P1 · 13. What the Azure workload data really is

**A. What to say:** “We used external Azure function invocation data to build test workloads. Exact CPU bursts and arrival milliseconds were reconstructed or approximated.”

**B. Code to show:** `AzureWorkloads/scripts/convert_workloads.py` → `reconstruct` (source lines 30–55).

**Code chunk 1** — show these exact source lines:
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

**C. Explain the code:** The code creates reproducible arrival times and converts the recorded average duration into a burst-time proxy.

**D. Why this approach:** External-source data gives a useful test beyond our synthetic training workloads. **Alternative:** Direct observed CPU traces would be more realistic but were not supplied by this Azure source.

**E. If she asks — Did we train v5 on Azure?** The original v5 was trained on synthetic workloads; Azure was used for external evaluation.

**F. Don’t say:** Do not call these real measured Linux CPU bursts or real scheduling timestamps.

**G. Connected code:** `AzureWorkloads/scripts/refine_workloads.py → sample_sources()`

---

<a id="topic-14"></a>
## P1 · 14. What the Azure evaluation actually showed

**A. What to say:** “On the completed Azure-derived cases, v5 reduced average waiting but had worse response time and overall weighted score than tuned MLFQ.”

**B. Code to show:** `autoscheduler/azure_generalization_report.py` → `summarize` (source lines 44–84).

**Code chunk 1** — show these exact source lines:
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

**C. Explain the code:** The report compares policies on the same workloads that successfully completed for all policies.

**D. Why this approach:** A fair comparison needs the same test cases and must report incomplete runs. **Alternative:** Comparing different completed subsets would be easier but misleading.

**E. If she asks — Did v5 beat tuned MLFQ?** Not overall on the reported completed Azure cohort; some individual metrics did improve.

**F. Don’t say:** Only 12 of 17 selected workloads completed for all policies. These are not all 510 workloads.

**G. Connected code:** `autoscheduler/azure_generalization_evaluation.py → evaluate()`

---

<a id="topic-15"></a>
## P1 · 15. Tests that prove particular behaviors

**A. What to say:** “We wrote tests for scheduling behavior, model inputs and switching. One test checks that changing unknown future work does not change the model features.”

**B. Code to show:** `tests/test_dynamic_contract.py` → `DynamicObservabilityTests` (source lines 29–50).

**Code chunk 1** — show these exact source lines:
```python
        # Finish a known two-tick burst and observe the subsequent I/O block.
        _dispatch(state, "Priority", ALGORITHMS["Priority RR"][1])
        observed = extract_dynamic_features(state)
        altered = copy.deepcopy(state)
        for ready in altered.ready:
            ready.process.remaining_time = 999
            ready.process.burst_time = 2000
```

**Code chunk 2** — show these exact source lines:
```python
            process.cpu_bursts = (777, 777)
            process.io_bursts = (999,)
        altered.pending = [Process("unseen", 10000, 99999, priority=99)]
        self.assertEqual(extract_dynamic_features(altered), observed)
```

**C. Explain the code:** The test changes hidden data after copying a state and checks that extracted features remain the same.

**D. Why this approach:** Small controlled tests can show exactly whether a particular rule works. **Alternative:** A full workload benchmark checks performance, but does not isolate one rule as clearly.

**E. If she asks — Have all tests been rerun now?** Not for the original guide; only small read-only checks were reported.

**F. Don’t say:** Never claim a fresh full-suite pass without running it.

**G. Connected code:** `tests/test_mlfq.py; tests/test_switching_demo.py`

---

<a id="topic-16"></a>
## P2 · 16. What the dashboard animation actually does

**A. What to say:** “Choosing a workload asks the backend to simulate it. Play and pause then move through the result that was already calculated.”

**B. Code to show:** `dashboard/web/src/Simulation.jsx` → `Simulation` (source lines 46–50).

**Code chunk 1** — show these exact source lines:
```jsx
export function Simulation({data,workload,setWorkload}) {
  const [algorithm,setAlgorithm]=useState('Round Robin'),[result,setResult]=useState(null),[error,setError]=useState(''),[tick,setTick]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[retry,setRetry]=useState(0);
  useEffect(()=>{ const abort=new AbortController(); setResult(null);setError('');setTick(0);setPlaying(false);api(`/api/simulation?workload=${encodeURIComponent(workload)}&algorithm=${encodeURIComponent(algorithm)}`,abort.signal).then(setResult).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>abort.abort(); },[workload,algorithm,retry]);
  useEffect(()=>{if(!playing||!result)return; if(tick>=result.metrics.makespan){setPlaying(false);return;} const timer=setTimeout(()=>setTick(t=>Math.min(t+1,result.metrics.makespan)),500/speed);return()=>clearTimeout(timer);},[playing,tick,speed,result]);
  const frame=result?.frames[tick],done=result&&tick===result.metrics.makespan;
```

**C. Explain the code:** React requests simulation data when inputs change. The playback timer advances through returned frames.

**D. Why this approach:** Keeping playback separate makes demonstrations repeatable. **Alternative:** Live streaming could update during scheduling, but would be a different implementation.

**E. If she asks — Does clicking Play start CPU scheduling?** No. It starts replaying the already computed simulation.

**F. Don’t say:** Do not call it a live operating-system scheduler.

**G. Connected code:** `dashboard/adapter.py → simulation(); dashboard/app.py → /api/simulation`

---

<a id="topic-17"></a>
## P2 · 17. Which dashboard results are saved

**A. What to say:** “The simulation page can calculate small workload results when requested. Research charts mostly display saved experiment data.”

**B. Code to show:** `dashboard/app.py` → `get_catalog / get_simulation` (source lines 25–43).

**Code chunk 1** — show these exact source lines:
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
```

**C. Explain the code:** The catalog API reads JSON files, while some frontend panels import saved JSON at build time.

**D. Why this approach:** This lets us show expensive research results without rerunning experiments in a review. **Alternative:** Live recomputation would be slower and may change results or require retraining.

**E. If she asks — Do research panels train models when opened?** No. They display recorded results.

**F. Don’t say:** Some UI text is stale: the source guide identifies misleading SJF and classifier-availability wording.

**G. Connected code:** `dashboard/adapter.py → catalog(); dashboard/web/src/RealSourceDynamic.jsx`

---

<a id="topic-18"></a>
## P2 · 18. What our Linux trace and CLI code does

**A. What to say:** “We also have commands for experiments and Linux trace preparation, but our current ML scheduler runs in a simulator.”

**B. Code to show:** `autoscheduler/real_dataset.py` → `build_development_action_rows; main.main` (source lines 46–63; 136–148).

**Code chunk 1** — show these exact source lines:
```python
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

**C. Explain the code:** The CLI launches selected commands; replay code creates offline policy-comparison rows from traces.

**D. Why this approach:** Offline tools let us study scheduling without changing the actual operating system. **Alternative:** Kernel integration would be more realistic but needs separate implementation and validation.

**E. If she asks — Is the ML policy installed in Linux?** No. There is no validated kernel-level deployment in the reviewed path.

**F. Don’t say:** Do not claim real-time Linux CPU control or multicore validation.

**G. Connected code:** `autoscheduler/cli.py → main(); autoscheduler/real_features.py`

---

## Quick answers to likely faculty questions

| Faculty question | Short answer |
|---|---|
| **What are the 19 features?** | Queue counts, CPU history, priorities, waiting, recent arrivals/I/O, active policy, dwell time and first-service waits. |
| **Does the fitted v5 tree use all 19?** | It accepts 19, but its actual splits use only three: `completed_burst_variance`, `ready_count`, `arrival_quiet_ticks`. |
| **What does regression predict?** | Six scheduling-cost differences, not a process ID or response-time number. |
| **Who performs switching?** | The dynamic controller, after checking the model suggestion and safety rules. |
| **Why use regression instead of classification?** | Regression gives numerical cost differences, so we can compare whether switching may be worth it. |
| **Why did we build the classifier earlier?** | It was an earlier experiment to choose one policy per workload. It is separate from v5. |
| **Is v5 a hybrid classifier + regressor?** | No. The demo uses the fitted cost-regression tree. |
| **What is tuned MLFQ?** | Fixed MLFQ with time quanta `(1, 2, 4)` and aging `40`, selected from development comparisons. |
| **What makes scheduling dynamic?** | The active algorithm can change while the workload is still running. |
| **Does the model learn during the demo?** | No. Training is offline; the demo uses saved-model inference. |
| **Does every demo workload switch?** | No. Some stay on MLFQ; the selected illustrative case switches twice. |
| **How are the metrics computed?** | From each process’s arrival, first execution, final completion, total CPU and I/O time. |
| **Do the Azure results prove ML is better?** | No. V5 reduced waiting on completed cases but worsened response and weighted score overall. |
| **Is this installed in the OS?** | No. It is a CPU scheduling simulator and an offline research system. |
| **Are the dashboard charts live training?** | No. Tiny simulation results are computed on request; research panels mostly read saved results. |

## The exact 19 features, without long explanations

If asked, **say the categories first**; list individual names only if she requests them.

| Category | Feature names |
|---|---|
| Queue | `ready_count`, `blocked_count` |
| Finished CPU bursts | `completed_burst_mean`, `completed_burst_variance` |
| CPU already received | `observed_service_mean`, `observed_service_variance` |
| Priority | `priority_mean` |
| Ready waiting | `ready_wait_mean`, `ready_wait_max`, `ready_wait_p50`, `ready_wait_p95` |
| Recent activity | `recent_arrivals`, `io_returns`, `io_return_ratio`, `arrival_quiet_ticks` |
| Active scheduler | `active_policy_index`, `dwell_remaining_ticks` |
| First CPU service | `first_service_ready_count`, `first_service_wait_max` |

**Simplest answer:** “They tell us how busy the CPU queues are, how jobs have behaved so far, how long they are waiting, and which scheduler is running.”

## Results to remember — only when asked

| Study | V5 cost tree | Tuned MLFQ | Safe conclusion |
|---|---:|---:|---|
| Synthetic audit, mean weighted score ↓ | 0.1359 | 0.1676 | V5 had a better mean score, but did not pass the full acceptance test. |
| Synthetic audit, mean workload P95 ↓ | 7.6450 | 7.4873 | Tuned MLFQ had slightly better response tails. |
| Azure-derived completed cases, score ↓ | 0.1320 | 0.0761 | Tuned MLFQ was better overall. |
| Azure-derived completed cases, mean P95 response ↓ | 2197.91 ms | 2.91 ms | V5 performed worse for first-response tails. |

**Scope:** Azure table covers **12 workloads completed by all policies out of 17 selected**; it is not a claim about all 510 available workloads. Original v5 and Azure-retrained v5 are different experiments.

## Six things NOT to claim

1. “Our model always beats MLFQ.” — It does not.
2. “Classifier and regression run together.” — Not in the active v5 demo.
3. “We schedule processes inside Linux.” — The reviewed project is a simulator.
4. “The dashboard trains the model live.” — Training is offline.
5. “Azure supplied exact CPU bursts.” — CPU burst lengths are proxies based on duration summaries.
6. “Every ML prediction creates a switch.” — Safety and timing rules can reject it.

## Two-minute revision route

1. First: topics **1, 2, 3** — the model, switching and 19 features.
2. Then: topics **4, 5, 8, 9** — simulator, MLFQ, metrics and loaded model.
3. If faculty focuses on research: topics **10–14** — classifier, training, gates and Azure findings.
4. If faculty opens frontend: topics **16–17** — simulation playback and saved results.

## Codex prompt — use with your Caveman explanation style

Copy the prompt below into Codex in VS Code while the AutoScheduler repository is open. It asks for an even simpler version **without changing the code**.

```text
Create a simple faculty viva study guide from the CURRENT AutoScheduler code and the existing detailed faculty review guide.
Follow the existing priority order (P0, then P1, then P2), not the order of presentation.
Use the writing style I call CAVEMAN: extremely simple, short English, but technically correct. Do not use childish slang.

Create exactly one Markdown file: docs/FACULTY_CAVEMAN_QUICK_GUIDE.md
Only that Markdown file may be added or changed. Do NOT modify project code, tests, models, outputs or the dashboard.
Do NOT retrain, run long tests, install dependencies or execute heavy experiments.

For each important code topic, keep this SAME format:
A. WHAT TO SAY: maximum 2 short spoken sentences (about 10–15 seconds).
B. WHAT CODE TO SHOW: exact file, function and 1 or 2 short VERBATIM source snippets of about 4–12 lines.
C. EXPLAIN THE CODE: maximum 2 short sentences in basic English.
D. WHY THIS APPROACH: 1 sentence; ALTERNATIVE: 1 sentence explaining the tradeoff.
E. IF FACULTY ASKS: one likely question with a 1-sentence answer.
F. DO NOT SAY: 1 clear warning about claims not supported by code.
G. CONNECTION: exact next function or file, no long tracing.

Cover these FIRST: v5 cost regression, dynamic switching and guards, the 19 features, simulator dispatch, MLFQ, metrics and model loading.
Then cover classifier research, training labels, evaluation gates, Azure trace reconstruction, Azure results and tests.
Keep frontend and CLI details last.

At the top make a ranked 1-page quick navigation table.
At the end add: 20 common faculty questions answered in 1 sentence each; list of all 19 feature names grouped by purpose;
a 30-second project overview; six unsafe claims to avoid; and the 10 source code locations I should practice opening.

Use current source code, not just dashboard labels or README. Every snippet must be copied exactly from a real source file.
Never invent implementation details or historical developer reasoning; mark unknowns as UNKNOWN.
Clearly separate old classifier from live v5 regression. Do not call them a hybrid.
Do not claim v5 beats tuned MLFQ overall on the completed Azure evaluation.
Never explain beyond what the faculty question needs; give the smallest correct answer.

The guide must be easy to read in VS Code Markdown Preview. Use tight paragraphs, clear headings and small code blocks.
Write the file and then print its location plus the P0/P1/P2 topic counts.
```

---

*This is a short revision version of the supplied technical audit. For detailed evidence, model artifacts, complete code traces and full evaluation limitations, refer to the original AutoScheduler Faculty Code Review Guide.*

---

<a id="topic-19"></a>
## P1 · 19. What our synthetic training data was based on, how we generated it, and where it is

**A. What to say:** “We designed synthetic workloads to cover different scheduling situations, such as continuous arrivals, low load, long I/O and changing job mixes. We generated them with fixed random seeds, simulated the scheduling actions, and trained the model on the observed features and resulting action costs.”

**B. Code to show:** `autoscheduler/development_workloads.py` → `generate_development_workload_v4()` (source lines 68–86); `autoscheduler/dynamic.py` → `build_dynamic_dataset()` (lines 677–708); `autoscheduler/dynamic_v5_experiment.py` → `run()` (lines 179–181).

**Code chunk 1** — the generator used by original v5 (source lines 68–74):
```python
def generate_development_workload_v4(seed: int, family: str | None = None,
                                     process_count: int | None = None) -> DevelopmentWorkload:
    """Balanced families, broader counts and unpredictable arrivals; no outcome filtering."""
    rng = random.Random(seed)
    family = family or rng.choice(DEV_FAMILIES)
    count = process_count if process_count is not None else rng.choice((3, 6, 12, 24, 48))
    workload = generate_development_workload(seed, family, count)
```

**Code chunk 2** — generate the training features and targets (source lines 692–698):
```python
        references = compare_algorithms(workload.processes, rr_config)
        for epoch, (state, active, dwell) in enumerate(_training_states(
            workload.processes, config, rr_config, behavior, workload.seed, behavior_model,
        )):
            label, scores = _counterfactual_label(state, config.epoch_ticks, rr_config, dynamic_action_names(config), active, dwell,
                                                 config=config, references=references)
            row = extract_dynamic_features(state, active, dwell)
```

**Code chunk 3** — save the generated table (source lines 179–181):
```python
    print("Building grouped training labels and train-only pilot occupancy", flush=True)
    rows, occupancy = build_training_data(144, train_seed, config, artifacts / "split.json", development="v4")
    save_dataset(rows, artifacts / "training.csv")
```

**C. Explain the code:** We generate process descriptions first, then run simulations to turn them into labeled decision examples. The original v5 experiment uses the generator named `v4`; that is the workload-generator version, not the loaded model version.

**What was the basis?** These are manually specified scheduling scenarios and numeric ranges in the source, rather than distributions fitted to Azure observations. They let us test different queue pressures, CPU demands and I/O patterns; the code does not establish that their frequencies match real desktop workloads.

| Family | What we generated | Scheduling situation covered |
|---|---|---|
| `cohort_mix` | Batch, interactive and I/O groups arriving in phases | Different job types competing |
| `sustained_arrivals` | Continuing arrivals; the v4 generator varies gaps using exponential draws or a fixed set of gap values | Ongoing and irregular queue pressure |
| `low_load` | Short jobs arriving 80 ticks apart | Little CPU competition |
| `long_io` | Multiple CPU bursts with long I/O gaps; a sparse variant has CPU bursts `(20, 20, 20)` and I/O `(100, 100)` | Blocking and returning jobs |
| `repeated_changes` | Several phases of batch, interactive, CPU and I/O work | Workload conditions changing during a run |
| `homogeneous_batch` | Same-length CPU-only jobs arriving together | A simple uniform control case |

The exact rules are in `autoscheduler/development_workloads.py:34–86`. For example, interactive CPU bursts are short, CPU-heavy bursts can be 30–60 ticks, and long-I/O gaps are normally 50–150 ticks. These are simulator settings, not measured milliseconds.

**How did these become training rows?**

1. Generate workloads using reproducible seeds and process counts of **3, 6, 12, 24 or 48**. Original v5 starts from **144 development traces**, with training-generation seed **9701**.
2. Collect execution states under different behavior policies and exploration. A training-only pilot rollout adds more states without adding validation/test trace groups to training.
3. Extract the **19 observed-state features** at each sampled decision state. During offline labeling, copied states try feasible actions and then continue with MLFQ; their weighted-score differences supply the six regression targets.
4. Save the table. One row is a **decision state**, not one process or one complete workload. The original v5 CSV has **7,282 rows across its internal splits**, with **100 training, 22 validation and 22 test trace groups**. All states from a trace stay in the same group split.

**Where is it located?** Paths below are relative to `/home/bob_the_bob/AutoScheduler-SL-CPU-Scheduler/`; all listed files were verified to exist.

| What to open | Exact location |
|---|---|
| Original v5 synthetic training table — features, labels and `score_*` cost columns | `artifacts/dynamic_v5_20261019/training.csv` |
| Trace-group split manifest | `artifacts/dynamic_v5_20261019/split.json` |
| Saved original v5 regression model | `artifacts/dynamic_v5_20261019/policy_cost/model.joblib` |
| Training report — row counts, features and internal split results | `results/dynamic_v5_20261019/policy_cost_training.json` |
| Generation protocol — seeds, trace counts and experiment settings | `results/dynamic_v5_20261019/protocol.json` |
| Workload generation rules | `autoscheduler/development_workloads.py` |
| State sampling and target generation | `autoscheduler/dynamic.py` |
| Grouping and training-only pilot augmentation | `autoscheduler/dynamic_training.py` |

**Older classifier — separate dataset:** Its saved table is `results/six_policy/training.csv`, with **2,500 workload rows**. `autoscheduler/workloads.py:12–65` defines five profiles: `interactive`, `batch`, `cpu_intensive`, `io_intensive`, and `mixed`. Seeded draws choose arrival gaps, CPU/I/O bursts and priorities from the profile settings; `autoscheduler/dataset.py:21–36` simulates policies and labels the lowest weighted-score result. This is one row per whole workload, unlike the v5 decision-state table.

**D. Why this approach:** Controlled, seeded workloads make scheduling cases repeatable and help expose policy tradeoffs. **Alternative:** Measured traces can provide stronger external evidence, but require trustworthy observations and separate validation; synthetic results alone cannot prove real-world superiority.

**E. If she asks — Was original v5 trained on Azure data?** No. Original v5 used synthetic development data; the later Azure-retrained v5 is a separate experiment and artifact.

**F. Don’t say:** Do not say we “trained the data,” copied these synthetic workloads from Azure, or proved that our chosen ranges represent real CPU traffic. We generated the data and trained the model; no synthetic result selects the final real-data model.

**G. Connected code:** `autoscheduler/dynamic_v5_experiment.py → run()` calls `build_training_data()`, which calls `build_dynamic_dataset()`; the generated rows are saved by `autoscheduler/dataset.py → save_dataset()` and passed to `autoscheduler/model.py → train_model()`.

---

<a id="topic-20"></a>
## P1 · 20. Where the Azure datasets are, what we reconstructed, and what the results showed

**A. What to say:** “We used Microsoft Azure Functions 2019 observations to construct external-source simulator workloads. They tested whether our synthetic-trained v5 model generalized: it reduced waiting on the completed cases, but worsened response tails and weighted score, so tuned MLFQ remained recommended.”

**B. Code to show:** `AzureWorkloads/scripts/convert_workloads.py` → `reconstruct()` (source lines 21–56); `autoscheduler/azure_generalization.py` → `load()` (lines 53–57); `autoscheduler/azure_generalization_report.py` → `summarize()` (lines 44–58).

**Code chunk 1** — reconstruct process inputs from source summaries (source lines 45–55):
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

**Code chunk 2** — load existing workloads and the original fitted model (source lines 53–57):
```python
def load():
    workloads=json.loads(DATA.read_text())['workloads']
    metadata=load_model_metadata(MODEL);config=DynamicRouterConfig(**metadata['dynamic_config'])
    model=load_model(MODEL,DYNAMIC_FEATURE_NAMES,expected_dynamic_config=config)
    return workloads,model,config
```

Here `DATA` is `AzureWorkloads/cleaned/evaluation_workloads.json` and `MODEL` is `artifacts/dynamic_v5_20261019/policy_cost/model.joblib` (`autoscheduler/azure_generalization.py:21–23`). Loading and evaluating original v5 does **not** retrain it on Azure.

**Code chunk 3** — select the same completed workloads for every policy's reported mean (source lines 44–49):
```python
    policies = list(dict.fromkeys(r['policy'] for r in rows))
    by_id = defaultdict(dict)
    for row in rows:
        by_id[row['workload_id']][row['policy']] = row
    common = [wid for wid, values in by_id.items()
              if len(values) == len(policies) and all(v['status'] == 'COMPLETE' for v in values.values())]
```

**C. Explain the code:** The converter creates reproducible simulator jobs from aggregate Azure observations. The evaluation loads these jobs and a saved model, runs scheduling policies, and reports matched completed-workload results while retaining failures.

**What did Azure actually provide?** Per-function invocation counts in one-minute bins, anonymized owner/application/function identifiers, and duration summaries including a daily mean. These are serverless workload observations, not a trace of OS process arrivals, ready queues or CPU/I/O execution.

**What did we reconstruct exactly?**

| Simulator input | How we obtained it | Important limitation |
|---|---|---|
| One simulated process per selected invocation | Expand selected counts into jobs; assign a PID containing source row, minute and invocation ordinal | A PID is our bookkeeping label, not an observed Azure OS PID |
| `arrival_time` | Generate reproducible millisecond offsets within the source minute, assuming uniform arrivals, then express time relative to the workload start | Exact invocation timestamps were unavailable; the positions within each minute are reconstructed |
| `burst_time` | Use `ceil(positive daily Average)` in milliseconds for each selected invocation of that function/day | Daily wall-clock mean is a CPU-demand proxy; actual per-invocation CPU bursts and variation are unknown |
| `priority` | Assign neutral priority `0` | Azure did not supply scheduler priorities |
| CPU/I/O phases | Supply the single CPU-demand proxy; no I/O burst sequence is added | We cannot recover CPU/I/O blocking behavior from these summaries |
| Bounded high-load workloads | Sample source-minute counts without replacement, with saved quotas/fractions; also create short contiguous reconstructed-rank peak snapshots | Full-hour thinning reduces arrival intensity; snapshots depend on the within-minute assumption |

The arrival reconstruction branches are in `convert_workloads.py:30–44`; sampling is in `refine_workloads.py:42–75`. **One tick = one millisecond for this Azure mapping.** Positive published means were already integers, so the saved rounding analysis found zero additional ceiling error; that does not recover unknown upstream quantization or individual invocation durations.

**Why did we refine the selection?** The old 2,000-process cap rejected entire busy function-hours containing **94.37% of recorded invocations**. We retained the 286 original control workloads and added bounded high-load, mixed-function and local-rate samples, giving **510 workloads and 520,408 process entries**, with at most **2,000 processes per workload**. This improves high-load eligibility; it does not replay all Azure traffic or produce a population-weighted sample.

**Where is everything located?** Paths are relative to `/home/bob_the_bob/AutoScheduler-SL-CPU-Scheduler/`; all listed paths were verified locally.

| What to open | Exact location |
|---|---|
| Original Azure archive | `AzureWorkloads/raw/azurefunctions_dataset2019_azurefunctions-dataset2019.tar.xz` |
| Extracted source CSVs | `AzureWorkloads/extracted/` — e.g. `invocations_per_function_md.anon.d09.csv` and `function_durations_percentiles.anon.d07.csv` |
| Cleaned invocation observations | `AzureWorkloads/cleaned/azure_cleaned.csv` |
| Cleaned duration observations | `AzureWorkloads/cleaned/azure_durations_cleaned.csv` |
| Reconstructed jobs with provenance | `AzureWorkloads/cleaned/azure_scheduler_jobs.csv` |
| Ready-to-load simulator workloads | `AzureWorkloads/cleaned/evaluation_workloads.json` |
| Source attribution, units, assumptions and checksums | `AzureWorkloads/metadata.json` |
| Dataset statistics and reconstruction quality | `AzureWorkloads/reports/descriptive_statistics.json`; `AzureWorkloads/reports/data_quality_report.md` |
| Selected Azure evaluation workloads and grouping rules | `results/dynamic_azure_generalization/selection_manifest.json` |
| Per-workload, per-policy outcomes and retained timeouts | `results/dynamic_azure_generalization/baseline_rows.json` |
| Recorded decisions and switching diagnostics | `results/dynamic_azure_generalization/baseline_decisions.json` |
| Original v5 Azure evaluation summary and explanation | `results/dynamic_azure_generalization/summary.json`; `results/dynamic_azure_generalization/REPORT.md` |
| Separate Azure-retrained decision-cost data and model | `artifacts/dynamic_v5_azure_retrained/decision_costs.json`; `artifacts/dynamic_v5_azure_retrained/model.joblib` |
| Separate Azure-retrained results | `results/dynamic_v5_azure_retrained_20261020/results.json` |

**What were the results?** The original-v5 evaluation selected **17 workloads**. **12 workloads containing 3,135 processes completed under all seven policies**; **8 individual policy attempts timed out** across the selected suite. The means below use those same 12 completed workloads, not all 510 available workloads.

| Metric — lower is better | Original Dynamic v5 | Tuned MLFQ `(1, 2, 4)`, aging `40` | What it showed |
|---|---:|---:|---|
| Weighted score | 0.132043 | 0.076082 | MLFQ better on the composite objective |
| Average waiting, ms | 16,304.783 | 32,262.493 | V5 lower waiting |
| Average first response, ms | 991.355 | 0.302 | MLFQ much more responsive |
| Mean workload P95 first response, ms | 2,197.908 | 2.9125 | V5 worse response tails |
| Average turnaround, ms | 20,058.313 | 36,016.023 | V5 lower turnaround |

These values were checked against saved `baseline_rows.json`; they are simulator outcomes, not measured Azure production latency. P95 here means the **mean of each workload's P95**, not a percentile pooled across all processes.

**What did this establish?** It demonstrated that the existing pipeline can convert external-source summaries into controlled simulator comparisons and exposed a generalization limitation: lower waiting did not translate into better overall scheduling under the chosen objective and safety criteria. Original v5 failed the weighted-score and response-tail acceptance gates, so **tuned static MLFQ remained recommended**; this did not establish population-wide superiority, untouched-holdout improvement, or real-kernel performance.

**What about Azure-retrained v5?** That was a **separate six-workload development experiment**, not the 12-workload comparison above. Its weighted score was **0.027529**, identical to tuned MLFQ, and both had zero mean P95 first response on that cohort. The retrained controller made **two accepted transitions**, but established **no strict scheduling improvement over MLFQ**; it was not promoted and the final holdout was not evaluated. Do not compare its score directly with the differently selected original-v5 cohort.

**D. Why this approach:** External-source workloads test behavior outside our scripted synthetic families while keeping comparisons reproducible. **Alternative:** Complete timestamped CPU/I/O traces would require fewer reconstruction assumptions, but Azure's aggregate source does not contain that information.

**E. If she asks — Did the Azure results prove ML is better than MLFQ?** No: original v5 improved waiting but worsened response tails and weighted score on completed cases; the separate retrained model matched MLFQ rather than beating it.

**F. Don’t say:** Do not call these reconstructed jobs observed Linux processes, use wall-clock means as proven CPU bursts, claim all 510 workloads were evaluated, or hide the timeouts. Azure observations are real; the process timing model and scheduling outcomes are reconstructed and simulated.

**G. Connected code:** `AzureWorkloads/scripts/convert_workloads.py → reconstruct()` and `refine_workloads.py` build the workload inputs; `autoscheduler/azure_generalization.py → load()` loads them; `azure_generalization_evaluation.py → evaluate()` runs policies; `azure_generalization_report.py → summarize()` aggregates saved outcomes.

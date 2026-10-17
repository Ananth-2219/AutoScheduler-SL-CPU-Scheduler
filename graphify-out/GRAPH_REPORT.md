# Graph Report - AutoScheduler-SL-CPU-Scheduler  (2026-10-17)

## Corpus Check
- 103 files · ~88,895 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 747 nodes · 1683 edges · 61 communities (44 shown, 15 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 100 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1ec3b1bf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- test_fairness.py
- evaluation.py
- Process
- generate_workload
- dynamic.py
- benefit.py
- cli.py
- srtf
- AutoScheduler Realistic ML Validation Tasks
- What You Must Do When Invoked
- extract_features_at
- read_traces
- load_real_config
- AutoScheduler: Workload-Adaptive CPU Scheduling Simulator
- test_srtf.py
- Design
- Implementation Plan: Realistic ML Validation for AutoScheduler
- graphify reference: extra exports and benchmark
- LinuxPilotTests
- Phase 1 — Basic CPU Scheduling Engine
- Fairness Metrics Post-Test Report
- AutoScheduler Five-Policy Consistency Experiment
- AutoScheduler Handoff
- AutoScheduler Agent Guide
- graphify reference: query, path, explain
- AutoScheduler Priority-RR Experiment
- Phase 6: Run the Cross-Model Bake-Off
- Phase 3: Capture Local Linux Scheduler Traces
- Checkpoints
- Phase 0: Freeze the Scientific Contract
- Phase 1: Define the Real Trace Contract
- Phase 2: Import Public Production Traces
- Phase 4: Validate Trace Replay and Generator Calibration
- Phase 5: Build Observed-State Decision Data
- Phase 7: Evaluate Generalization on a Locked Real Test Set
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- Phase 8: Implement a Minimal `sched_ext` Pilot
- Phase 9: Reproducibility and Research Report
- CliTests
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- autoscheduler/__init__.py
- CLAUDE.md
- .claude/CLAUDE.md
- extraction-spec.md
- REAL_DATA_POLICY.md
- DemoTests
- LinuxCollectorTests
- capture_linux_trace.sh
- TestSrtfTieBreaking
- FirefoxProbeTests
- run_firefox_probe.sh
- TestSrtfPreemption
- TestSrtfIdleCpu
- capture_linux_pilot.sh
- run_wakeup_probe.py

## God Nodes (most connected - your core abstractions)
1. `Process` - 115 edges
2. `generate_workload()` - 36 edges
3. `srtf()` - 35 edges
4. `run_simulation()` - 31 edges
5. `simulate()` - 25 edges
6. `compare_algorithms()` - 24 edges
7. `BenefitConfig` - 22 edges
8. `SimulationResult` - 22 edges
9. `build_parser()` - 21 edges
10. `run_dynamic()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `AdaptiveResult` --uses--> `SimulationResult`  [INFERRED]
  autoscheduler/adaptive.py → simulator/simulator.py
- `run_adaptive()` --uses--> `Process`  [INFERRED]
  autoscheduler/adaptive.py → simulator/process.py
- `_observe()` --uses--> `Process`  [INFERRED]
  autoscheduler/benefit.py → simulator/process.py
- `run_fixed_hybrid()` --uses--> `Process`  [INFERRED]
  autoscheduler/benefit.py → simulator/process.py
- `run_benefit()` --uses--> `Process`  [INFERRED]
  autoscheduler/benefit.py → simulator/process.py

## Import Cycles
- None detected.

## Communities (61 total, 15 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.20
Nodes (11): demo(), main(), make_processes(), print_gantt(), print_result(), main.py ------- AutoScheduler: Self-Learning CPU Scheduling Algorithm Phase 1 —…, Return a fresh list of processes for each algorithm run., Print a text Gantt chart. Example output: | P1 | P2 | P4 | P3 | 0 5 8 10 18 (+3 more)

### Community 1 - "test_fairness.py"
Cohesion: 0.28
Nodes (8): aggregate_fairness(), _mean_or_none(), Report-only fairness metrics for completed process samples., Aggregate pooled process fairness metrics without affecting scheduler scores., ProcessMetrics, Per-process scheduling metrics., FairnessTests, metric()

### Community 2 - "evaluation.py"
Cohesion: 0.18
Nodes (14): Static scheduler comparison and oracle labeling., scheduler/fcfs.py ----------------- First Come First Serve (FCFS) — non-…, Three-level Multi-Level Feedback Queue scheduler., scheduler/priority.py --------------------- Non-preemptive Priority Scheduling.…, Preemptive priority scheduling with aging and an I/O-return boost., scheduler/round_robin.py ------------------------ Round Robin (RR) — preemptive…, scheduler/sjf.py ---------------- Shortest Job First (SJF) — non-preemptive…, Shortest Remaining Time First (preemptive, current CPU burst). (+6 more)

### Community 3 - "Process"
Cohesion: 0.17
Nodes (9): mlfq(), Run fixed MLFQ with top-queue admission, feedback, and aging., Process, Represents a single process in the CPU scheduling simulation. Attributes: pid :…, Re-initialise mutable scheduling fields so the same Process object can be…, compute_metrics(), simulator/simulator.py ---------------------- Common simulation layer: computes…, Derive per-process metrics from a list of scheduled (completed) processes.… (+1 more)

### Community 4 - "generate_workload"
Cohesion: 0.06
Nodes (41): AdaptiveResult, Adaptive algorithm selection and execution., run_adaptive(), select_scheduler(), build_dataset(), Oracle-labeled dataset generation., compare_algorithms(), oracle_label() (+33 more)

### Community 6 - "dynamic.py"
Cohesion: 0.12
Nodes (34): _dynamic_train(), build_dynamic_dataset(), _counterfactual_label(), _dispatch(), DynamicResult, DynamicRouterConfig, DynamicWorkload, evaluate_dynamic() (+26 more)

### Community 7 - "benefit.py"
Cohesion: 0.11
Nodes (37): _benefit_row(), BenefitConfig, BenefitResult, _complete(), evaluate_benefit(), extract_observed_features(), _full_rr(), _observe() (+29 more)

### Community 8 - "cli.py"
Cohesion: 0.08
Nodes (49): ArgumentParser, load_benefit_model(), _plot_setup(), Path, save_benefit_evaluation(), save_benefit_latency(), _benefit_evaluate(), _benefit_latency() (+41 more)

### Community 9 - "srtf"
Cohesion: 0.09
Nodes (18): fcfs(), Run the FCFS scheduling algorithm. Parameters ---------- processes :…, priority_round_robin(), Run Priority Round Robin; lower priority numbers run first., Run preemptive SRTF; arrivals and I/O completions can interrupt a burst., srtf(), Execute a scheduling algorithm and return a SimulationResult. Parameters…, run_simulation() (+10 more)

### Community 10 - "AutoScheduler Realistic ML Validation Tasks"
Cohesion: 0.06
Nodes (33): AutoScheduler Realistic ML Validation Tasks, Checkpoint A, Checkpoint B, Checkpoint C, Checkpoint D, Checkpoint E: Complete, Phase 0: Scientific Contract, Phase 1: Trace Contract (+25 more)

### Community 11 - "What You Must Do When Invoked"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 12 - "extract_features_at"
Cohesion: 0.21
Nodes (14): _real_features(), _busy_fraction(), extract_feature_rows(), extract_features_at(), _mean(), _p95(), Any, Path (+6 more)

### Community 13 - "read_traces"
Cohesion: 0.15
Nodes (15): _event(), import_trace_files(), import_trace_report(), Any, Path, Import trace-cmd scheduler reports into the canonical observed trace format., _record(), Any (+7 more)

### Community 14 - "load_real_config"
Cohesion: 0.28
Nodes (9): _real_config(), config_hash(), load_real_config(), Any, Path, Frozen contract for the real Linux desktop ML experiment., stamp_summary(), validate_real_config() (+1 more)

### Community 15 - "AutoScheduler: Workload-Adaptive CPU Scheduling Simulator"
Cohesion: 0.12
Nodes (16): Architecture, AutoScheduler: Workload-Adaptive CPU Scheduling Simulator, Commands, Dynamic Routing Experiment, Evaluation, Features, Limitations, Model Inputs (+8 more)

### Community 16 - "test_srtf.py"
Cohesion: 0.15
Nodes (8): priority_scheduling(), Run the non-preemptive Priority scheduling algorithm. Parameters ----------…, Run the non-preemptive SJF scheduling algorithm. Parameters ----------…, sjf(), tests/test_srtf.py ------------------ Unit tests for the SRTF (Shortest…, Smoke-test the existing algorithms to confirm the SRTF addition has not altered…, SRTF must produce a different timeline than SJF for this workload., TestExistingSchedulersUnaffected

### Community 17 - "Design"
Cohesion: 0.18
Nodes (10): Accessibility, Aesthetic direction, Color, Copy, Design, Dials, Interaction, Last updated (+2 more)

### Community 18 - "Implementation Plan: Realistic ML Validation for AutoScheduler"
Cohesion: 0.20
Nodes (9): Architecture Decisions, CLI Target, Current Baseline, Definition of Done, Dependency Graph, Implementation Plan: Realistic ML Validation for AutoScheduler, Overview, Primary References (+1 more)

### Community 19 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 21 - "Phase 1 — Basic CPU Scheduling Engine"
Cohesion: 0.25
Nodes (7): Algorithms Implemented, AutoScheduler: Self-Learning CPU Scheduling Algorithm, Metrics Reported, Phase 1 — Basic CPU Scheduling Engine, Project Structure, Quick Start, Scheduling Conventions

### Community 22 - "Fairness Metrics Post-Test Report"
Cohesion: 0.25
Nodes (7): Conclusion, Deterministic Checks, Fairness Metrics Post-Test Report, New Measurements, Results, Scope, What Changed in Interpretation

### Community 23 - "AutoScheduler Five-Policy Consistency Experiment"
Cohesion: 0.25
Nodes (7): AutoScheduler Five-Policy Consistency Experiment, Conclusion, Decision Latency, Held-Out Results, Limitations, Methodology, Training Results

### Community 24 - "AutoScheduler Handoff"
Cohesion: 0.29
Nodes (6): AutoScheduler Handoff, Current State, Recommended Next Work, Suggested Skills, Verified Experiment Result, Workspace Notes

### Community 25 - "AutoScheduler Agent Guide"
Cohesion: 0.33
Nodes (5): AutoScheduler Agent Guide, Change rules, Commands, Project, Research boundaries

### Community 26 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 27 - "AutoScheduler Priority-RR Experiment"
Cohesion: 0.33
Nodes (5): AutoScheduler Priority-RR Experiment, Conclusion, Method, Results, Setup

### Community 28 - "Phase 6: Run the Cross-Model Bake-Off"
Cohesion: 0.33
Nodes (6): Candidate models, Exit gate, Fair tuning, Goal, Phase 6: Run the Cross-Model Bake-Off, Reports

### Community 29 - "Phase 3: Capture Local Linux Scheduler Traces"
Cohesion: 0.33
Nodes (6): Capture method, Exit gate, Goal, Phase 3: Capture Local Linux Scheduler Traces, Repetition protocol, Workload suite

### Community 30 - "Checkpoints"
Cohesion: 0.33
Nodes (6): Checkpoint A: After Phases 0-2, Checkpoint B: After Phases 3-4, Checkpoint C: After Phases 5-6, Checkpoint D: After Phase 7, Checkpoint E: After Phases 8-9, Checkpoints

### Community 31 - "Phase 0: Freeze the Scientific Contract"
Cohesion: 0.40
Nodes (5): Decisions to freeze, Deliverables, Exit gate, Goal, Phase 0: Freeze the Scientific Contract

### Community 32 - "Phase 1: Define the Real Trace Contract"
Cohesion: 0.40
Nodes (5): Event vocabulary, Exit gate, Goal, Phase 1: Define the Real Trace Contract, Tables

### Community 33 - "Phase 2: Import Public Production Traces"
Cohesion: 0.40
Nodes (5): Exit gate, First adapters, Goal, Phase 2: Import Public Production Traces, Storage policy

### Community 34 - "Phase 4: Validate Trace Replay and Generator Calibration"
Cohesion: 0.40
Nodes (5): Exit gate, Generator calibration, Goal, Phase 4: Validate Trace Replay and Generator Calibration, Replay validation

### Community 35 - "Phase 5: Build Observed-State Decision Data"
Cohesion: 0.40
Nodes (5): Exit gate, Feature rules, Goal, Label strategy, Phase 5: Build Observed-State Decision Data

### Community 36 - "Phase 7: Evaluate Generalization on a Locked Real Test Set"
Cohesion: 0.40
Nodes (5): Final ML acceptance gate, Goal, Phase 7: Evaluate Generalization on a Locked Real Test Set, Required test splits, Statistical protocol

### Community 37 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 38 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 39 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 40 - "Phase 8: Implement a Minimal `sched_ext` Pilot"
Cohesion: 0.50
Nodes (4): Exit gate, Goal, Phase 8: Implement a Minimal `sched_ext` Pilot, Scope

### Community 41 - "Phase 9: Reproducibility and Research Report"
Cohesion: 0.50
Nodes (4): Exit gate, Goal, Phase 9: Reproducibility and Research Report, Required artifacts

### Community 51 - "DemoTests"
Cohesion: 0.14
Nodes (7): _project_python(), Path, Interactive terminal front-end for AutoScheduler experiment demos., Run numbered presentation menu without changing research artifacts., run_demo(), DemoTests, FakeRunner

### Community 54 - "TestSrtfTieBreaking"
Cohesion: 0.22
Nodes (6): _pids(), P1: arrival=0, burst=5 P2: arrival=0, burst=5 Both have the same remaining_time…, When a new process arrives with the same remaining_time as the currently…, P1: arrival=0, burst=5 (running, remaining=3 at t=2) P2: arrival=2, burst=3…, Return just the pid sequence from a timeline., TestSrtfTieBreaking

### Community 57 - "TestSrtfPreemption"
Cohesion: 0.22
Nodes (5): Three processes where preemptions happen at every arrival. P1: arrival=0,…, Classic SRTF preemption example: P1: arrival=0, burst=8 P2: arrival=2, burst=3…, If the running job is always shorter than any new arrival, SRTF should not…, Verify that SRTF and non-preemptive SJF produce different timelines for a…, TestSrtfPreemption

### Community 58 - "TestSrtfIdleCpu"
Cohesion: 0.22
Nodes (5): Only one process, arriving at t=5. Expected: CPU idle 0-5. P1 runs 5-10.…, P1: arrival=0, burst=3 → completes at t=3 P2: arrival=6, burst=2 → CPU idle…, An empty process list should return two empty lists., Single process should run uninterrupted., TestSrtfIdleCpu

## Knowledge Gaps
- **175 isolated node(s):** `capture_linux_trace.sh script`, `run_firefox_probe.sh script`, `graphify`, `Usage`, `What graphify is for` (+170 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 333 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Process` connect `Process` to `main.py`, `test_fairness.py`, `evaluation.py`, `generate_workload`, `dynamic.py`, `benefit.py`, `srtf`, `test_srtf.py`, `TestSrtfTieBreaking`, `TestSrtfPreemption`, `TestSrtfIdleCpu`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Why does `generate_workload()` connect `generate_workload` to `Process`, `dynamic.py`, `benefit.py`, `cli.py`, `DemoTests`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `read_traces()` connect `read_traces` to `cli.py`, `extract_features_at`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `Process` (e.g. with `run_adaptive()` and `_observe()`) actually correct?**
  _`Process` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `srtf()` (e.g. with `evaluate_benefit()` and `evaluation.py`) actually correct?**
  _`srtf()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `capture_linux_trace.sh script`, `run_firefox_probe.sh script`, `graphify` to the rest of the system?**
  _175 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `generate_workload` be split into smaller, more focused modules?**
  _Cohesion score 0.057942057942057944 - nodes in this community are weakly interconnected._
# Graph Report - AutoScheduler-SL-CPU-Scheduler  (2026-09-13)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 45 nodes · 91 edges · 6 communities (4 shown, 1 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 11 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a11d8f52`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4

## God Nodes (most connected - your core abstractions)
1. `Process` - 18 edges
2. `main()` - 8 edges
3. `run_simulation()` - 8 edges
4. `SimulationResult` - 6 edges
5. `fcfs()` - 6 edges
6. `priority_scheduling()` - 6 edges
7. `round_robin()` - 6 edges
8. `sjf()` - 6 edges
9. `print_result()` - 5 edges
10. `compute_metrics()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `print_result()` --uses--> `SimulationResult`  [INFERRED]
  main.py → simulator/simulator.py
- `fcfs()` --uses--> `Process`  [INFERRED]
  scheduler/fcfs.py → simulator/process.py
- `priority_scheduling()` --uses--> `Process`  [INFERRED]
  scheduler/priority.py → simulator/process.py
- `round_robin()` --uses--> `Process`  [INFERRED]
  scheduler/round_robin.py → simulator/process.py
- `main()` --indirect_call--> `priority_scheduling()`  [INFERRED]
  main.py → scheduler/priority.py

## Import Cycles
- None detected.

## Communities (6 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.25
Nodes (10): main(), make_processes(), print_gantt(), print_result(), main.py ------- AutoScheduler: Self-Learning CPU Scheduling Algorithm Phase 1 —…, Return a fresh list of processes for each algorithm run., Print a text Gantt chart. Example output: | P1 | P2 | P4 | P3 | 0 5 8 10 18, Print a formatted summary of one algorithm's simulation result. (+2 more)

### Community 1 - "Community 1"
Cohesion: 0.29
Nodes (9): compute_metrics(), ProcessMetrics, simulator/simulator.py ---------------------- Common simulation layer: computes…, Per-process scheduling metrics., Aggregated result returned by run_simulation()., Derive per-process metrics from a list of scheduled (completed) processes.…, Execute a scheduling algorithm and return a SimulationResult. Parameters…, run_simulation() (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.28
Nodes (6): priority_scheduling(), scheduler/priority.py --------------------- Non-preemptive Priority Scheduling.…, Run the non-preemptive Priority scheduling algorithm. Parameters ----------…, scheduler/round_robin.py ------------------------ Round Robin (RR) — preemptive…, Run the Round Robin scheduling algorithm. Parameters ---------- processes :…, round_robin()

### Community 3 - "Community 3"
Cohesion: 0.25
Nodes (6): scheduler/sjf.py ---------------- Shortest Job First (SJF) — non-preemptive…, Run the non-preemptive SJF scheduling algorithm. Parameters ----------…, sjf(), Process, Represents a single process in the CPU scheduling simulation. Attributes: pid :…, Re-initialise mutable scheduling fields so the same Process object can be…

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Process` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.345) - this node is a cross-community bridge._
- **Why does `run_simulation()` connect `Community 1` to `Community 0`, `Community 3`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `compute_metrics()` connect `Community 1` to `Community 3`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Process` (e.g. with `fcfs()` and `priority_scheduling()`) actually correct?**
  _`Process` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `main()` (e.g. with `fcfs()` and `priority_scheduling()`) actually correct?**
  _`main()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `fcfs()` (e.g. with `main()` and `Process`) actually correct?**
  _`fcfs()` has 2 INFERRED edges - model-reasoned connections that need verification._
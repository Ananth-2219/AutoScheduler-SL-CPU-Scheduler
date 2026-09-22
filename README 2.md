# AutoScheduler: Self-Learning CPU Scheduling Algorithm

A modular Python implementation of classic CPU scheduling algorithms, serving as the foundational engine for a future self-learning (ML-based) adaptive scheduler.

---

## Phase 1 — Basic CPU Scheduling Engine

This phase implements four core scheduling algorithms with a shared process model and simulation layer. No machine learning or adaptive logic is included yet.

### Algorithms Implemented

| Algorithm | Type | File |
|---|---|---|
| First Come First Serve (FCFS) | Non-preemptive | `scheduler/fcfs.py` |
| Shortest Job First (SJF) | Non-preemptive | `scheduler/sjf.py` |
| Round Robin (RR) | Preemptive | `scheduler/round_robin.py` |
| Priority Scheduling | Non-preemptive | `scheduler/priority.py` |

### Project Structure

```text
AutoScheduler/
│
├── scheduler/
│   ├── __init__.py
│   ├── fcfs.py          # First Come First Serve
│   ├── sjf.py           # Shortest Job First (non-preemptive)
│   ├── round_robin.py   # Round Robin (configurable quantum)
│   └── priority.py      # Priority Scheduling (1 = highest priority)
│
├── simulator/
│   ├── __init__.py
│   ├── process.py       # Process dataclass
│   └── simulator.py     # Metrics engine & SimulationResult
│
├── main.py              # Demo: runs all four algorithms on a test workload
└── README.md
```

### Quick Start

```bash
python main.py
```

No external dependencies — pure Python 3.7+.

### Metrics Reported

| Metric | Formula |
|---|---|
| Turnaround Time (TAT) | Completion Time − Arrival Time |
| Waiting Time (WT) | Turnaround Time − Burst Time |
| Response Time (RT) | First Start Time − Arrival Time |

### Scheduling Conventions

- **Priority**: Lower number = higher priority (1 is highest).
- **Tie-breaking**: All algorithms break ties deterministically by `(key, arrival_time, pid)` to produce consistent, repeatable results.
- **Idle CPU**: When no process is available, the clock advances to the next arrival.
- **Round Robin quantum**: Configurable via the `quantum` parameter (default = 2). New arrivals during a quantum are enqueued before the preempted process.

---

> **Next phase**: ML workload classification, real-time performance monitoring, and adaptive algorithm switching.

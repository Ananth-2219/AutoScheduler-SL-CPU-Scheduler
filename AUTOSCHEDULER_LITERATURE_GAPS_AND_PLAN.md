# AutoScheduler Literature Review: Paper Gaps and Proposed Solution

## 1. Project direction

AutoScheduler investigates whether a small machine-learning model can improve
CPU scheduling without adding excessive decision overhead.

The current Python simulator already supports FCFS, SJF, SRTF, Round Robin,
Priority, Priority-RR, MLFQ, CPU/I/O bursts, changing workloads, fairness
metrics, statistical comparisons, and scheduler-decision latency measurements.

The strongest current static baseline is **RR-20-SRTF**:

1. Run Round Robin with quantum 1 at the beginning.
2. At the first dispatch boundary after tick 20, switch permanently to SRTF.

The next proposed ML experiment is deliberately small:

1. Generate workloads whose behavior changes while they are running.
2. Hide future arrivals, future CPU bursts, and future I/O behavior from ML.
3. Keep the Round Robin quantum fixed at 1.
4. Let a compact model choose one switch time: `5`, `10`, `20`, `40`, or
   `never`.
5. Compare it directly with fixed RR-20-SRTF on identical unseen traces.
6. Accept ML only if it improves mean weighted score by at least 1%, its paired
   95% confidence interval is fully below zero, and decision P99 remains below
   10 ms.
7. If simulation evidence succeeds, validate with real workload traces and then
   move the controller toward a Linux `sched_ext` prototype. The simulator is
   the research test bench; it is not yet a kernel scheduler.

## 2. Existing reference papers

### Paper 1: A Machine Learning Approach for Predicting Efficient CPU Scheduling Algorithm

**Reference:** S. Biswas et al., STI 2023, DOI
[10.1109/STI59863.2023.10464816](https://doi.org/10.1109/STI59863.2023.10464816).

**Simple idea:** The paper trains classifiers to choose a classical scheduling
algorithm. It reports SVM as the best classifier with 94.56% accuracy.

**Gap:** High prediction accuracy does not prove that the selected scheduler
actually produces better CPU performance. The work also does not fully measure
runtime decision cost, changing workloads, safe switching, or performance
against a strong hybrid scheduler.

**How our plan addresses it:** We judge ML by completed scheduling results, not
classification accuracy. The model must beat RR-20-SRTF on the same unseen
workloads, pass a paired confidence-interval test, and keep P99 decision time
below 10 ms.

### Paper 2: A Context-Aware Intelligent Scheduling Framework for Modern Operating Systems Using Hybrid Machine Learning Models

**Reference:** P. Savarimalai et al., *Journal of Computational and Cognitive
Engineering*, 5(2), 2026, pp. 321-332, DOI
[10.47852/bonviewJCCE62026664](https://doi.org/10.47852/bonviewJCCE62026664).

**Simple idea:** A random forest identifies workload type and a deep Q-network
changes scheduling actions.

**Gap:** The evaluation uses 50,000 synthetically generated samples in a Python
implementation rather than a demonstrated Linux scheduler. Its reporting also
contains inconsistent response-time figures. A DQN is relatively heavy for a
fast CPU scheduling path.

**How our plan addresses it:** We use a small tree model, expose its exact
switch-time choice, measure complete decision latency, prevent access to future
workload information, and use strict statistical gates. Real traces and kernel
validation are explicit later stages rather than claims based on simulation.

### Paper 3: Mixture-of-Schedulers: An Adaptive Scheduling Agent as a Learned Router for Expert Policies

**Reference:** X. Wang et al., arXiv:2511.11628, 2025.
[Primary source](https://arxiv.org/abs/2511.11628)

**Simple idea:** The system recognizes workload patterns and switches among
expert Linux `sched_ext` schedulers.

**Gap:** It is currently an arXiv preprint. It uses custom expert schedulers,
reports an average total decision latency of 18.3 ms, and contains a small
Top-3 result discrepancy between its abstract and evaluation body. Its design
does not prove that ML is better than a simple fixed RR-to-SRTF switch.

**How our plan addresses it:** We first test the smallest useful decision—when
to switch from RR to SRTF—and require P99 below 10 ms. Only a statistically
proven gain over fixed RR-20-SRTF justifies later `sched_ext` implementation.

### Paper 4: A Reinforcement Learning Based Job Scheduling Algorithm for Heterogeneous Computing Environment

**Reference:** Y. Song et al., *Computers & Electrical Engineering*, 107,
108653, 2023, DOI
[10.1016/j.compeleceng.2023.108653](https://doi.org/10.1016/j.compeleceng.2023.108653).

**Simple idea:** PPO and a graph neural network select tasks from dependency
graphs, while a heuristic assigns them to heterogeneous processors.

**Gap:** This is cluster/DAG task placement across different processors, not
single-CPU operating-system ready-queue scheduling. The model is also too heavy
for a small per-decision latency budget.

**How our plan addresses it:** AutoScheduler models one CPU, arrivals, CPU/I/O
bursts, preemption, waiting, response, fairness, and context switches. The ML
action space contains only five possible switch times and uses a compact model.

### Paper 5: ALPS—An Adaptive Learning, Priority OS Scheduler for Serverless Functions

**Reference:** Y. Fu et al., USENIX ATC 2024, pp. 19-36.
[Primary source](https://www.usenix.org/conference/atc24/presentation/fu)

**Simple idea:** ALPS learns priorities for short serverless functions in user
space and applies them through an eBPF/CFS kernel backend.

**Gap:** It is specialized for serverless functions and adjusts priority rather
than deciding between general CPU scheduling strategies. Its results do not
show whether one approach works across interactive, batch, CPU-heavy,
I/O-heavy, and mixed workloads.

**How our plan addresses it:** We evaluate several workload profiles and traces
that change over time. The model chooses a scheduling transition rather than a
serverless-specific priority. We retain ALPS's useful architectural lesson:
learning outside the kernel and a small actuation path near the kernel.

### Paper 6: STUN—Reinforcement-Learning-Based Optimization of Kernel Scheduler Parameters for Static Workload Performance

**Reference:** H. Lee, S. Jung, and H. Jo, *Applied Sciences*, 12(14), 7072,
2022, DOI
[10.3390/app12147072](https://doi.org/10.3390/app12147072).

**Simple idea:** Q-learning searches for a Linux scheduling policy and parameter
configuration that performs well for a workload.

**Gap:** STUN mainly tunes relatively static workload configurations. It does
not focus on a workload whose behavior changes while processes are running or
on preserving process state during one controlled policy transition.

**How our plan addresses it:** Our traces change during execution. The switch
happens only at a safe dispatch boundary, and the simulator preserves completed
work, remaining work, I/O events, wait history, and process state.

### Paper 7: Applying Machine Learning Techniques to Improve Linux Process Scheduling

**Reference:** A. Negi and K. K. Pusukuri, TENCON 2005, pp. 1-6, DOI
[10.1109/TENCON.2005.300837](https://doi.org/10.1109/TENCON.2005.300837).

**Simple idea:** A C4.5 decision tree learns from previous executions of known
programs and predicts a useful CPU time slice.

**Gap:** The experiment targets known programs on Linux 2.4.20-8. It does not
test unseen changing traces, CPU/I/O phases, modern baselines, or data leakage
from information that a real scheduler would not know.

**How our plan addresses it:** Training, validation, and testing are separated
by complete trace. ML sees only information already observed at runtime. It is
evaluated on fresh workloads against RR-20-SRTF rather than an old default
scheduler alone.

### Paper 8: SCHED—Safe CPU Scheduling Framework with Reinforcement Learning and Decision Trees for Autonomous Vehicles

**Reference:** D. Seo et al., IEEE VTC2025-Spring, 2025, pp. 1-5, DOI
[10.1109/VTC2025-SPRING65109.2025.11174897](https://doi.org/10.1109/VTC2025-SPRING65109.2025.11174897).

**Simple idea:** Reinforcement learning develops a policy, then a decision tree
provides a smaller and more interpretable runtime scheduler for autonomous
vehicle workloads.

**Gap:** It is a short, domain-specific paper and its full text is not openly
available for checking detailed quantitative claims. Its autonomous-vehicle
safety objective is narrower than general CPU scheduling.

**How our plan addresses it:** We publish reproducible seeds, CSV/JSON results,
fairness metrics, paired confidence intervals, and latency percentiles. We use
the same valuable principle—a small interpretable runtime model—but test it
across general workload profiles.

### Paper 9: Caladan—Mitigating Interference at Microsecond Timescales

**Reference:** J. Fried et al., OSDI 2020, pp. 281-297.
[Primary source](https://www.usenix.org/conference/osdi20/presentation/fried)

**Simple idea:** Caladan reacts quickly to CPU and memory interference by using
a centralized controller and a small Linux kernel mechanism for core
allocation.

**Gap:** Caladan is not ML-based and does not select among RR, SRTF, Priority,
or other classical policies. Its headline result comes from a specialized
colocation experiment.

**How our plan addresses it:** We add the missing learned scheduling decision,
but retain Caladan's separation between controller and actuation mechanism. We
also avoid generalizing one workload result by reporting overall and
per-profile outcomes.

## 3. Additional recommended papers

### Paper 10: Decima—Learning Scheduling Algorithms for Data Processing Clusters

**Reference:** H. Mao et al., SIGCOMM 2019, pp. 270-288, DOI
[10.1145/3341302.3342080](https://doi.org/10.1145/3341302.3342080).
[Project page](https://web.mit.edu/decima/)

**Simple idea:** Decima uses reinforcement learning and graph neural networks
to schedule dependent data-processing jobs on a cluster. Its Spark prototype
reports at least 21% lower average job-completion time than tuned heuristics.

**Gap:** Cluster jobs allow much more decision time than an OS CPU scheduler.
Decima's large model and graph-based state are not suitable for a sub-10-ms CPU
decision path, and its objective does not cover process fairness or interactive
response.

**How our plan addresses it:** We keep the action space and model small, measure
P99 decision time directly, and evaluate response, waiting, starvation,
throughput, context switches, and weighted performance together.

### Paper 11: Paragon—QoS-Aware Scheduling for Heterogeneous Datacenters

**Reference:** C. Delimitrou and C. Kozyrakis, ASPLOS 2013, pp. 77-88, DOI
[10.1145/2451116.2451125](https://doi.org/10.1145/2451116.2451125).
[Primary source](https://mast.stanford.edu/pubs/paragon_qos_aware_scheduling_for_heterogeneous_datacenters/)

**Simple idea:** Paragon classifies an unfamiliar workload by comparing it with
previous workloads, then uses a simple scheduling rule to place it on a suitable
server.

**Gap:** It solves datacenter application placement and interference, not CPU
time sharing among processes on one machine. It also depends on a history of
previously seen applications.

**How our plan addresses it:** We apply the same useful split—ML recognizes the
situation, simple rules perform scheduling—but use live single-CPU queue data.
Unknown workloads safely fall back to a fixed switch choice instead of requiring
ML to control every scheduler action.

### Paper 12: ghOSt—Fast and Flexible User-Space Delegation of Linux Scheduling

**Reference:** J. T. Humphries et al., SOSP 2021, pp. 588-604, DOI
[10.1145/3477132.3483542](https://doi.org/10.1145/3477132.3483542).
[Primary source](https://mast.stanford.edu/pubs/ghost_fast_flexible_user_space_delegation_of_linux_scheduling/)

**Simple idea:** ghOSt lets user-space programs make Linux scheduling decisions
while a kernel component applies those decisions efficiently.

**Gap:** ghOSt is an execution framework, not an intelligent policy. It does
not decide what workload features an ML scheduler should observe, when it
should change policy, or how to prove that ML is better than a static hybrid.

**How our plan addresses it:** Our work supplies that decision logic and its
evaluation: observed-only features, one safe RR-to-SRTF transition, statistical
gates, fairness checks, and latency limits. If successful, `sched_ext` or a
ghOSt-like split becomes the implementation layer rather than the research
claim itself.

### Paper 13: Shinjuku—Preemptive Scheduling for Microsecond-Scale Tail Latency

**Reference:** K. Kaffes et al., NSDI 2019, pp. 345-360.
[Primary source](https://www.usenix.org/conference/nsdi19/presentation/kaffes)

**Simple idea:** Shinjuku uses very frequent preemption so short requests do not
get trapped behind long requests. It reports up to 6.6 times higher throughput
and 88% lower tail latency for a mixed RocksDB workload.

**Gap:** Shinjuku uses a specialized single-address-space operating system and
does not use ML. It focuses on network-service requests rather than a general
Linux process workload.

**How our plan addresses it:** SRTF provides the short-job behavior in our
shared simulator, while RR protects early fairness. ML only chooses the safest
time to transition between them. We measure P95 waiting, starvation, response,
context switches, and P99 decision cost so aggressive preemption cannot appear
better by hiding its costs.

## 4. Combined research gap

The literature does **not** support claiming that ML has never been used for
CPU scheduling. Several papers already use classification, reinforcement
learning, decision trees, scheduler routing, or learned priority control.

The narrower unresolved question is:

> Can a compact model, using only information already visible to the scheduler,
> choose when to transition between two strong classical policies and beat the
> best fixed transition under changing workloads, while remaining fair,
> statistically reliable, and faster than 10 ms at P99?

This is the main contribution AutoScheduler should attempt to prove.

## 5. What would count as a successful contribution

AutoScheduler may claim an ML improvement only when all of the following hold:

- ML is evaluated on fresh, trace-disjoint workloads.
- Future arrivals and hidden burst information are unavailable to the model.
- The comparator is fixed RR-20-SRTF, not a weak untuned scheduler.
- Mean weighted score improves by at least 1%.
- The paired 95% confidence interval is completely below zero.
- P99 decision latency is strictly below 10 ms.
- Fairness, starvation, response, and context-switch results are disclosed.
- Real workload traces reproduce the benefit before a kernel-level claim is
  made.

If these gates fail, the correct research result is that the static RR-20-SRTF
hybrid remains the better scheduler for the tested conditions.

## 6. Evidence limitations

- AutoScheduler currently uses synthetic workloads; they are useful for
  controlled experiments but do not prove real-kernel performance.
- The current implementation is a single-CPU Python simulator.
- A passed simulator latency gate measures Python decision logic, not Linux
  kernel dispatch overhead.
- Results reported above belong to each cited paper and have not been
  independently reproduced by this project.
- The proposed switch-time ML experiment and real-trace validation must be
  completed before claiming that ML beats RR-20-SRTF.

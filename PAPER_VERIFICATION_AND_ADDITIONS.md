# AutoScheduler Paper Verification and Additional References

Verified on 23 September 2026 against DOI records, official publisher pages,
conference proceedings, author publication pages, and arXiv. A paper being
listed as verified means its identity and the cited claim appear in the source;
it does not mean the result has been independently reproduced.

## Overall finding

All nine cited works are real and relevant, but they do not all provide the
same level of evidence:

- Seven are peer-reviewed papers with accessible source text and accurately
  reported headline results.
- *Mixture-of-Schedulers* is an arXiv preprint, not confirmed peer reviewed.
- *SCHED* has verified conference metadata and abstract-level claims, but the
  full five-page paper is closed-access, so detailed performance claims cannot
  be checked from the available primary source.
- The 2026 context-aware RF+DQN paper is published, but its generated-data
  evaluation contains inconsistent wording/numbers and should be cited with
  caution.

## Verification of the existing nine papers

| # | Paper | Status | Verification and corrections |
|---|---|---|---|
| 1 | A Machine Learning Approach for Predicting Efficient CPU Scheduling Algorithm | Verified | DOI, title, authors, STI 2023 venue, candidate classifiers, and reported SVM accuracy of 94.56% match the paper. Treat accuracy as classification accuracy on that study's dataset, not proof of kernel-level speed or real-system improvement. |
| 2 | A Context-Aware Intelligent Scheduling Framework for Modern Operating Systems Using Hybrid Machine Learning Models | Verified with caution | Published online 24 Feb. 2026 and now cited as JCCE 5(2), pp. 321-332. RF+DQN, Python implementation, 50,000 synthetically generated samples, and the headline throughput claims are present. However, the abstract says "up to 42.2%" response-time reduction while the results section reports interactive response changing from 42.2 ms to 7.4 ms, called an 82.5% reduction. This internal inconsistency should be disclosed. It is simulation evidence, not a demonstrated Linux-kernel scheduler. |
| 3 | Mixture-of-Schedulers: An Adaptive Scheduling Agent as a Learned Router for Expert Policies | Verified preprint | arXiv:2511.11628, authors, sched_ext routing design, and 86.4% win rate over EEVDF are verified. The source is internally inconsistent: its abstract reports a 78.6% Top-3 rate while the evaluation body reports 78.9%. Quote the figure with its location. The work reports an average total decision latency of 18.3 ms and remains a preprint. |
| 4 | A Reinforcement Learning Based Job Scheduling Algorithm for Heterogeneous Computing Environment | Verified | DOI, volume 107/article 108653, PPO plus bidirectional GCN, and two-stage task-selection/processor-allocation design are verified. It schedules DAG jobs across heterogeneous processors; it is not an OS ready-queue CPU scheduler, so use it as a contrast/reference for learned scheduling rather than direct validation of AutoScheduler. |
| 5 | ALPS: An Adaptive Learning, Priority OS Scheduler for Serverless Functions | Verified | USENIX ATC 2024, pp. 19-36. The user-space learning frontend, eBPF/CFS backend, Huawei/Azure traces, and reported 57.2% reduction in average function execution duration versus CFS are verified. This is one of the strongest direct systems references. |
| 6 | STUN: Reinforcement-Learning-Based Optimization of Kernel Scheduler Parameters for Static Workload Performance | Verified | Applied Sciences 12(14), 7072 and DOI are correct. Q-learning-based policy/parameter tuning and the reported 18.3% execution-time and 22.4% FPS improvements for face detection are present. It tunes relatively static configurations rather than routing every process online. |
| 7 | Applying Machine Learning Techniques to Improve Linux Process Scheduling | Verified | TENCON 2005 DOI, C4.5 decision tree, Linux 2.4.20-8 modification, execution-history features, and reported 1.4%-5.8% turnaround-time reduction are verified. The result is for known programs and custom time slices on an old single-core-era kernel. |
| 8 | SCHED: Safe CPU Scheduling Framework with Reinforcement Learning and Decision Trees for Autonomous Vehicles | Partially verified | Title, authors, VTC2025-Spring venue, pages 1-5, and DOI are verified. The available abstract supports RL training followed by lightweight decision-tree execution and an autonomous-vehicle evaluation. Because the full paper is closed-access, keep claims qualitative unless a copy is obtained. |
| 9 | Caladan: Mitigating Interference at Microsecond Timescales | Verified | OSDI 2020, pp. 281-297. The centralized scheduler/KSCHED architecture and the reported reduction from 580 ms to 52 microseconds in the specified memcached-plus-GC colocation experiment are verified. This is a specialized interference/core-allocation result, not a general claim that all scheduling decisions achieve that improvement. |

## Four additional papers worth adding

### 10. Decima: Learning Scheduling Algorithms for Data Processing Clusters

H. Mao, M. Schwarzkopf, S. B. Venkatakrishnan, Z. Meng, and M. Alizadeh,
SIGCOMM 2019, pp. 270-288, DOI
[10.1145/3341302.3342080](https://doi.org/10.1145/3341302.3342080).

Decima uses reinforcement learning and graph neural networks to learn
workload-specific scheduling policies for DAG jobs. Its 25-node Spark prototype
reports at least 21% lower average job-completion time than hand-tuned
heuristics and up to a 2x improvement under high load.

**Why add it:** It is strong evidence that learned scheduling can beat tuned
heuristics when the state/action space and workload dependencies are genuinely
complex. It also provides a useful boundary: this success is at cluster-job
timescales, not the microsecond OS dispatch path.

Primary source: [MIT Decima project](https://web.mit.edu/decima/)

### 11. Paragon: QoS-Aware Scheduling for Heterogeneous Datacenters

C. Delimitrou and C. Kozyrakis, ASPLOS 2013, pp. 77-88, DOI
[10.1145/2451116.2451125](https://doi.org/10.1145/2451116.2451125).

Paragon uses collaborative filtering to classify unseen workloads by hardware
heterogeneity and resource interference, then schedules them with a lightweight
greedy policy. In a 2,500-workload experiment it reports meeting performance
guarantees for 91% of applications, compared with 14%, 11%, and 3% for the
listed simpler baselines.

**Why add it:** It supports AutoScheduler's most defensible architecture:
machine learning recognizes workload behavior, while a simpler deterministic
mechanism makes the final scheduling action.

Primary source: [Stanford MAST publication page](https://mast.stanford.edu/pubs/paragon_qos_aware_scheduling_for_heterogeneous_datacenters/)

### 12. ghOSt: Fast & Flexible User-Space Delegation of Linux Scheduling

J. T. Humphries et al., SOSP 2021, pp. 588-604, DOI
[10.1145/3477132.3483542](https://doi.org/10.1145/3477132.3483542).

ghOSt delegates Linux scheduling decisions to user-space agents while retaining
a kernel actuation mechanism. Policies can be changed without rebooting and can
target latency, throughput, or energy goals.

**Why add it:** It fills the implementation gap between the current Python
simulator and a real Linux prototype. It is also a useful architectural
comparison for sched_ext: both separate policy experimentation from the core
kernel mechanism.

Primary source: [Stanford MAST publication page](https://mast.stanford.edu/pubs/ghost_fast_flexible_user_space_delegation_of_linux_scheduling/)

### 13. Shinjuku: Preemptive Scheduling for Microsecond-Scale Tail Latency

K. Kaffes, T. Chong, J. T. Humphries, A. Belay, D. Mazieres, and
C. Kozyrakis, NSDI 2019, pp. 345-360.

Shinjuku uses centralized scheduling and preemption as often as every five
microseconds to prevent short requests from waiting behind long requests. For a
mixed RocksDB workload, it reports up to 6.6x higher throughput and 88% lower
tail latency than the compared systems.

**Why add it:** It gives stronger support for SRTF-like preemption, tail-latency
measurement, and decision-overhead accounting. These are central to judging
whether an adaptive selector is useful rather than merely accurate.

Primary source: [USENIX NSDI 2019](https://www.usenix.org/conference/nsdi19/presentation/kaffes)

## Recommended way to use these references

- Use papers 1, 3, 5, 6, and 7 as the closest prior work for learned OS
  scheduling and scheduler/parameter selection.
- Use Decima and Paragon to explain when ML becomes valuable: complex,
  workload-dependent choices with enough decision time and observable signal.
- Use ALPS, ghOSt, Mixture-of-Schedulers, and Caladan to motivate the split
  between an intelligent controller and a small, safe kernel execution path.
- Use Shinjuku to justify preemption, P95/P99 response measurements, and strict
  overhead limits.
- Do not describe every paper as direct evidence for classical CPU-policy
  selection. Papers 4, 9, 10, and 11 solve adjacent scheduling problems at
  different system levels.

## Research gap after verification

The defensible gap is narrower than "ML has not been used for CPU scheduling."
It has. A stronger AutoScheduler claim is:

> Existing studies either learn specialized policies, tune parameters for
> static workloads, route among sched_ext experts at millisecond timescales, or
> schedule jobs/resources above the OS ready queue. There is still limited
> evidence that a compact, observation-only model can safely outperform a
> strong static or hybrid CPU scheduler under changing workloads while meeting
> a strict dispatch-latency budget.

That claim matches the project's current simulator experiments and gives a
clear next validation path: changing traces, no future-burst leakage, strong
RR/SRTF/MLFQ hybrids, paired confidence intervals, fairness checks, and measured
P99 decision latency.

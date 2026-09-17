# AutoScheduler Priority-RR Experiment

> Superseded for primary research claims by
> `results/five_policy_consistent/REPORT.md`. This historical run used a
> four-policy training objective and five-policy evaluation objective.

## Method

This single-CPU experiment adds Priority Round Robin as a deterministic static
baseline. It uses priority classes, Round Robin dispatch, one-level I/O-return
promotion, aging, and one tick of process-switch cost. Existing decision tree
remains a four-policy selector; Priority-RR is not a new ML label.

Nine configurations use quantum values 1, 2, and 4 with aging intervals 4, 8,
and 12. Selection uses seed-42 validation workloads only. Each held-out score
normalizes all five static policies within each workload; score weights remain
unchanged.

## Setup

- Tuning data: 2,500 generated workloads, seed 42; 375 validation workloads
- Held-out data: 1,000 workloads, 200 per profile, seed 2026
- Selected Priority-RR configuration: quantum 1, aging interval 4, switch cost 1
- Pass rule: Priority-RR must have lower mean score and lower maximum waiting
  time than SJF

## Results

- Best static baseline: Round Robin, mean score 0.1108
- Oracle mean score: 0.1061
- SJF: mean score 0.1577; maximum wait 279 ticks
- Priority-RR: mean score 0.7744; maximum wait 605 ticks
- Priority-RR mean regret: 0.6683
- Priority-RR mean switch time: 169.507 ticks
- `priority_rr_beats_sjf`: false

Priority-RR fails both gates. Short selected quantum creates many switches;
one-tick switch cost dominates this synthetic workload mix. Oracle winners:
Round Robin 794, SJF 181, FCFS 25, Priority 0, Priority-RR 0.

## Conclusion

Do not expand this Priority-RR design or add RL. Keep SJF or Round Robin as
supported baseline for this score. Revisit objectives only through separate
findings review that explicitly values fairness or priority service.

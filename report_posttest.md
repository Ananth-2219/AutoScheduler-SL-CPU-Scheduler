# Fairness Metrics Post-Test Report

## Scope

This run added report-only fairness metrics. `SCORE_WEIGHTS`, oracle selection,
static winners, ML behavior, and existing adaptive gates were not changed.
Results use 1,000 held-out workloads (200 per profile), seed 2026. Counts pool
completed processes across all workloads; they are not workload counts.

## New Measurements

- **Maximum wait:** worst individual waiting time.
- **P95 wait:** 95th percentile of pooled waiting times.
- **Starvation count:** waiting time strictly greater than three times process CPU time.
- **Priority delay:** mean and maximum wait for priority classes 1 and 2.
- **Post-I/O response:** delay from I/O completion until next CPU execution.

## Results

| Policy | P95 wait(Lower-Better) | Max wait(Lower-Better) | Starvation count(Lower-Better) | Priority mean wait | Post-I/O mean / max |
|---|---:|---:|---:|---:|---:|
| FCFS | 198.00 | 312 | 9,396 | 90.68 | 28.99 / 187 |
| SJF | 179.05 | 279 | 6,888 | 67.06 | 13.62 / 264 |
| Round Robin | 203.00 | 279 | 10,723 | 101.74 | 10.94 / 21 |
| Priority | 197.00 | 295 | 6,705 | 33.71 | 9.11 / 275 |
| Priority RR | 434.00 | 605 | 10,788 | 216.93 | 14.95 / 22 |

## What Changed in Interpretation

1. **Round Robin remains weighted-score winner** at 0.1108. Fairness reporting
   did not alter this result.
2. **SJF has lowest P95 wait** and ties Round Robin for lowest maximum wait,
   but has a much worse post-I/O tail (264 ticks versus Round Robin's 21).
3. **Priority Scheduling best serves urgent classes.** It has lowest priority
   mean wait and lowest starvation count, but its worst post-I/O delay is 275.
4. **Round Robin gives most predictable post-I/O service.** Its mean is near
   Priority's, while its maximum response is lowest.
5. **Priority RR remains unsuitable.** Switch cost produces largest waiting,
   starvation, and priority-delay values.

## Deterministic Checks

Four fixtures now run SJF, Round Robin, and Priority RR: short-job pressure,
I/O return, high-priority arrival, and switch pressure. Every policy completes
every process. Fixture tests assert only valid deterministic metrics; no policy
is declared winner by a fixture.

## Conclusion

Current evidence supports different policies for different goals:

- Use **Round Robin** for current weighted score and bounded post-I/O tail.
- Use **SJF** for lower typical and worst waiting time.
- Use **Priority Scheduling** when urgent classes matter.

Do not revise score weights yet. The starvation threshold produces thousands of
pooled events, so first review threshold sensitivity and decide whether fairness,
interactive response, or priority service is the research objective.

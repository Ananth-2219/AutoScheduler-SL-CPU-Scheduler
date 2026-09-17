# AutoScheduler Five-Policy Consistency Experiment

## Methodology

The earlier experiment trained the decision tree with four-policy oracle labels
but evaluated scores after adding Priority-RR as a fifth policy. Because metrics
are normalized within each workload across candidate policies, changing the
candidate set changed the effective score. Those results are retained only as
historical artifacts.

This corrected experiment uses FCFS, SJF, Round Robin, Priority, and Priority-RR
throughout tuning, label generation, model training, held-out evaluation, and
latency testing. Score weights, workload profiles, workload counts, and held-out
seed remain unchanged.

Priority-RR was tuned on deterministic seed-42 development workloads. The frozen
configuration is quantum 1, aging interval 4, and context-switch cost 1. The
decision tree uses the existing 70/15/15 split and validation mean regret for
hyperparameter selection. Round Robin was the best validation static policy and
was frozen as the held-out comparator.

Adaptive evidence uses the paired per-workload score difference:
`adaptive score - Round Robin score`. A lower value favors Adaptive. The 95%
confidence interval uses 10,000 deterministic paired bootstrap resamples with
seed 2027. Adaptive must have a negative mean and confidence-interval upper bound,
and P99 decision latency must remain below 10 ms at every tested size.

## Training Results

- Workloads: 2,500; 500 per profile; seed 42
- Oracle labels: Round Robin 2,035; SJF 395; FCFS 70; Priority 0; Priority-RR 0
- Validation accuracy: 0.824
- Validation mean regret: 0.0037
- Test accuracy: 0.800
- Test mean regret: 0.0049
- Frozen static comparator: Round Robin

## Held-Out Results

- Workloads: 1,000; 200 per profile; seed 2026
- Adaptive accuracy: 0.792
- Adaptive mean regret: 0.0050
- Oracle mean score: 0.1061
- Round Robin mean score: 0.1108
- Adaptive mean score: 0.1111
- Adaptive minus Round Robin mean: 0.000292
- Paired 95% confidence interval: [-0.000105, 0.000756]
- Statistical pass: false

Adaptive matches Round Robin on interactive, batch, and I/O-intensive profiles.
It is slightly worse on CPU-intensive and mixed workloads. Every per-profile
confidence interval includes zero or is exactly zero, so no profile provides
evidence of adaptive improvement.

## Decision Latency

Every policy passes the strict P99 decision-time gate below 10 ms. Large-workload
P99 values are 0.120 ms for SJF, 0.055 ms for Round Robin, 0.120 ms for Priority,
0.169 ms for Priority-RR, and 6.136 ms for Adaptive.

Adaptive remains within the latency requirement, but it is much slower than the
static selectors and does not improve weighted score.

## Conclusion

Use Round Robin for the current five-policy objective. Adaptive selection does
not beat the validation-frozen static baseline and fails the statistical gate.
Per the experiment rule, stop ML expansion. Further work requires a separate
objective review, such as fairness-first or real-time scheduling, rather than
additional models or features under the current score.

## Limitations

- Results use synthetic workloads, not kernel traces.
- The simulator models one CPU and selects one policy per workload.
- Metric normalization depends on the fixed five-policy candidate set.
- Priority and fairness diagnostics do not affect the weighted objective.
- Latency measures Python simulator decisions, not kernel scheduling overhead.

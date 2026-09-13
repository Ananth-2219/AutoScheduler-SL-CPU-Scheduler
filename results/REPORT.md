# AutoScheduler Experimental Report

## Methodology

AutoScheduler generates five seeded synthetic workload profiles: interactive,
batch, CPU-intensive, I/O-intensive, and mixed. Each process contains an arrival
time, priority, and alternating CPU and I/O bursts. FCFS, SJF, Round Robin, and
Priority Scheduling run on every training workload.

The oracle label is the algorithm with the lowest workload-normalized score:
30% waiting time, 25% response time, 20% turnaround time, 15% CPU-utilization
penalty, and 10% throughput penalty. The decision tree receives only features
available before simulation.

## Experimental Setup

- Training data: 2,500 workloads, 500 per profile, seed 42
- Split: 70% training, 15% validation, 15% internal test
- Held-out evaluation: 1,000 workloads, 200 per profile, seed 2026
- Tuned parameters: tree depth and minimum leaf size
- Selected tree: depth 3, minimum leaf size 10
- Oracle class distribution: SJF 2,033; Priority 283; FCFS 168; Round Robin 16

Candidates are selected by lowest validation mean regret, then lower depth and
larger minimum leaf size. Accuracy is diagnostic, not the tuning objective.
Oracle weights stayed fixed for this experiment.

## Results

- Validation accuracy: 81.3%
- Validation mean regret: 0.0195
- Internal test accuracy: 81.3%
- Internal test mean regret: 0.0168
- Held-out accuracy: 80.0%
- Mean adaptive score: 0.2556
- Constant SJF score: 0.2556
- Best static algorithm: SJF, score 0.2556
- Oracle score: 0.2370
- Mean regret from oracle: 0.0187
- Mean selector inference time: 0.063 ms
- `adaptive_beats_sjf`: false
- `eligible_for_next_adaptive_phase`: false

The trained model selected SJF for all 1,000 held-out workloads. Therefore,
AutoScheduler did not strictly outperform constant SJF and cannot proceed to a
new adaptive phase under the diagnostic gate.

## Diagnostic Evidence

Held-out oracle labels were FCFS 71, SJF 800, Round Robin 6, and Priority 123.
The selected-policy distribution was SJF 1,000, so every confusion-matrix count
falls in the SJF selection column. The leading feature importances were I/O
frequency (45.4%), burst variance (36.3%), burst mean (7.7%), I/O-to-CPU ratio
(7.1%), and priority mean (3.6%).

`evaluation.csv`, `confusion_matrix.csv`, `feature_importance.csv`, and
`diagnostics.png` preserve the raw diagnostic evidence. The strict pass rule is
adaptive mean score < constant-SJF mean score. A score change requires a
separate written findings review.

## Discussion

The experiment does not yet demonstrate useful adaptive behavior. SJF wins 80%
of held-out oracle labels and the selected scoring function strongly rewards the
waiting and turnaround metrics that SJF is designed to minimize. Classifier
accuracy therefore overstates the value of adaptation: a constant SJF selector
achieves the same aggregate result. The diagnostics make this explicit rather
than treating 80% classifier accuracy as evidence of adaptive value.

The oracle's lower score shows that workload-specific selection has theoretical
room to improve. Current features and objective do not make minority winners
predictable enough for this decision tree.

## Limitations

- Synthetic workloads may not match production operating-system traces.
- Priority importance and fairness are absent from the oracle score.
- Context switches are counted but have no simulated time cost.
- Round Robin wins few labels under the selected weights.
- Selection occurs once per workload, not during execution.
- Results cover one seeded training set and one held-out evaluation set.

## Conclusion

The implementation proves the complete adaptive-scheduling experiment pipeline,
including CPU/I/O simulation, reproducible data generation, oracle labeling,
training, inference, and baseline comparison. Current evidence does not support
a claim that the adaptive selector improves performance over SJF. Future work
requires a separate findings review before revising score weights or expanding
adaptive scheduling; until then, constant SJF is the simpler supported choice.

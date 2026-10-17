# Locked Evaluation Gate Report

**Status: SYNTHETIC_DEVELOPMENT_ONLY**

- Fixed comparator: `Round Robin` (chosen only from validation data)
- Locked-test traces: 60 / 60 required
- Model cost: `0.185541`; comparator cost: `0.185991`
- Improvement: `0.002422463570366883`; gate: `False`
- Paired model-minus-comparator 95% CI: `[-0.000900, -0.000008]`; gate: `True`
- Decision P99: `23.408250 ms`; gate: `False`
- Fairness gate: `True`; details: `{'passes': True, 'selected_mean_starvation_count': 10.0, 'comparator_mean_starvation_count': 10.0, 'selected_mean_post_io_max_response_time': 0.44525547445255476, 'comparator_mean_post_io_max_response_time': 13.532846715328468}`

This report is an offline replay prototype. It cannot authorize a scheduler deployment or support a real-kernel performance claim.

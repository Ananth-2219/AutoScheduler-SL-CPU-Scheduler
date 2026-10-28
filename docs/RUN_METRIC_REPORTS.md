# Run the dashboard metric reports

Run these commands from the repository root. They use the existing `.venv` if
available, print results to the terminal, and do not train models or overwrite
datasets, models or historical result files. Each report includes its source,
units and calculation scope. The default output is a compact set of aligned
tables, with separate scheduling, regression, safety and overhead sections.
The dashboard's scheduler behavior is unchanged.

| Run | What it shows | What is calculated now |
|---|---|---|
| `python3 scripts/show_demo_metrics.py` | All four dashboard workload comparisons, measured controller overhead and transitions; selecting `--algorithm` also shows per-process metrics | Calls the same backend functions as `/api/simulation` and `/api/comparison` |
| `python3 scripts/show_synthetic_metrics.py` | Original v5 synthetic audit, classifier/cost-tree training evidence and historical offline-classifier metadata | Recalculates policy means from saved audit CSV; explicitly retains historical pooled P99, confidence intervals and training results |
| `python3 scripts/show_azure_metrics.py` | Original v5 versus tuned MLFQ, comparison percentages, retained timeouts, decision counts, regression errors and recorded overhead | Aggregates the original 17 selected workloads using the common-complete subset; performs fresh regression inference on saved development labels |
| `python3 scripts/show_azure_retrained_metrics.py` | Separate six-workload original/retrained/MLFQ comparison and train/validation/internal-test regression metrics | Aggregates the saved per-workload rows and performs fresh inference without fitting |
| `python3 scripts/show_bakeoff_metrics.py` | Dummy, Ridge, Decision Tree, Random Forest and Histogram Gradient Boosting results | Displays the same saved offline-replay comparison and gates as the dashboard; does not rerun the bake-off |
| `python3 scripts/show_latency_metrics.py` | Current original-v5 controller mean, median, P95, P99, maximum, accumulated time and switch counts | Times the four demo workloads with 30 runs each, after five tiny-job warmups |

These scripts share the calculations in `autoscheduler/review_metrics.py`; they
do not contain hand-entered performance results. Saved experiment outcomes are
inputs to aggregation, not fresh scheduling reruns. Historical gates and
confidence intervals are labeled as historical rather than recomputed silently.
Unavailable measurements appear as `--` with an explanation (`null` in JSON).
Recorded P99 overhead is shown for each matching saved cohort; cumulative time
is explicitly labeled `not recorded` when only percentiles were saved. No total
is estimated by multiplying P99 by the review count.

Add `--json` to retain every underlying field, including all policies, detailed
provenance, saved confidence intervals and historical cohorts. These details are
kept out of the default tables to make them easier to present.

## Useful options

```bash
# Show just the selected switching demo and original fitted v5.
python3 scripts/show_demo_metrics.py --workload dynamic_response_advantage --algorithm 'Dynamic ML (v5)'

# Show the separate synthetic v6 audit and its saved fixed-baseline sensitivity.
python3 scripts/show_synthetic_metrics.py --version 6

# Add freshly measured cumulative controller overhead to the displayed metrics.
# Original Azure: 12 previously completed workloads (can take tens of seconds).
python3 scripts/show_azure_metrics.py --measure-overhead

# Retrained Azure: the retrained model on its own six-workload cohort.
python3 scripts/show_azure_retrained_metrics.py --measure-overhead

# Synthetic v5: its cost tree on all 240 original audit workloads.
python3 scripts/show_synthetic_metrics.py --measure-overhead

# Synthetic v6: its own frozen model/configuration and audit workload seeds.
python3 scripts/show_synthetic_metrics.py --version 6 --measure-overhead

# Reproduce cost-error metrics for original and Azure-retrained models together.
# This existing script performs inference only; it does not fit either model.
python3 scripts/show_model_metrics.py

# Measure the 12 previously completed Azure development workloads, once each.
# Default cap: 20 seconds per workload; failures remain visible.
python3 scripts/show_latency_metrics.py --suite azure

# Timing report only, for the separate Azure-retrained model/cohort.
python3 scripts/show_latency_metrics.py --suite azure --model retrained

# Timing-only replay of six synthetic audit workloads, without fitting/labeling.
# Omit --limit to time all 240 original v5 synthetic audit workloads.
python3 scripts/show_latency_metrics.py --suite synthetic --limit 6

# More repeated demo timing samples.
python3 scripts/show_latency_metrics.py --repeats 300 --warmups 20

# Export any report as JSON using ordinary shell redirection.
python3 scripts/show_azure_metrics.py --json > /tmp/original_v5_metrics.json
```

Scripts also work when invoked by absolute path from another directory.
Use `--help` on any script for its options. Report scripts exit nonzero if a
required input is unavailable; the latency command also exits nonzero on a
retained timing timeout, including when invoked by `--measure-overhead`.
No dependencies are installed automatically.

## Read the cohorts and units correctly

- Original Azure v5: 17 selected workloads; historical matched means use the 12
  completed by all seven policies. Eight policy timeouts remain in the report.
- Azure-retrained v5: a separate six-workload development cohort. Neither this
  report nor fresh inference accesses the reserved final holdout.
- Synthetic v5: 240 audited development workloads; v6 is a separate cohort.
  Synthetic ticks have no calibrated physical millisecond mapping.
- Latency is host wall time measured by the existing controller timer: feature
  extraction, predictions, margin, safeguards and accepted-switch queue updates.
  It excludes imports/model loading, CPU dispatch, HTTP and browser playback.
- Only Azure uses 1 tick = 1 ms. The latency report divides **summed controller
  time**, not P99 times review count, by summed simulated makespan and CPU proxy
  time. Idle time is included in makespan and excluded from CPU proxy time.
  These ratios are illustrative budgets, not measured process slowdown: the
  simulator does not add host overhead to simulated time or model feedback from
  doing so. Python simulation wall time is also reported separately.
- The new report commands do not automatically replace dashboard research
  panels or their saved historical values. Timing varies by host and run.

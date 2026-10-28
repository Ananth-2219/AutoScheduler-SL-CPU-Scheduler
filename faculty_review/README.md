# Faculty review: answers, terminal commands and code links

Open this file in your editor's Markdown preview to click the source links. Each link opens a project file; the function and line number tell you where to look. In VS Code, use Ctrl+G after opening a file to jump to that line. Line numbers were checked against the current source when this guide was written and may move after edits.

This guide was prepared by reading code and saved results. No tests, training, report scripts or dashboard changes were performed to prepare it.

## 1. “We used a Decision Tree Regressor, right?”

**Say:** “Yes. Our Dynamic v5 controller uses a multi-output Decision Tree Regressor. It takes 19 observed workload features and predicts a numerical cost for each action. We choose the lowest predicted cost, then apply switching safeguards.”

The six outputs are **FCFS, Round Robin, Priority, Priority RR, MLFQ and No Switch**. No Switch means keep the current policy. These are action costs, not process IDs, CPU burst predictions or six class probabilities. Costs use a weighted scheduling-score difference relative to MLFQ continuation. Lower is better.

The development-selected v5 tree has **maximum depth 3, minimum leaf size 10 and random seed 9701**. Its switch margin is **0.005**. The saved v5 configuration reviews every 10 simulated ticks with a minimum dwell of 20 ticks; reviews execute at available dispatch boundaries.

**Open these files:**

| What to demonstrate | Click to open | Function / line |
|---|---|---|
| The actual sklearn regressor constructor | [Model factory](../autoscheduler/model_bakeoff.py) | `_new_model`, line 25; `DecisionTreeRegressor` at 38 |
| Original policy-cost training | [Training](../autoscheduler/model.py) | `fit_candidate`, line 179; `.fit()` at 184 |
| Cost predictions become an action | [PolicyCostModel](../autoscheduler/model.py) | `predict`, line 22 |
| Predicted benefit must exceed a margin | [Switch margin](../autoscheduler/model.py) | `switch_allowed`, line 31 |
| Actual runtime switching and guards | [Dynamic controller](../autoscheduler/dynamic.py) | `run_dynamic`, line 481; decision logic at 508 |
| Separate Azure tree fitting | [Azure retraining](../autoscheduler/azure_v5_retrain.py) | `DecisionTreeRegressor(...).fit(x, y)`, line 107 |
| Saved exact parameters and action order | [Azure experiment protocol](../results/dynamic_v5_azure_retrained_20261020/protocol.json) | `tree_parameters`, `actions`, `config` |

**If asked “Why regression rather than classification?”** A classifier predicts an action label. Regression predicts comparable costs, so the controller can estimate whether a change has enough benefit to justify switching. The repository also contains an older choose-once classifier and diagnostic classifiers; their accuracy percentages are separate from v5 regression fit.

**If asked “Why a tree?”** It provides inspectable threshold rules over a small tabular input and a compact inference path. That is a design justification, not proof that it outperforms every other model. Scikit-learn describes trees as learned decision rules and supports multi-output regression: [official tree documentation](https://scikit-learn.org/stable/modules/tree.html).

## 2. “Do we have proof and comparison metrics?”

**Say:** “We have saved experiments, fitted artifacts, source hashes and terminal scripts that reproduce or display the comparisons. Those results show both benefits and failures. They do not establish universal superiority or real Linux scheduler performance.”

### Regression evidence: the same Azure development labels

These are saved results on **72 internal-test decision states from six provenance groups**, with six cost outputs per state. The mean-cost baseline uses 216 training states from 18 disjoint groups. These internal test data were previously inspected; the reports do not establish independent final generalization.

| Model | MAE ↓ | RMSE ↓ | Pooled R² ↑ |
|---|---:|---:|---:|
| Original Dynamic v5 tree | 0.012602638 | 0.019537636 | -3161.553846 |
| Separate Azure-retrained v5 tree | 0.000245307 | 0.001121760 | -9.425419 |
| Training-mean cost baseline | 0.000096746 | 0.000355869 | -0.049241 |

Sources: [original-model report](../results/original_v5_azure_prediction_20261020/REPORT.md), [original numerical metrics](../results/original_v5_azure_prediction_20261020/metrics.json), [retrained-model report](../results/dynamic_v5_azure_retrained_20261020/REPORT.md), [retrained numerical metrics](../results/dynamic_v5_azure_retrained_20261020/prediction_metrics.json).

**Interpretation:** Retraining improves these prediction errors relative to the original model, but the retrained model still loses to the mean-cost baseline on this test set. Negative R² means predictions are worse than the constant test-target mean under the stated pooled calculation. The separately reported dummy is based on training means, so its R² need not equal zero. **R² is not classification accuracy.**

**Metric definitions:** MAE is average absolute prediction error. RMSE squares errors before averaging and taking a square root, so larger errors have more influence. Here the errors are in dimensionless score-delta units, not milliseconds. Inspect [the calculation](../autoscheduler/azure_regression_comparison.py), `metrics`, line 24. This code pools all decision/action pairs for R²; it does not use an average of six separately calculated R² values.

### Scheduling evidence: judge the resulting schedule separately

| Experiment | Saved finding | What you can conclude |
|---|---|---|
| Original v5 synthetic audit: 240 workloads | Score 0.135887 versus tuned MLFQ 0.167564, an 18.90% lower point estimate; mean workload P95 7.64500 versus 7.48729 ticks | A score benefit with a response-tail tradeoff; the P95 acceptance gate fails and v5 is not promoted |
| Separate Azure-retrained evaluation: six development workloads | Retrained score 0.02752916 versus original v5 0.04166667; retrained scheduling metrics equal tuned MLFQ on all six workloads | Improvement relative to original v5 on this cohort; no measurable switching benefit over tuned MLFQ |

Sources: [synthetic audit and paired confidence intervals](../results/dynamic_v5_20261019/REPORT.md), [Azure scheduling comparison](../results/dynamic_v5_azure_retrained_20261020/REPORT.md). The two experiments have different cohorts and score reference conventions; do not compare their absolute scores across rows.

For “Did you compare other ML algorithms?”, open [the Azure regression comparison](../results/dynamic_v5_azure_prediction_comparison_20261020/REPORT.md). It compares the existing tree, a regularized tree, Ridge, Random Forest and a mean dummy. **None beats the dummy on both validation MAE and RMSE**, so no candidate is selected. The code is [azure_regression_comparison.py](../autoscheduler/azure_regression_comparison.py), `run`, line 63.

The dashboard's **five-family replay bake-off is a separate experiment**: Dummy, Ridge, Decision Tree, Random Forest and Histogram Gradient Boosting. Its [saved summary](../results/real_desktop_ml/decision-tree-demo/summary.json) selects **Ridge**, not the tree. Tree, forest and Ridge tie at zero realized cost on its two test traces. The status is `prototype_development_only`, labels are `pilot_offline_replay_development_only`, and the data gate is `INSUFFICIENT_DATA`: **2 test traces versus 60 required**. This cannot select the final real-data model or prove real-kernel performance.

## 3. “Are we manually extracting features?”

**Say:** “We manually designed the feature definitions, but software automatically computes their values. We do not type the feature values for each row. This is domain-informed feature engineering with automated extraction.”

For example, if three ready jobs have waited 2, 4 and 6 ticks, the code computes `ready_count = 3`, `ready_wait_mean = 4` and `ready_wait_max = 6`. We chose those measurements; the program calculates them from state at each review.

The dynamic extractor is [extract_dynamic_features](../autoscheduler/dynamic.py), line **422**. Its 19 inputs are listed at line **26**:

| What the feature describes | Inputs |
|---|---|
| Current queues | `ready_count`, `blocked_count` |
| Completed CPU bursts | `completed_burst_mean`, `completed_burst_variance` |
| CPU service already observed | `observed_service_mean`, `observed_service_variance` |
| Current priority | `priority_mean` |
| Ready waiting | `ready_wait_mean`, `ready_wait_max`, `ready_wait_p50`, `ready_wait_p95` |
| Recent activity | `recent_arrivals`, `io_returns`, `io_return_ratio`, `arrival_quiet_ticks` |
| Controller state | `active_policy_index`, `dwell_remaining_ticks` |
| Jobs awaiting first CPU service | `first_service_ready_count`, `first_service_wait_max` |

The tree automatically learns **which supplied features to split on and at which thresholds**. It does not invent these 19 inputs from the raw Azure archive. Feature importance describes use of the supplied inputs; it is not automatic creation of new features.

### “What is automatic feature extraction? Is it possible?”

**Yes. There are several meanings:**

| Meaning | Example | Current project |
|---|---|---|
| Automatically calculate defined features | Code computes queue counts, averages and variances | Already implemented |
| Automatically select useful existing features | RFE or model-based feature selection chooses a subset | The tree chooses its split inputs; a separate RFE pipeline is not established here |
| Automatically generate candidate features | Generate lagged counts, rolling statistics and ratios from past event windows | Possible extension; not the current v5 feature contract |
| Learn a transformed representation | PCA learns numerical components; an autoencoder could learn an encoded history | Possible extension; not the current v5 training path |

Feature selection retains or removes supplied inputs; representation extraction creates transformed inputs. PCA is a linear transformation, not an automatic understanding of scheduling. See [official feature-selection documentation](https://scikit-learn.org/stable/modules/feature_selection.html) and [official PCA documentation](https://scikit-learn.org/stable/modules/decomposition.html#pca).

**“Why did we choose designed features?”** They correspond to scheduling concepts we can explain and audit, enforce a fixed input order, and make it easier to check that only information already observed is available. Runtime cost still needs measurement. We have not run a controlled comparison proving that hand-designed features are more accurate or faster than learned representations.

**“Could we add automatic extraction later?”** Yes, as a separately specified experiment. Split complete source/capture groups first; fit any learned transformation and select features using training/validation only; feed each decision only past events; evaluate prediction error, actual scheduling, fairness and controller latency; freeze the full pipeline before final testing. This would require a new version of the frozen feature contract, not silently changing the existing model inputs.

### “Can automatic extraction recover everything from Azure?”

**No. It cannot recover unrecorded ground truth.** Our Azure source supplies minute invocation counts and duration summaries. The converter reconstructs within-minute arrivals and uses rounded-up mean wall-clock duration as a CPU-demand proxy. These are explicit modeling assumptions, not measured per-process CPU bursts or precise original arrivals.

Open [Azure reconstruction](../AzureWorkloads/scripts/convert_workloads.py), `reconstruct`, line **21**, and [dataset explanation](../AzureWorkloads/README.md). Keep these two stages distinct:

```text
Azure observations → cleaning/reconstruction → simulator Process objects
Current observed simulator state → 19 numerical features → cost tree → guarded action
```

The separate real Linux trace pipeline has **16 observed features**, not these 19. Open [real_features.py](../autoscheduler/real_features.py): the list is at line **11**, `extract_features_at` starts at **58**, and lines **71–74** exclude events at or after the decision time. Do not interchange its feature rows with the v5 model inputs.

## 4. “Where do training labels come from? Is that leakage?”

**Say:** “Features come from observed state. Labels are generated offline by replaying alternative feasible actions and comparing their scheduling costs. Future outcomes may be used as offline targets, but they are excluded from runtime features.”

Show [dynamic.py](../autoscheduler/dynamic.py), `_counterfactual_label`, line **557**. It copies the same state for each action, runs the action over its feasible horizon, continues with the baseline, then calculates a cost. That work creates training targets; it is not repeated at every runtime prediction.

Show [group splitting](../autoscheduler/model.py), `_split_indexes`, line **76**, and [Azure group checks](../autoscheduler/azure_v5_retrain.py), `validate_splits`, line **34**. Azure source groups remain in one split. For the Linux track, [real_split.py](../autoscheduler/real_split.py), `split_feature_rows`, line **37**, keeps application/scenario/capture groups together. A real-data split manifest is required before fitting.

The [real-dataset builder](../autoscheduler/real_dataset.py), line **23**, emits development replay labels. `real-features` alone supplies inputs, not action-cost labels; neither is a real-kernel performance measurement. The [offline replay contract](../docs/OFFLINE_REPLAY_CONTRACT.md) defines that boundary.

## 5. Terminal demonstration: existing scripts

Run from the repository root. These are commands to use during the review; they were not run while preparing this guide. They do not train models. Demo and latency reports execute simulations; other reports mainly aggregate saved evidence, with Azure reports also performing inference.

| Faculty asks to see | Terminal command | Click to inspect the script |
|---|---|---|
| Dashboard demo metrics and policy comparisons | `python3 scripts/show_demo_metrics.py` | [Demo script](../scripts/show_demo_metrics.py) |
| One demo, including per-process values | `python3 scripts/show_demo_metrics.py --workload dynamic_response_advantage --algorithm 'Dynamic ML (v5)'` | [Demo script](../scripts/show_demo_metrics.py) |
| Original synthetic v5 evidence | `python3 scripts/show_synthetic_metrics.py` | [Synthetic script](../scripts/show_synthetic_metrics.py) |
| Original v5 on Azure-derived workloads | `python3 scripts/show_azure_metrics.py` | [Azure script](../scripts/show_azure_metrics.py) |
| Separate Azure-retrained results | `python3 scripts/show_azure_retrained_metrics.py` | [Retrained script](../scripts/show_azure_retrained_metrics.py) |
| Original/retrained/dummy MAE, RMSE and R² | `python3 scripts/show_model_metrics.py` | [Inference and calculation](../scripts/show_model_metrics.py) |
| Saved five-family replay comparison | `python3 scripts/show_bakeoff_metrics.py` | [Bake-off script](../scripts/show_bakeoff_metrics.py) |
| Fresh controller timing on demo workloads | `python3 scripts/show_latency_metrics.py` | [Latency script](../scripts/show_latency_metrics.py) |

For all fields in the shared report scripts, add `--json`. See [existing terminal instructions](../docs/RUN_METRIC_REPORTS.md) for optional timing and cohort controls. `show_model_metrics.py` is a separate script and does not offer that shared `--json` option.

**“Are terminal and dashboard calculations connected?”** Open [review_metrics.py](../autoscheduler/review_metrics.py), `demo_report`, line **192**. It calls the dashboard's existing backend `simulation` and `comparison` functions and prints their results. The terminal does not need a running browser. `bakeoff_report`, line **348**, reads the saved comparison summary. Reports distinguish fresh calculations from saved outcomes.

**“What does overhead measure?”** Controller feature extraction, inference, margin checks, safeguards and accepted queue updates are timed in [run_dynamic](../autoscheduler/dynamic.py), lines **511–549**. Host wall-clock milliseconds are separate from simulated waiting/response ticks. These numbers do not measure Linux application slowdown or browser rendering. Fresh timing varies with the machine and run.

## 6. Additional code locations worth knowing

| Question | Click to open | Where to explain |
|---|---|---|
| What is a process? | [Process representation](../simulator/process.py) | `Process`, line 12; fields begin at 28, with CPU/I/O bursts and runtime state |
| Where are classical policy rules? | [Shared static engine](../simulator/engine.py) | `simulate`, line 32; `take_ready` and quantum handling |
| Where does the dynamic CPU execute a job? | [Dynamic dispatch](../autoscheduler/dynamic.py) | `_dispatch`, line 302 |
| How is progress preserved across policy changes? | [Policy transition](../autoscheduler/dynamic.py) | `_switch_policy`, line 291; ready-queue rebuild at 272 |
| How are waiting/response/turnaround calculated? | [Metric calculation](../simulator/simulator.py) | `compute_metrics`, line 54; formulas at 71–73 |
| How is the overall score calculated? | [Scoring](../autoscheduler/evaluation.py) | weights at 38; `score_result_against_reference` at 86 |
| Which actions are realistic? | [Policy registry](../autoscheduler/evaluation.py) | `DEPLOYABLE_ALGORITHMS`, lines 31–36; true-burst SJF/SRTF are oracle references |
| Which model does the original-v5 demo load? | [Backend loader](../dashboard/adapter.py) | artifact constant at 24; `_original_v5` at 93 verifies the source hash |
| Where are terminal report calculations? | [Report backend](../autoscheduler/review_metrics.py) | `prediction_report` 64, `azure_report` 114, `synthetic_report` 172, `demo_report` 192 |
| Where is the frozen Linux research contract? | [Real-data config](../configs/real_desktop_ml.json) | allowed features, policies, split rules and gates |

Waiting = completion − arrival − CPU service − I/O time. Response = first CPU start − arrival. Turnaround = completion − arrival. The weighted score combines normalized waiting **0.30**, response **0.25**, turnaround **0.20**, CPU utilization **0.15** and throughput **0.10**; lower scores are better. Report P95 and fairness separately as well.

The experimental v5 comparator uses tuned MLFQ `(1, 2, 4)`, aging 40. The frozen Linux contract uses MLFQ `(2, 4, 8)`, aging 20. The experiment does not change the frozen Linux policy contract.

## 7. A 30-second answer to rehearse

“We built an event-driven CPU scheduling simulator and a dynamic controller. A decision tree regressor estimates action costs using automatically computed, manually designed features from observed execution history. The controller chooses the lowest-cost action subject to dwell, margin and safety checks. We can show the same backend demo metrics in the terminal and trace comparisons to saved experiments. The results include failures: the tree is not proven universally best, the Azure-retrained model does not beat tuned MLFQ, and real Linux validation remains separate.”

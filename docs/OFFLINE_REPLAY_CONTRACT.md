# Offline Replay Contract

Offline replay reconstructs simulator workloads from completed Linux traces. It
is a candidate-screening method only. It does not establish real Linux
scheduler performance.

## Eligibility

- A trace must not be marked truncated.
- A process must have an exit event and a completion time.
- Replay uses the capture's `affinity_cpu` (or legacy `cpu`).
- A process with a CPU switch event on another CPU is rejected as
  `migrated_cpu`.
- A process with no reconstructed CPU service is rejected; no service is
  fabricated from wall-clock duration.
- A process missing a wakeup after a blocking state is rejected.
- A trace with no accepted process is rejected.

Accepted and rejected process counts must be reported with every replay result.

## Build command

Create one deterministic JSON manifest from canonical JSONL traces:

```bash
python main.py real-replay-build trace-a.jsonl trace-b.jsonl \
  --output data/processed/linux/offline_replay_manifest.json
```

Each accepted trace includes reconstructed `Process` inputs. A rejected trace
stays in the manifest with its reason; no source trace is silently dropped.

## Reconstruction

- Replay time uses one tick per millisecond.
- Arrival is measured from the first trace event.
- If a task was already running on the affinity CPU immediately before its
  recorded arrival, its replay service starts at arrival; pre-arrival service
  is excluded.
- A `switch_in` through `switch_out` interval contributes observed CPU service.
- Runnable (`R`) switch-outs are preemptions. Their service remains in the same
  logical CPU burst.
- Blocking states end a CPU burst. The next wakeup becomes the intervening I/O
  duration.
- Exit ends the final CPU burst.
- Any terminal `Z` or `X` switch-out recorded after exit is ignored.
- Positive durations round up to one replay tick only after a complete logical
  CPU or I/O burst has been accumulated.
- Linux normal priority 100 maps to simulator priority 0; lower Linux numeric
  values remain higher simulator priority.

## Information boundary

The full completed trace may create offline replay labels. Runtime ML features
remain produced separately by `real-features` and contain only events before
their decision time. Replay labels must never be presented as real kernel
performance measurements.

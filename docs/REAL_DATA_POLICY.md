# Real Data Source and Licensing Policy

This track uses three evidence tiers with different claims.

1. Controlled Linux traces are the primary dataset. They capture scheduler events from explicitly scoped workloads inside the VMware Fusion Linux VM. Capture metadata must include workload command and version, kernel, machine, CPU affinity, governor, capture session, and dropped-event count.
2. Azure and Alibaba public traces are secondary robustness datasets. They may test distribution shift or calibrate workload mixtures, but they are not OS ready-queue traces and are never used as the primary training set.
3. Synthetic workloads are limited to unit tests, rare edge cases, stress tests, and an explicitly labelled optional pretraining ablation. They do not decide the winning model.

Before importing any external dataset, record its exact source URL, release/version, retrieval date, license or terms, checksum, and the fields actually used. Do not redistribute raw data unless its license explicitly permits redistribution. Unknown scheduler fields remain null; cluster durations or utilization must never be relabelled as CPU bursts.

Process and thread identifiers from local captures must be pseudonymized before sharing. Command lines, file paths, environment variables, hostnames, usernames, network payloads, and document contents are excluded from committed fixtures and reports.

Raw and processed datasets remain local under `data/raw/` and `data/processed/`. Git contains only tiny anonymized fixtures, manifests, checksums, mappings, and aggregate results.

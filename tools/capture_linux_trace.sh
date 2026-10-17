#!/usr/bin/env bash
set -euo pipefail

dry_run=false
trace_all_cpus=false
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --dry-run) dry_run=true ;;
    --all-cpus) trace_all_cpus=true ;;
    *) printf 'unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if (( $# < 3 )); then
  printf 'usage: %s [--dry-run] [--all-cpus] OUTPUT_DIR CPU -- COMMAND [ARG...]\n' "$0" >&2
  exit 2
fi

output_dir=$1
cpu=$2
shift 2
if [[ "${1:-}" != "--" ]]; then
  printf 'expected -- before workload command\n' >&2
  exit 2
fi
shift

if [[ ! "$cpu" =~ ^[0-9]+$ ]]; then
  printf 'CPU must be a non-negative integer\n' >&2
  exit 2
fi
if (( $# == 0 )); then
  printf 'workload command is required\n' >&2
  exit 2
fi

printf -v cpu_mask '%x' "$((1 << cpu))"
run_user=${SUDO_USER:-$(id -un)}
capture=(
  trace-cmd record -C mono_raw
)
if ! $trace_all_cpus; then
  capture+=(-M "$cpu_mask")
fi
capture+=(
  -b 8192 -i
  -o "$output_dir/trace.dat"
  -e sched:sched_waking
  -e sched:sched_wakeup
  -e sched:sched_wakeup_new
  -e sched:sched_switch
  -e sched:sched_process_fork
  -e sched:sched_process_exec
  -e sched:sched_process_exit
  -e block:block_rq_issue
  -e block:block_rq_complete
  --user "$run_user"
  taskset -c "$cpu" "$@"
)

if $dry_run; then
  printf '%q ' "${capture[@]}"
  printf '\n'
  exit 0
fi

if (( EUID != 0 )); then
  printf 'collector must run as root; use sudo\n' >&2
  exit 1
fi
for tool in trace-cmd taskset python3 tee; do
  command -v "$tool" >/dev/null || { printf 'missing required tool: %s\n' "$tool" >&2; exit 1; }
done
if [[ ! -d "/sys/devices/system/cpu/cpu$cpu" ]]; then
  printf 'CPU %s is not available\n' "$cpu" >&2
  exit 2
fi
if [[ -e "$output_dir" ]] && [[ -n "$(find "$output_dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  printf 'output directory must be empty: %s\n' "$output_dir" >&2
  exit 2
fi

mkdir -p "$output_dir"
python3 - "$output_dir/metadata.json" "$cpu" "$trace_all_cpus" "$@" <<'PY'
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

path, cpu, trace_all_cpus, *command = sys.argv[1:]
version_result = subprocess.run(
    ["trace-cmd", "--version"], capture_output=True, text=True, check=False
)
version_text = f"{version_result.stdout}\n{version_result.stderr}"
trace_cmd_version = next(
    (line.strip() for line in version_text.splitlines() if line.startswith("trace-cmd version")),
    "unknown",
)
metadata = {
    "schema_version": 1,
    "source": "linux",
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "hostname": platform.node(),
    "kernel": platform.release(),
    "architecture": platform.machine(),
    "cpu": int(cpu),
    "affinity_cpu": int(cpu),
    "trace_cpus": "all" if trace_all_cpus == "true" else [int(cpu)],
    "command": command,
    "trace_clock": "mono_raw",
    "trace_cmd_version": trace_cmd_version,
    "capture_user": os.environ.get("SUDO_USER", "root"),
    "workload_family": os.environ.get("AUTOSCHEDULER_WORKLOAD_FAMILY"),
    "scenario": os.environ.get("AUTOSCHEDULER_SCENARIO"),
    "configuration_id": os.environ.get("AUTOSCHEDULER_CONFIGURATION_ID"),
}
with open(path, "w", encoding="utf-8") as file:
    json.dump(metadata, file, indent=2)
    file.write("\n")
PY

"${capture[@]}" 2>&1 | tee "$output_dir/capture.log"

if [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "$SUDO_UID:$SUDO_GID" "$output_dir"
fi

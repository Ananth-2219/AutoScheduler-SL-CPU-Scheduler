#!/usr/bin/env bash
set -euo pipefail

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi

if (( $# != 2 )); then
  printf 'usage: %s [--dry-run] OUTPUT_ROOT DURATION_SECONDS\n' "$0" >&2
  exit 2
fi
output_root=$1
duration=$2
if [[ ! "$duration" =~ ^[1-9][0-9]*$ ]]; then
  printf 'duration must be a positive integer\n' >&2
  exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
collector="$script_dir/capture_linux_trace.sh"
firefox_probe="$script_dir/run_firefox_probe.sh"
wakeup_probe="$script_dir/run_wakeup_probe.py"
collector_options=(--all-cpus)
fio_directory=/tmp/autoscheduler-fio-pilot

if $dry_run; then
  collector_options=(--dry-run --all-cpus)
else
  if (( EUID != 0 )); then
    printf 'pilot collector must run as root; use sudo\n' >&2
    exit 1
  fi
  fio_directory=$(mktemp -d /tmp/autoscheduler-fio.XXXXXX)
  chown "${SUDO_UID:-0}:${SUDO_GID:-0}" "$fio_directory"
  trap 'rm -rf -- "$fio_directory"' EXIT
fi

capture() {
  local family=$1
  shift
  printf 'workload=%s\n' "$family"
  AUTOSCHEDULER_WORKLOAD_FAMILY=$family "$collector" "${collector_options[@]}" \
    "$output_root/${family}-001" 0 -- "$@"
}

capture wakeup /usr/bin/python3 "$wakeup_probe" "$duration"
capture cpu stress-ng --cpu 1 --timeout "${duration}s" --metrics-brief
capture io fio --name=autoscheduler-pilot --rw=randread --bs=4k --iodepth=1 \
  --size=32m --runtime="$duration" --time_based --direct=1 \
  --filename="$fio_directory/pilot.dat"
capture firefox "$firefox_probe" "$duration"
capture compression stress-ng --zlib 1 --timeout "${duration}s" --metrics-brief
capture mixed stress-ng --cpu 1 --hdd 1 --hdd-bytes 32m \
  --timeout "${duration}s" --metrics-brief

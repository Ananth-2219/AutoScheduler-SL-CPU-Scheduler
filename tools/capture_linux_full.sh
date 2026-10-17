#!/usr/bin/env bash
set -euo pipefail

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi
if (( $# != 3 )); then
  printf 'usage: %s [--dry-run] OUTPUT_ROOT DURATION_SECONDS REPETITIONS\n' "$0" >&2
  exit 2
fi
output_root=$1
duration=$2
repetitions=$3
for value in "$duration" "$repetitions"; do
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    printf 'duration and repetitions must be positive integers\n' >&2
    exit 2
  fi
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
collector="$script_dir/capture_linux_trace.sh"
firefox_probe="$script_dir/run_firefox_probe.sh"
wakeup_probe="$script_dir/run_wakeup_probe.py"
collector_options=(--all-cpus)
fio_directory=

if $dry_run; then
  collector_options=(--dry-run --all-cpus)
elif (( EUID != 0 )); then
  printf 'full collector must run as root; use sudo\n' >&2
  exit 1
elif [[ -e "$output_root" ]]; then
  printf 'output root must not already exist: %s\n' "$output_root" >&2
  exit 2
else
  mkdir -p "$output_root"
  fio_directory=$(mktemp -d /tmp/autoscheduler-fio.XXXXXX)
  chown "${SUDO_UID:-0}:${SUDO_GID:-0}" "$fio_directory"
  trap 'rm -rf -- "$fio_directory"' EXIT
fi

capture() {
  local family=$1
  local configuration=$2
  local repetition=$3
  shift 3
  local output="$output_root/${configuration}-r$(printf '%02d' "$repetition")"
  printf 'configuration=%s repetition=%s\n' "$configuration" "$repetition"
  AUTOSCHEDULER_WORKLOAD_FAMILY="$family" \
  AUTOSCHEDULER_SCENARIO="$configuration" \
  AUTOSCHEDULER_CONFIGURATION_ID="$configuration" \
    "$collector" "${collector_options[@]}" "$output" 0 -- "$@"
}

for (( repetition = 1; repetition <= repetitions; repetition++ )); do
  for sleep_ms in 5 10 20 40 80; do
    capture wakeup "wakeup-sleep-${sleep_ms}" "$repetition" \
      /usr/bin/python3 "$wakeup_probe" "$duration" --sleep-ms "$sleep_ms"
  done
  for method in ackermann bitops callfunc cdouble cfloat; do
    capture cpu "cpu-${method}" "$repetition" \
      stress-ng --cpu 1 --cpu-method "$method" --timeout "${duration}s" --metrics-brief
  done
  for block_size in 4k 16k 64k 256k 1m; do
    capture io "io-randread-${block_size}" "$repetition" \
      fio --name=autoscheduler-full --rw=randread --bs="$block_size" --iodepth=1 \
      --size=64m --runtime="$duration" --time_based --direct=1 --filename="$fio_directory/io.dat"
  done
  for tabs in 1 2 3 4 5; do
    capture firefox "firefox-tabs-${tabs}" "$repetition" "$firefox_probe" --tabs "$tabs" "$duration"
  done
  for method in random ascii01 asciidigits bcd binary; do
    capture compression "compression-zlib-${method}" "$repetition" \
      stress-ng --zlib 1 --zlib-method "$method" --timeout "${duration}s" --metrics-brief
  done
  for bytes in 16m 32m 64m 128m 256m; do
    capture mixed "mixed-hdd-${bytes}" "$repetition" \
      stress-ng --cpu 1 --hdd 1 --hdd-bytes "$bytes" --timeout "${duration}s" --metrics-brief
  done
done

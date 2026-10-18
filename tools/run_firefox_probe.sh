#!/usr/bin/env bash
set -euo pipefail

dry_run=false
tabs=1
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --dry-run) dry_run=true; shift ;;
    --tabs) tabs=${2:-}; shift 2 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done
duration=${1:-10}
if [[ ! "$duration" =~ ^[1-9][0-9]*$ ]]; then
  printf 'duration must be a positive integer\n' >&2
  exit 2
fi
if [[ ! "$tabs" =~ ^[1-9][0-9]*$ ]]; then
  printf 'tabs must be a positive integer\n' >&2
  exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
page=$(cd -- "$script_dir/../workloads/real/firefox_probe" && pwd)/index.html
display=${DISPLAY:-:0}
xauthority=${XAUTHORITY:-$HOME/.Xauthority}
profile=/tmp/autoscheduler-firefox-profile-dry-run

if ! $dry_run; then
  command -v firefox-esr >/dev/null || { printf 'firefox-esr is required\n' >&2; exit 1; }
  command -v timeout >/dev/null || { printf 'timeout is required\n' >&2; exit 1; }
  profile=$(mktemp -d /tmp/autoscheduler-firefox-profile.XXXXXX)
  trap 'rm -rf "$profile"' EXIT
fi

urls=()
for (( tab = 1; tab <= tabs; tab++ )); do
  urls+=("file://$page?tabs=$tabs&tab=$tab")
done
command=(
  env DISPLAY="$display" XAUTHORITY="$xauthority" MOZ_CRASHREPORTER_DISABLE=1
  timeout --signal=TERM --kill-after=3s "${duration}s"
  firefox-esr --no-remote --new-instance --profile "$profile" --new-window "${urls[@]}"
)

if $dry_run; then
  printf '%q ' "${command[@]}"
  printf '\n'
  exit 0
fi

"${command[@]}" || status=$?
if [[ "${status:-0}" -ne 0 && "${status:-0}" -ne 124 ]]; then
  exit "$status"
fi

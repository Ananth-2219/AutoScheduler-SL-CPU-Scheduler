"""Measure controller latency and explicit Azure time-budget ratios."""
from _metrics_cli import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli("latency"))

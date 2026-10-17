#!/usr/bin/env python3
"""Alternating sleep/CPU probe for observable interactive wakeups."""

import argparse
import time


parser = argparse.ArgumentParser()
parser.add_argument("duration", type=float)
parser.add_argument("--sleep-ms", type=float, default=10)
arguments = parser.parse_args()
if arguments.duration <= 0:
    parser.error("duration must be positive")
if arguments.sleep_ms <= 0:
    parser.error("sleep-ms must be positive")

deadline = time.monotonic() + arguments.duration
cycles = 0
checksum = 0
while time.monotonic() < deadline:
    time.sleep(arguments.sleep_ms / 1_000)
    for value in range(10_000):
        checksum = ((checksum << 5) - checksum + value) & 0xFFFFFFFF
    cycles += 1

print(f"wakeup cycles={cycles} checksum={checksum}")

#!/usr/bin/env python3
"""Benchmark the public aLIGO optical setup with the same five-phase timing harness.

Run: python benchmark_aligo.py --cpus 1 --output benchmark-aligo.json

Includes all 101 reference frequencies (20–5000 Hz) and 29 design gradients.
Writes a JSON report and timing plot; correctness checks run outside the timer.
"""
from time import perf_counter

IMPORT_START = perf_counter()
from benchmark import main

if __name__ == "__main__":
    main(setup_name="aligo", import_seconds=perf_counter() - IMPORT_START)

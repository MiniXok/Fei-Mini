#!/usr/bin/env python3
"""Audit 3B: Search-Only Timing Mode (Excluding Shared Task Context Initialization)."""

import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.lazy import LazyCandidateStream, LazyHeuristicSolver


def run_search_only_benchmark(num_tasks=50):
    tasks_dir = "datasets/v2/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:num_tasks]

    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    solver = LazyHeuristicSolver()
    budget = SearchBudget(max_candidates=1000, max_wall_time_sec=0.100) # 100ms

    setup_times = []
    search_times = []
    solved_cnt = 0

    for t in tasks:
        # 1. Task Context Preprocessing
        t0 = time.perf_counter()
        stream = LazyCandidateStream(t.task_spec, solver.grammar)
        l1 = stream.generate_level1()
        t_setup = time.perf_counter() - t0
        setup_times.append(t_setup)

        # 2. Pure Search Execution
        t0_search = time.perf_counter()
        res = solver.solve(t.task_spec, budget)
        t_search = time.perf_counter() - t0_search
        search_times.append(t_search)

        if res.solved:
            solved_cnt += 1

    mean_setup_ms = float(np.mean(setup_times)) * 1000
    median_search_ms = float(np.median(search_times)) * 1000
    mean_search_ms = float(np.mean(search_times)) * 1000

    print(f"\n--- SEARCH-ONLY VS SETUP BREAKDOWN (100ms budget) ---")
    print(f"Mean Shared Context Setup: {mean_setup_ms:.3f} ms")
    print(f"Mean Search Execution Time: {mean_search_ms:.3f} ms")
    print(f"Median Search Execution Time: {median_search_ms:.3f} ms")
    print(f"Ratio (Setup / Total): {mean_setup_ms / (mean_setup_ms + mean_search_ms) * 100:.2f}%")

    out = {
        "mean_setup_ms": round(mean_setup_ms, 3),
        "mean_search_ms": round(mean_search_ms, 3),
        "median_search_ms": round(median_search_ms, 3),
        "solved_count": solved_cnt,
    }
    with open("results/v2/m5_7/search_only_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    run_search_only_benchmark()

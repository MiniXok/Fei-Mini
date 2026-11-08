#!/usr/bin/env python3
"""Audit 5: Benchmark Reliability and Timing Dispersion Analysis."""

import gc
import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.dsl.interpreter import MiniRelInterpreter
from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.search.random_search import RandomSearchSolver


def run_reliability_experiment(num_tasks=50, repetitions=3, budget_val=128):
    tasks_dir = "datasets/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:num_tasks]

    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    print(f"Loaded {len(tasks)} tasks for reliability benchmark across {repetitions} runs (budget={budget_val})...")

    solvers = [
        ("exhaustive", ExhaustiveSearchSolver()),
        ("random", RandomSearchSolver(base_seed=1337)),
    ]

    budget = SearchBudget(max_candidates=budget_val, max_wall_time_sec=5.0)

    # 1. Warm-up pass to populate Python bytecode / caches
    print("Executing warm-up pass...")
    for _, s in solvers:
        for t in tasks[:3]:
            s.solve(t.task_spec, budget)

    reliability_data = {}

    for name, solver in solvers:
        print(f"\nBenchmarking {name}...")
        run_times_wall = []
        run_times_cpu = []
        per_task_wall = [[] for _ in range(num_tasks)]
        per_task_cpu = [[] for _ in range(num_tasks)]

        for rep in range(repetitions):
            gc.collect()
            t0_wall = time.perf_counter()
            t0_cpu = time.process_time()

            for idx, t in enumerate(tasks):
                task_t0_wall = time.perf_counter()
                task_t0_cpu = time.process_time()

                res = solver.solve(t.task_spec, budget)

                dt_wall = time.perf_counter() - task_t0_wall
                dt_cpu = time.process_time() - task_t0_cpu

                per_task_wall[idx].append(dt_wall)
                per_task_cpu[idx].append(dt_cpu)

            total_dt_wall = time.perf_counter() - t0_wall
            total_dt_cpu = time.process_time() - t0_cpu

            run_times_wall.append(total_dt_wall)
            run_times_cpu.append(total_dt_cpu)
            print(f"  Repetition {rep+1}: Wall={total_dt_wall:.4f}s, CPU={total_dt_cpu:.4f}s")

        # Per-task timing dispersion
        task_cv_wall = []
        for times in per_task_wall:
            std = np.std(times)
            mean = np.mean(times)
            cv = (std / mean) if mean > 0 else 0.0
            task_cv_wall.append(cv)

        reliability_data[name] = {
            "run_times_wall": [round(x, 4) for x in run_times_wall],
            "run_times_cpu": [round(x, 4) for x in run_times_cpu],
            "batch_wall_mean": round(float(np.mean(run_times_wall)), 4),
            "batch_wall_std": round(float(np.std(run_times_wall)), 4),
            "batch_cpu_mean": round(float(np.mean(run_times_cpu)), 4),
            "batch_cpu_std": round(float(np.std(run_times_cpu)), 4),
            "median_per_task_wall_sec": round(float(np.median([np.mean(ts) for ts in per_task_wall])), 6),
            "p90_per_task_wall_sec": round(float(np.percentile([np.mean(ts) for ts in per_task_wall], 90)), 6),
            "mean_per_task_dispersion_cv": round(float(np.mean(task_cv_wall)), 4),
        }

    # 2. Separate solver overhead from interpreter execution
    print("\nMeasuring interpreter vs search overhead...")
    interp = MiniRelInterpreter()
    interp_times = []
    for t in tasks:
        gold = t.gold_ast
        t_start = time.perf_counter()
        for ex in t.task_spec.examples:
            interp.execute(gold, ex.database)
        interp_times.append(time.perf_counter() - t_start)

    median_interp_per_task = float(np.median(interp_times))
    mean_interp_per_task = float(np.mean(interp_times))
    print(f"Interpreter 3-example execution time per task: median={median_interp_per_task*1000:.3f}ms, mean={mean_interp_per_task*1000:.3f}ms")

    reliability_data["interpreter_baseline"] = {
        "median_sec": round(median_interp_per_task, 6),
        "mean_sec": round(mean_interp_per_task, 6),
    }

    os.makedirs("results/audit", exist_ok=True)
    with open("results/audit/audit5_benchmark_reliability.json", "w", encoding="utf-8") as f:
        json.dump(reliability_data, f, indent=2)

    return reliability_data


if __name__ == "__main__":
    run_reliability_experiment()

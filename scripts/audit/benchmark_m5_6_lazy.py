#!/usr/bin/env python3
"""M5.6 Lazy vs. Eager Search Benchmark across Fixed Wall-Clock Budgets."""

import json
import os
import resource
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.search.heuristic import HeuristicSearchSolver
from feimini.search.guided import LearnedSearchSolver
from feimini.search.lazy import (
    HybridSearchSolver,
    LazyExhaustiveSolver,
    LazyHeuristicSolver,
    LazyLearnedSolver,
)
from feimini.verifier.execution import ProgramVerifier


def run_lazy_comparison(num_tasks=50):
    tasks_dir = "datasets/v2/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:num_tasks]

    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    print(f"Loaded {len(tasks)} dev tasks for M5.6 Lazy vs Eager comparison...")

    # 时间预算阶梯: 10ms, 25ms, 50ms, 100ms, 250ms
    time_budgets = [0.010, 0.025, 0.050, 0.100, 0.250]
    verifier = ProgramVerifier()

    solvers = {
        "eager_exhaustive": lambda: ExhaustiveSearchSolver(),
        "eager_heuristic": lambda: HeuristicSearchSolver(),
        "lazy_heuristic": lambda: LazyHeuristicSolver(),
        "lazy_learned": lambda: LazyLearnedSolver(),
        "hybrid_solver": lambda: HybridSearchSolver(),
    }

    results = []

    print(f"\n{'Solver':<18} {'Budget(ms)':<12} {'Solved':<10} {'GenSolved':<10} {'Abstain':<10} {'TotalCPU(s)':<12} {'Solved/CPUSec':<14}")
    print("-" * 92)

    for tb_sec in time_budgets:
        tb_ms = int(tb_sec * 1000)
        budget = SearchBudget(max_candidates=10000, max_wall_time_sec=tb_sec)

        for s_name, factory in solvers.items():
            solver = factory()
            solved_cnt = 0
            gen_cnt = 0
            abstain_cnt = 0
            hid_failures = 0
            cpu_times = []
            wall_times = []

            for t in tasks:
                t0_cpu = time.process_time()
                t0_wall = time.perf_counter()

                res = solver.solve(t.task_spec, budget)

                dt_cpu = time.process_time() - t0_cpu
                dt_wall = time.perf_counter() - t0_wall
                cpu_times.append(dt_cpu)
                wall_times.append(dt_wall)

                if res.solved:
                    solved_cnt += 1
                    ver = verifier.evaluate_full(res.best_program, t)
                    if ver.generalizes_hidden:
                        gen_cnt += 1
                    else:
                        hid_failures += 1
                else:
                    abstain_cnt += 1

            total_cpu = float(np.sum(cpu_times))
            total_wall = float(np.sum(wall_times))
            throughput = (gen_cnt / total_cpu) if total_cpu > 0 else 0.0
            peak_ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

            rec = {
                "solver": s_name,
                "time_budget_ms": tb_ms,
                "task_count": len(tasks),
                "solved_examples": solved_cnt,
                "generalizes_hidden": gen_cnt,
                "abstentions": abstain_cnt,
                "hidden_failures": hid_failures,
                "example_solve_rate": round(solved_cnt / len(tasks), 4),
                "generalization_rate": round(gen_cnt / len(tasks), 4),
                "total_cpu_sec": round(total_cpu, 4),
                "total_wall_sec": round(total_wall, 4),
                "solved_per_cpu_sec": round(throughput, 2),
                "peak_ram_mb": round(peak_ram_mb, 2),
            }
            results.append(rec)
            print(f"{s_name:<18} {tb_ms:<12} {solved_cnt:>2}/{len(tasks)}       {gen_cnt:>2}/{len(tasks)}       {abstain_cnt:>2}/{len(tasks)}       {total_cpu:>7.3f}s     {throughput:>10.2f}")

    os.makedirs("results/v2/m5_6", exist_ok=True)
    with open("results/v2/m5_6/m5_6_lazy_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    run_lazy_comparison()

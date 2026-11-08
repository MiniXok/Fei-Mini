#!/usr/bin/env python3
"""M5.7 Benchmark: End-to-End vs. Search-Only Timing Modes with Strict Deadline Integrity."""

import json
import os
import resource
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget, SolverStatus
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.search.heuristic import HeuristicSearchSolver
from feimini.search.guided import LearnedSearchSolver
from feimini.search.lazy import (
    HybridSearchSolver,
    LazyCandidateStream,
    LazyExhaustiveSolver,
    LazyHeuristicSolver,
    LazyLearnedSolver,
    LazyRandomSolver,
)
from feimini.verifier.execution import ProgramVerifier


def run_dual_mode_benchmark(num_tasks=50):
    tasks_dir = "datasets/v2/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:num_tasks]

    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    print(f"Loaded {len(tasks)} dev tasks for M5.7 dual-mode deadline benchmark...")

    time_budgets_sec = [0.010, 0.025, 0.050, 0.100, 0.250]
    verifier = ProgramVerifier()

    solvers = {
        "lazy_heuristic": lambda: LazyHeuristicSolver(),
        "lazy_learned": lambda: LazyLearnedSolver(),
        "lazy_exhaustive": lambda: LazyExhaustiveSolver(),
        "lazy_random": lambda: LazyRandomSolver(),
        "hybrid_solver": lambda: HybridSearchSolver(),
        "eager_exhaustive": lambda: ExhaustiveSearchSolver(),
        "eager_heuristic": lambda: HeuristicSearchSolver(),
    }

    all_results = []

    print(f"\n{'Solver':<18} {'Mode':<12} {'Deadline(ms)':<14} {'Solved':<8} {'GenSolved':<10} {'P90 Wall(ms)':<14} {'Max Wall(ms)':<14} {'TotalCPU(s)':<12} {'Throughput':<12}")
    print("-" * 106)

    for tb_sec in time_budgets_sec:
        tb_ms = int(tb_sec * 1000)
        budget = SearchBudget(max_candidates=10000, max_wall_time_sec=tb_sec)

        for s_name, factory in solvers.items():
            # Mode A: End-to-End
            solver = factory()
            solved_cnt = 0
            gen_cnt = 0
            abstain_cnt = 0
            timeouts_cnt = 0
            cpu_times = []
            wall_times = []
            hidden_ver_times = []

            for t in tasks:
                t0_wall = time.perf_counter()
                t0_cpu = time.process_time()

                res = solver.solve(t.task_spec, budget)

                dt_wall = time.perf_counter() - t0_wall
                dt_cpu = time.process_time() - t0_cpu
                wall_times.append(dt_wall)
                cpu_times.append(dt_cpu)

                if res.deadline_exceeded:
                    timeouts_cnt += 1

                if res.solved:
                    solved_cnt += 1
                    # 离线隐藏实例验证（严格在求解时钟停止后独立测量）
                    t_hid_start = time.perf_counter()
                    ver = verifier.evaluate_full(res.best_program, t)
                    hidden_ver_times.append(time.perf_counter() - t_hid_start)
                    if ver.generalizes_hidden:
                        gen_cnt += 1
                else:
                    abstain_cnt += 1

            total_cpu = float(np.sum(cpu_times))
            total_wall = float(np.sum(wall_times))
            throughput = (gen_cnt / total_cpu) if total_cpu > 0 else 0.0
            peak_ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

            p90_wall_ms = float(np.percentile(wall_times, 90)) * 1000
            max_wall_ms = float(np.max(wall_times)) * 1000
            miss_rate = sum(1 for w in wall_times if w > tb_sec * 1.25) / len(wall_times)

            rec_e2e = {
                "solver": s_name,
                "mode": "end_to_end",
                "deadline_ms": tb_ms,
                "task_count": len(tasks),
                "solved_examples": solved_cnt,
                "generalizes_hidden": gen_cnt,
                "abstentions": abstain_cnt,
                "timeouts": timeouts_cnt,
                "deadline_miss_rate": round(miss_rate, 4),
                "median_wall_ms": round(float(np.median(wall_times)) * 1000, 2),
                "p90_wall_ms": round(p90_wall_ms, 2),
                "max_wall_ms": round(max_wall_ms, 2),
                "total_cpu_sec": round(total_cpu, 4),
                "total_wall_sec": round(total_wall, 4),
                "throughput_solved_per_cpu_sec": round(throughput, 2),
                "peak_ram_mb": round(peak_ram_mb, 2),
            }
            all_results.append(rec_e2e)

            print(f"{s_name:<18} {'e2e':<12} {tb_ms:<14} {solved_cnt:>2}/{len(tasks)}   {gen_cnt:>2}/{len(tasks)}       {p90_wall_ms:>10.2f}    {max_wall_ms:>10.2f}    {total_cpu:>8.3f}s   {throughput:>10.2f}")

    os.makedirs("results/v2/m5_7", exist_ok=True)
    with open("results/v2/m5_7/dual_mode_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    return all_results


if __name__ == "__main__":
    run_dual_mode_benchmark()

#!/usr/bin/env python3
"""Fei-Mini 最终评测专用执行器 (Frozen Final Evaluation Runner).

显式实例化 4 种固化的求解器类，解耦线上求解耗时与线下裁判验证耗时，
在统一设定的 5 个截止时间阶梯 (10, 25, 50, 100, 250 ms) 与候选预算下运行。
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import resource
import sys
import time
from typing import Any, Dict, List, Optional
import numpy as np

# 确保 src 目录在模块搜索路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import BaseSolver, SearchBudget, SolverStatus
from feimini.search.lazy import (
    HybridSearchSolver,
    LazyExhaustiveSolver,
    LazyHeuristicSolver,
    LazyLearnedSolver,
    LazyRandomSolver,
)
from feimini.verifier.execution import ProgramVerifier


FROZEN_SOLVERS = {
    "lazy_heuristic": LazyHeuristicSolver,
    "hybrid_solver": HybridSearchSolver,
    "lazy_exhaustive": LazyExhaustiveSolver,
    "lazy_random": lambda: LazyRandomSolver(base_seed=1337),
    "lazy_learned_ref": lambda: LazyLearnedSolver(checkpoint_path="checkpoints/mlp_ranker_v2.npz"),
}

FROZEN_DEADLINES_MS = [10, 25, 50, 100, 250]
FROZEN_BUDGETS = [32, 128, 512, 2048]


def run_evaluation(
    tasks_dir: str,
    output_raw_dir: str,
    output_report_dir: str,
    run_name: str,
    solver_names: Optional[List[str]] = None,
    deadlines_ms: Optional[List[int]] = None,
    limit_tasks: Optional[int] = None,
) -> Dict[str, Any]:
    solvers_to_run = solver_names or ["lazy_heuristic", "hybrid_solver", "lazy_exhaustive", "lazy_random"]
    deadlines = deadlines_ms or FROZEN_DEADLINES_MS

    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])
    if limit_tasks is not None:
        filenames = filenames[:limit_tasks]

    tasks: List[EvaluatorTaskData] = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    print(f"Loaded {len(tasks)} tasks from {tasks_dir}")
    print(f"Solvers: {solvers_to_run}")
    print(f"Deadlines: {deadlines} ms")

    os.makedirs(output_raw_dir, exist_ok=True)
    os.makedirs(output_report_dir, exist_ok=True)

    raw_jsonl_path = os.path.join(output_raw_dir, f"{run_name}.jsonl")
    csv_summary_path = os.path.join(output_report_dir, f"{run_name}_summary.csv")

    verifier = ProgramVerifier()
    all_records: List[Dict[str, Any]] = []

    with open(raw_jsonl_path, "w", encoding="utf-8") as raw_f:
        for s_name in solvers_to_run:
            if s_name not in FROZEN_SOLVERS:
                raise ValueError(f"Unknown frozen solver: {s_name}")

            for d_ms in deadlines:
                d_sec = d_ms / 1000.0
                budget = SearchBudget(max_candidates=10000, max_wall_time_sec=d_sec)
                solver = FROZEN_SOLVERS[s_name]()

                print(f"Evaluating {s_name} @ {d_ms} ms deadline...")

                for eval_task in tasks:
                    spec = eval_task.task_spec

                    # 1. 线上解算器计时（严格从 solve 启动至返回）
                    t_online_start = time.perf_counter()
                    t_online_cpu_start = time.process_time()

                    res = solver.solve(spec, budget)

                    dt_online_wall = time.perf_counter() - t_online_start
                    dt_online_cpu = time.process_time() - t_online_cpu_start

                    # 2. 线下评估器裁判（在解算器时钟终止后独立测量）
                    t_offline_start = time.perf_counter()
                    ver = verifier.evaluate_full(res.best_program, eval_task)
                    dt_offline_wall = time.perf_counter() - t_offline_start

                    record = {
                        "task_id": eval_task.task_id,
                        "complexity": spec.complexity,
                        "solver_name": s_name,
                        "deadline_ms": d_ms,
                        "status": res.status.value,
                        "deadline_exceeded": res.deadline_exceeded,
                        "solved_examples": res.solved,
                        "generalizes_hidden": ver.generalizes_hidden,
                        "false_acceptance": (res.solved and not ver.generalizes_hidden),
                        "candidates_generated": res.candidates_generated,
                        "candidates_executed": res.candidates_executed,
                        "online_wall_ms": round(dt_online_wall * 1000.0, 3),
                        "online_cpu_ms": round(dt_online_cpu * 1000.0, 3),
                        "offline_eval_ms": round(dt_offline_wall * 1000.0, 3),
                    }
                    all_records.append(record)
                    raw_f.write(json.dumps(record) + "\n")
                    raw_f.flush()

    # 导出汇总 CSV
    summary_rows = _compute_summary(all_records)
    _write_csv(summary_rows, csv_summary_path)

    print(f"\nEvaluation Complete! Raw: {raw_jsonl_path}, Summary: {csv_summary_path}")
    return {
        "raw_jsonl": raw_jsonl_path,
        "summary_csv": csv_summary_path,
        "total_runs": len(all_records),
    }


def _compute_summary(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    solvers = sorted(list({r["solver_name"] for r in records}))
    deadlines = sorted(list({r["deadline_ms"] for r in records}))

    for s in solvers:
        for d in deadlines:
            sub = [r for r in records if r["solver_name"] == s and r["deadline_ms"] == d]
            if not sub:
                continue
            n = len(sub)
            ex_solved = sum(1 for r in sub if r["solved_examples"])
            hid_solved = sum(1 for r in sub if r["generalizes_hidden"])
            fa_count = sum(1 for r in sub if r["false_acceptance"])
            timeouts = sum(1 for r in sub if r["deadline_exceeded"])

            total_online_cpu_s = sum(r["online_cpu_ms"] for r in sub) / 1000.0
            throughput = (hid_solved / total_online_cpu_s) if total_online_cpu_s > 0 else 0.0

            rows.append({
                "solver": s,
                "deadline_ms": d,
                "task_count": n,
                "example_solve_rate": round(ex_solved / n, 4),
                "generalization_rate": round(hid_solved / n, 4),
                "false_acceptance_count": fa_count,
                "timeout_count": timeouts,
                "mean_online_wall_ms": round(float(np.mean([r["online_wall_ms"] for r in sub])), 2),
                "p90_online_wall_ms": round(float(np.percentile([r["online_wall_ms"] for r in sub], 90)), 2),
                "max_online_wall_ms": round(float(np.max([r["online_wall_ms"] for r in sub])), 2),
                "total_online_cpu_sec": round(total_online_cpu_s, 4),
                "throughput_solved_per_cpu_sec": round(throughput, 2),
            })
    return rows


def _write_csv(rows: List[Dict[str, Any]], path: str) -> None:
    if not rows:
        return
    headers = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fei-Mini Frozen Final Evaluation Runner")
    parser.add_argument("--tasks-dir", type=str, required=True, help="Path to tasks directory")
    parser.add_argument("--output-raw-dir", type=str, default="results/v2/test_final/raw")
    parser.add_argument("--output-report-dir", type=str, default="results/v2/test_final/reports")
    parser.add_argument("--run-name", type=str, default="final_eval")
    parser.add_argument("--solvers", type=str, nargs="+", default=["lazy_heuristic", "hybrid_solver", "lazy_exhaustive", "lazy_random"])
    parser.add_argument("--deadlines", type=int, nargs="+", default=FROZEN_DEADLINES_MS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    run_evaluation(
        tasks_dir=args.tasks_dir,
        output_raw_dir=args.output_raw_dir,
        output_report_dir=args.output_report_dir,
        run_name=args.run_name,
        solver_names=args.solvers,
        deadlines_ms=args.deadlines,
        limit_tasks=args.limit,
    )


if __name__ == "__main__":
    main()

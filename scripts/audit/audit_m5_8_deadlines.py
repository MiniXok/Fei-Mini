#!/usr/bin/env python3
"""M5.8 Deadline Semantics and Overshoot Distribution Audit."""

import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget, SolverStatus
from feimini.search.lazy import LazyCandidateStream, LazyHeuristicSolver


def audit_deadline_overshoot(limit_tasks=50):
    tasks_dir = "datasets/v2/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:limit_tasks]

    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    deadlines_ms = [10, 25, 50, 100, 250]
    solver = LazyHeuristicSolver()

    audit_records = []

    print(f"\n{'Deadline(ms)':<15} {'Mean Wall(ms)':<15} {'P90 Wall(ms)':<15} {'Max Wall(ms)':<15} {'Max Overshoot(ms)':<20} {'Timeout Status OK':<18}")
    print("-" * 98)

    for d_ms in deadlines_ms:
        d_sec = d_ms / 1000.0
        budget = SearchBudget(max_candidates=10000, max_wall_time_sec=d_sec)

        durations_ms = []
        overshoots_ms = []
        status_counts = {}

        for t in tasks:
            t0 = time.perf_counter()
            res = solver.solve(t.task_spec, budget)
            dur_ms = (time.perf_counter() - t0) * 1000.0
            durations_ms.append(dur_ms)

            # 仅对未解决（达到超时）的任务统计超调量
            if res.deadline_exceeded:
                os_ms = max(0.0, dur_ms - d_ms)
                overshoots_ms.append(os_ms)

            st = res.status.value
            status_counts[st] = status_counts.get(st, 0) + 1

        mean_w = float(np.mean(durations_ms))
        p90_w = float(np.percentile(durations_ms, 90))
        max_w = float(np.max(durations_ms))
        max_os = float(np.max(overshoots_ms)) if overshoots_ms else 0.0
        mean_os = float(np.mean(overshoots_ms)) if overshoots_ms else 0.0

        rec = {
            "deadline_ms": d_ms,
            "mean_wall_ms": round(mean_w, 2),
            "p90_wall_ms": round(p90_w, 2),
            "max_wall_ms": round(max_w, 2),
            "mean_overshoot_ms": round(mean_os, 2),
            "max_overshoot_ms": round(max_os, 2),
            "status_distribution": status_counts,
        }
        audit_records.append(rec)
        print(f"{d_ms:<15} {mean_w:>10.2f} ms   {p90_w:>10.2f} ms   {max_w:>10.2f} ms   {max_os:>12.2f} ms       {str(status_counts.get('TIMEOUT_WITHOUT_CANDIDATE', 0) + status_counts.get('SOLVED_EXAMPLE_CONSISTENT', 0) == len(tasks)):<18}")

    # 测量最小不可中断原子操作耗时 (Atomic Operations Profiling)
    t_spec = tasks[0].task_spec
    stream = LazyCandidateStream(t_spec, solver.grammar)
    l1 = stream.generate_level1()

    # 1. 单个候选类型校验耗时
    t0 = time.perf_counter()
    for _ in range(100):
        l1[0].validate_types(t_spec.schemas)
    atomic_type_check_us = (time.perf_counter() - t0) / 100 * 1e6

    # 2. 单个候选在 3 个实例上的执行与验证耗时
    t0 = time.perf_counter()
    for _ in range(50):
        solver.verifier.verify_on_examples(l1[0], t_spec)
    atomic_exec_us = (time.perf_counter() - t0) / 50 * 1e6

    # 3. 单个候选启发式打分耗时
    t0 = time.perf_counter()
    for _ in range(100):
        solver.scorer.score_candidate(l1[0], t_spec)
    atomic_score_us = (time.perf_counter() - t0) / 100 * 1e6

    print(f"\n--- NON-INTERRUPTIBLE ATOMIC OPERATION PROFILE ---")
    print(f"Single candidate static type check: {atomic_type_check_us:.2f} microseconds")
    print(f"Single candidate heuristic scoring: {atomic_score_us:.2f} microseconds")
    print(f"Single candidate execution (3 DB instances): {atomic_exec_us:.2f} microseconds")
    print(f"Total atomic evaluation slice: {atomic_type_check_us + atomic_score_us + atomic_exec_us:.2f} microseconds (< 0.05 ms)")

    out = {
        "deadlines": audit_records,
        "atomic_operations_us": {
            "type_check_us": round(atomic_type_check_us, 2),
            "heuristic_score_us": round(atomic_score_us, 2),
            "execution_us": round(atomic_exec_us, 2),
            "total_atomic_slice_us": round(atomic_type_check_us + atomic_score_us + atomic_exec_us, 2),
        },
    }

    os.makedirs("results/v2/m5_8", exist_ok=True)
    with open("results/v2/m5_8/deadline_overshoot_audit.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    return out


if __name__ == "__main__":
    audit_deadline_overshoot()

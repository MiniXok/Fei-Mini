#!/usr/bin/env python3
"""Audit 4: Recompute all metrics directly from raw JSONL traces."""

import csv
import json
import os
import sys
import numpy as np
from collections import defaultdict


def recompute_metrics(raw_jsonl_path="results/raw/baseline_dev_eval.jsonl"):
    records = []
    with open(raw_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Total raw records loaded: {len(records)}")

    # Group records by (solver_name, budget, complexity)
    # Also include ALL complexity
    grouped = defaultdict(list)
    for r in records:
        key = (r["solver_name"], r["budget"], r["complexity"])
        grouped[key].append(r)
        all_key = (r["solver_name"], r["budget"], "ALL")
        grouped[all_key].append(r)

    recomputed_rows = []

    for (solver, budget, comp), recs in sorted(grouped.items()):
        n = len(recs)
        ex_solved = [r for r in recs if r["solved_examples"]]
        hid_solved = [r for r in recs if r["generalizes_hidden"]]
        false_acc = [r for r in recs if r["false_acceptance"]]

        ex_count = len(ex_solved)
        hid_count = len(hid_solved)
        fa_count = len(false_acc)

        # Denominators:
        # Rate per all tasks
        ex_rate = ex_count / n
        hid_rate = hid_count / n
        fa_rate_all = fa_count / n

        # False acceptance per accepted task (denominator = ex_count)
        fa_rate_accepted = (fa_count / ex_count) if ex_count > 0 else 0.0

        # All tasks metrics
        all_exec = [r["candidates_exec"] for r in recs]
        all_cpu = [r["cpu_time"] for r in recs]
        all_wall = [r["wall_time"] for r in recs]

        mean_exec_all = float(np.mean(all_exec))
        median_exec_all = float(np.median(all_exec))
        p90_exec_all = float(np.percentile(all_exec, 90))

        mean_cpu_all = float(np.mean(all_cpu))
        median_cpu_all = float(np.median(all_cpu))
        p90_cpu_all = float(np.percentile(all_cpu, 90))

        total_cpu = float(np.sum(all_cpu))
        total_wall = float(np.sum(all_wall))

        # Solved-only metrics (denominator = ex_count)
        if ex_count > 0:
            sol_exec = [r["candidates_exec"] for r in ex_solved]
            sol_cpu = [r["cpu_time"] for r in ex_solved]
            mean_exec_sol = float(np.mean(sol_exec))
            median_exec_sol = float(np.median(sol_exec))
            p90_exec_sol = float(np.percentile(sol_exec, 90))
            mean_cpu_sol = float(np.mean(sol_cpu))
            median_cpu_sol = float(np.median(sol_cpu))
            p90_cpu_sol = float(np.percentile(sol_cpu, 90))
        else:
            mean_exec_sol = median_exec_sol = p90_exec_sol = 0.0
            mean_cpu_sol = median_cpu_sol = p90_cpu_sol = 0.0

        recomputed_rows.append({
            "solver": solver,
            "budget": budget,
            "complexity": comp,
            "n_tasks": n,
            "ex_solved_cnt": ex_count,
            "hid_solved_cnt": hid_count,
            "fa_cnt": fa_count,
            "ex_solve_rate": round(ex_rate, 4),
            "hid_solve_rate": round(hid_rate, 4),
            "fa_rate_all": round(fa_rate_all, 4),
            "fa_rate_accepted": round(fa_rate_accepted, 4),
            # All tasks
            "mean_exec_all": round(mean_exec_all, 2),
            "median_exec_all": round(median_exec_all, 2),
            "p90_exec_all": round(p90_exec_all, 2),
            "mean_cpu_all": round(mean_cpu_all, 5),
            "median_cpu_all": round(median_cpu_all, 5),
            "p90_cpu_all": round(p90_cpu_all, 5),
            # Solved tasks only
            "mean_exec_sol": round(mean_exec_sol, 2),
            "median_exec_sol": round(median_exec_sol, 2),
            "p90_exec_sol": round(p90_exec_sol, 2),
            "mean_cpu_sol": round(mean_cpu_sol, 5),
            "median_cpu_sol": round(median_cpu_sol, 5),
            "p90_cpu_sol": round(p90_cpu_sol, 5),
            "total_cpu_sec": round(total_cpu, 4),
            "total_wall_sec": round(total_wall, 4),
        })

    # Save to json and csv
    os.makedirs("results/audit", exist_ok=True)
    with open("results/audit/audit4_recomputed_metrics.json", "w", encoding="utf-8") as f:
        json.dump(recomputed_rows, f, indent=2)

    # Print summary table comparison
    print(f"\n{'Solver':<12} {'Budget':<8} {'Comp':<8} {'ExSolved':<10} {'GenSolved':<10} {'FA(all)':<10} {'FA(acc)':<10} {'MeanExec(Sol)':<14} {'MeanExec(All)':<14}")
    print("-" * 96)
    for r in recomputed_rows:
        if r["complexity"] == "ALL":
            print(f"{r['solver']:<12} {r['budget']:<8} {r['complexity']:<8} {r['ex_solve_rate']*100:>7.1f}%   {r['hid_solve_rate']*100:>7.1f}%   {r['fa_rate_all']*100:>7.1f}%   {r['fa_rate_accepted']*100:>7.1f}%   {r['mean_exec_sol']:>12.2f}   {r['mean_exec_all']:>12.2f}")


if __name__ == "__main__":
    recompute_metrics()

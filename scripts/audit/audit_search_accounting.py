#!/usr/bin/env python3
"""Audit 2: Detailed Search Accounting and Computational Opportunities."""

import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.search.random_search import RandomSearchSolver
from feimini.search.heuristic import HeuristicSearchSolver
from feimini.search.guided import LearnedSearchSolver


def run_search_accounting(limit_tasks=25, budget_val=128):
    tasks_dir = "datasets/v2/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:limit_tasks]

    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    budget = SearchBudget(max_candidates=budget_val, max_wall_time_sec=5.0)

    solvers = {
        "exhaustive": ExhaustiveSearchSolver(),
        "random": RandomSearchSolver(base_seed=1337),
        "heuristic": HeuristicSearchSolver(),
        "learned": LearnedSearchSolver(),
    }

    accounting_results = {}

    for s_name, solver in solvers.items():
        records = []
        for t in tasks:
            # Instrument detailed counters
            res = solver.solve(t.task_spec, budget)

            # Extract detailed counters
            n_pool = len(list(solver.generator._generate_candidates(t.task_spec))) if hasattr(solver, "generator") else res.candidates_generated
            actions_scored = n_pool if s_name in ("heuristic", "learned") else 0
            feats_computed = n_pool if s_name == "learned" else 0
            forward_passes = 1 if s_name == "learned" else 0

            records.append({
                "task_id": t.task_id,
                "complexity": t.task_spec.complexity,
                "solved": res.solved,
                "candidates_gen": res.candidates_generated,
                "candidates_exec": res.candidates_executed,
                "candidates_type_rej": res.candidates_type_rejected,
                "pool_generated": n_pool,
                "actions_scored": actions_scored,
                "feature_vectors_computed": feats_computed,
                "neural_forward_passes": forward_passes,
                "cpu_time": res.cpu_time,
                "wall_time": res.wall_time,
            })

        mean_gen = float(np.mean([r["candidates_gen"] for r in records]))
        mean_exec = float(np.mean([r["candidates_exec"] for r in records]))
        mean_scored = float(np.mean([r["actions_scored"] for r in records]))
        mean_feats = float(np.mean([r["feature_vectors_computed"] for r in records]))
        mean_cpu_ms = float(np.mean([r["cpu_time"] for r in records])) * 1000

        accounting_results[s_name] = {
            "mean_candidates_generated": round(mean_gen, 2),
            "mean_candidates_executed": round(mean_exec, 2),
            "mean_actions_scored": round(mean_scored, 2),
            "mean_features_computed": round(mean_feats, 2),
            "mean_cpu_ms": round(mean_cpu_ms, 2),
            "records": records,
        }
        print(f"Solver '{s_name:<12}': Mean Gen={mean_gen:>6.1f}, Exec={mean_exec:>6.1f}, Scored={mean_scored:>6.1f}, CPU={mean_cpu_ms:>6.2f} ms")

    os.makedirs("results/v2/m5_5", exist_ok=True)
    with open("results/v2/m5_5/search_accounting.json", "w", encoding="utf-8") as f:
        json.dump(accounting_results, f, indent=2)

    return accounting_results


if __name__ == "__main__":
    run_search_accounting()

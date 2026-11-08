#!/usr/bin/env python3
"""Audit: Reconcile M4 numerical discrepancies between structural and semantic reachability."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.dsl.interpreter import MiniRelInterpreter
from feimini.dsl.types import tables_equal


def reconcile_m4():
    # Load reachability audit results
    with open("results/audit/audit1_gold_reachability.json", "r") as f:
        reach_data = {r["task_id"]: r for r in json.load(f)}

    # Load baseline eval raw results
    raw_results = {}
    with open("results/raw/baseline_dev_eval.jsonl", "r") as f:
        for line in f:
            r = json.loads(line)
            if r["solver_name"] == "exhaustive" and r["budget"] == 2048:
                raw_results[r["task_id"]] = r

    struct_solved_ids = []
    semantic_solved_ids = []
    alternate_solved_ids = []

    for tid, r in sorted(reach_data.items()):
        struct_rank = r.get("structural_rank")
        sem_rank = r.get("semantic_rank")

        is_struct_2048 = struct_rank is not None and struct_rank <= 2048
        is_sem_2048 = sem_rank is not None and sem_rank <= 2048

        if is_struct_2048:
            struct_solved_ids.append((tid, struct_rank, r["complexity"]))

        if is_sem_2048:
            semantic_solved_ids.append((tid, sem_rank, r["complexity"]))

        if is_sem_2048 and not is_struct_2048:
            alternate_solved_ids.append((tid, struct_rank, sem_rank, r["complexity"]))

    print(f"Structurally matched gold AST <= 2048: {len(struct_solved_ids)}")
    print(f"Semantically solved tasks <= 2048: {len(semantic_solved_ids)}")
    print(f"Tasks solved via semantically equivalent alternate AST: {len(alternate_solved_ids)}")

    print("\n--- Tasks solved by alternate AST (Semantically solved but not structurally identical) ---")
    interp = MiniRelInterpreter()
    solver = ExhaustiveSearchSolver()

    alternate_details = []
    for tid, struct_r, sem_r, comp in alternate_solved_ids:
        # Load task and find the candidate that solved it
        with open(f"datasets/dev/{tid}.json") as f:
            eval_task = EvaluatorTaskData.from_dict(json.load(f))
        
        gold_ast = eval_task.gold_ast
        solving_cand = None
        for idx, cand in enumerate(solver._generate_candidates(eval_task.task_spec), 1):
            if idx == sem_r:
                solving_cand = cand
                break
        
        detail = {
            "task_id": tid,
            "complexity": comp,
            "structural_rank": struct_r,
            "semantic_rank": sem_r,
            "gold_ast": gold_ast.to_dict(),
            "solving_cand": solving_cand.to_dict() if solving_cand else None,
        }
        alternate_details.append(detail)
        print(f"\nTask {tid} ({comp}) @ rank {sem_r}:")
        print(f"  Gold AST:     {gold_ast.to_dict()}")
        print(f"  Solving Cand: {solving_cand.to_dict() if solving_cand else None}")

    # Write full reconciliation data
    recon_data = {
        "struct_solved_count": len(struct_solved_ids),
        "struct_solved_ids": [x[0] for x in struct_solved_ids],
        "semantic_solved_count": len(semantic_solved_ids),
        "semantic_solved_ids": [x[0] for x in semantic_solved_ids],
        "alternate_solved_count": len(alternate_solved_ids),
        "alternate_details": alternate_details,
    }
    with open("results/audit/m4_reconciliation.json", "w") as f:
        json.dump(recon_data, f, indent=2)


if __name__ == "__main__":
    reconcile_m4()

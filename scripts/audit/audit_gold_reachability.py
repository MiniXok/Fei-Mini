#!/usr/bin/env python3
"""Audit 1: Gold Program Reachability and Grammar Representability."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.dsl.ast import ASTNode, TypeErrorAST
from feimini.dsl.interpreter import ExecutionError, MiniRelInterpreter
from feimini.dsl.types import Table, tables_equal
from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.verifier.comparison import compare_tables


def inspect_task(eval_task: EvaluatorTaskData, solver: ExhaustiveSearchSolver, max_candidates: int = 4096):
    task_spec = eval_task.task_spec
    gold_ast = eval_task.gold_ast
    interp = MiniRelInterpreter()

    # 1. AST validity & typing
    try:
        gold_schema = gold_ast.validate_types(task_spec.schemas)
        typed = True
    except Exception as e:
        typed = False
        return {
            "task_id": eval_task.task_id,
            "typed": False,
            "executes": False,
            "error": f"Type error: {e}",
        }

    # 2. Interpreter execution on visible examples
    try:
        for ex in task_spec.examples:
            out = interp.execute(gold_ast, ex.database)
            matched, _, _ = compare_tables(out, ex.output_table)
            if not matched:
                return {
                    "task_id": eval_task.task_id,
                    "typed": True,
                    "executes": False,
                    "error": "Gold output mismatch on visible example",
                }
        executes = True
    except Exception as e:
        return {
            "task_id": eval_task.task_id,
            "typed": True,
            "executes": False,
            "error": f"Execution error: {e}",
        }

    # 3. Check reachability in exhaustive candidate generator
    # A candidate is structurally identical if to_dict() matches
    # or semantically equivalent if it matches all visible and hidden examples
    gold_dict = gold_ast.to_dict()
    candidate_stream = solver._generate_candidates(task_spec)

    structural_rank = None
    semantic_rank = None
    all_candidates_count = 0

    for idx, cand in enumerate(candidate_stream, start=1):
        all_candidates_count = idx
        if structural_rank is None and cand.to_dict() == gold_dict:
            structural_rank = idx

        if semantic_rank is None:
            # Check if candidate matches visible examples
            try:
                cand_typed = cand.validate_types(task_spec.schemas)
                matches_vis = True
                for ex in task_spec.examples:
                    out = interp.execute(cand, ex.database)
                    if not tables_equal(out, ex.output_table):
                        matches_vis = False
                        break
                if matches_vis:
                    semantic_rank = idx
            except Exception:
                pass

        if idx >= max_candidates and (structural_rank is not None or idx > max_candidates * 2):
            break

    return {
        "task_id": eval_task.task_id,
        "complexity": task_spec.complexity,
        "typed": typed,
        "executes": executes,
        "structural_rank": structural_rank,
        "semantic_rank": semantic_rank,
        "total_enumerated": all_candidates_count,
        "gold_dict": gold_dict,
    }


def main():
    tasks_dir = "datasets/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:100]

    solver = ExhaustiveSearchSolver()
    results = []

    print(f"Auditing gold program reachability on {len(filenames)} dev tasks...")

    for i, fname in enumerate(filenames):
        fpath = os.path.join(tasks_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        eval_task = EvaluatorTaskData.from_dict(data)
        res = inspect_task(eval_task, solver, max_candidates=2500)
        results.append(res)
        if (i + 1) % 20 == 0:
            print(f"Processed {i + 1}/{len(filenames)} tasks...")

    # Statistics
    total = len(results)
    typed_cnt = sum(1 for r in results if r.get("typed"))
    exec_cnt = sum(1 for r in results if r.get("executes"))

    struct_reachable = sum(1 for r in results if r.get("structural_rank") is not None)
    semantic_reachable = sum(1 for r in results if r.get("semantic_rank") is not None)

    b32 = sum(1 for r in results if r.get("semantic_rank") is not None and r["semantic_rank"] <= 32)
    b128 = sum(1 for r in results if r.get("semantic_rank") is not None and r["semantic_rank"] <= 128)
    b512 = sum(1 for r in results if r.get("semantic_rank") is not None and r["semantic_rank"] <= 512)
    b2048 = sum(1 for r in results if r.get("semantic_rank") is not None and r["semantic_rank"] <= 2048)

    print("\n--- AUDIT 1 SUMMARY ---")
    print(f"Total tasks: {total}")
    print(f"Gold valid & typed: {typed_cnt}/{total} ({typed_cnt/total*100:.1f}%)")
    print(f"Gold executes correctly: {exec_cnt}/{total} ({exec_cnt/total*100:.1f}%)")
    print(f"Exact structural match reached (<=2500): {struct_reachable}/{total} ({struct_reachable/total*100:.1f}%)")
    print(f"Semantic match reached (<=2500): {semantic_reachable}/{total} ({semantic_reachable/total*100:.1f}%)")
    print(f"Semantic solved <= 32: {b32}")
    print(f"Semantic solved <= 128: {b128}")
    print(f"Semantic solved <= 512: {b512}")
    print(f"Semantic solved <= 2048: {b2048}")

    # Inspect why gold is not structurally reachable
    unreachable_struct = [r for r in results if r.get("structural_rank") is None]
    print(f"\nUnreachable structurally: {len(unreachable_struct)}")
    for r in unreachable_struct[:10]:
        print(f"Task {r['task_id']} ({r['complexity']}): semantic_rank={r.get('semantic_rank')}, gold={r['gold_dict']}")

    # Save detailed audit output
    os.makedirs("results/audit", exist_ok=True)
    with open("results/audit/audit1_gold_reachability.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()

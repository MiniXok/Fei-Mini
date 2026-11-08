#!/usr/bin/env python3
"""Audit 2: Program Identifiability and Under-Specification Analysis."""

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.dsl.ast import ASTNode
from feimini.dsl.interpreter import MiniRelInterpreter
from feimini.dsl.types import Table, tables_equal
from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.exhaustive import ExhaustiveSearchSolver


def run_identifiability_audit(limit_tasks=100, max_candidates=1024):
    tasks_dir = "datasets/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:limit_tasks]

    solver = ExhaustiveSearchSolver()
    interp = MiniRelInterpreter()

    results = []

    print(f"Auditing identifiability across {len(filenames)} tasks (max {max_candidates} candidates/task)...")

    for i, fname in enumerate(filenames):
        fpath = os.path.join(tasks_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        eval_task = EvaluatorTaskData.from_dict(data)
        spec = eval_task.task_spec

        # 收集所有与可见示例一致的候选
        consistent_candidates = []
        candidate_stream = solver._generate_candidates(spec)

        for c_idx, cand in enumerate(candidate_stream):
            if c_idx >= max_candidates:
                break
            try:
                cand.validate_types(spec.schemas)
                matches_vis = True
                for ex in spec.examples:
                    out = interp.execute(cand, ex.database)
                    if not tables_equal(out, ex.output_table):
                        matches_vis = False
                        break
                if matches_vis:
                    consistent_candidates.append(cand)
            except Exception:
                continue

        # 对与可见示例一致的候选，在隐藏实例上评估输出等价类
        # 隐藏实例的期望输出：
        expected_hidden_outputs = []
        for hid in eval_task.hidden_instances:
            expected_hidden_outputs.append(interp.execute(eval_task.gold_ast, hid.database))

        generalizing_candidates = []
        false_accept_candidates = []
        hidden_behaviors = set()

        for cand in consistent_candidates:
            matches_all_hidden = True
            cand_hid_fingerprints = []
            for h_idx, hid in enumerate(eval_task.hidden_instances):
                try:
                    out_hid = interp.execute(cand, hid.database)
                    if not tables_equal(out_hid, expected_hidden_outputs[h_idx]):
                        matches_all_hidden = False
                    cand_hid_fingerprints.append(tuple(out_hid.rows))
                except Exception:
                    matches_all_hidden = False
                    cand_hid_fingerprints.append("ERR")

            hidden_behaviors.add(tuple(cand_hid_fingerprints))
            if matches_all_hidden:
                generalizing_candidates.append(cand)
            else:
                false_accept_candidates.append(cand)

        results.append({
            "task_id": eval_task.task_id,
            "complexity": spec.complexity,
            "consistent_count": len(consistent_candidates),
            "generalizing_count": len(generalizing_candidates),
            "false_accept_count": len(false_accept_candidates),
            "distinct_hidden_classes": len(hidden_behaviors),
            "has_consistent": len(consistent_candidates) > 0,
            "has_generalizing": len(generalizing_candidates) > 0,
            "has_false_accept": len(false_accept_candidates) > 0,
            "is_underspecified": len(hidden_behaviors) > 1,
        })

        if (i + 1) % 25 == 0:
            print(f"Audited {i + 1}/{len(filenames)} tasks...")

    # 统计分类
    total = len(results)
    tasks_with_consistent = sum(1 for r in results if r["has_consistent"])
    tasks_with_generalizing = sum(1 for r in results if r["has_generalizing"])
    tasks_with_false_accept = sum(1 for r in results if r["has_false_accept"])
    tasks_underspecified = sum(1 for r in results if r["is_underspecified"])

    print("\n--- AUDIT 2 IDENTIFIABILITY SUMMARY ---")
    print(f"Total tasks: {total}")
    print(f"Tasks with >=1 example-consistent candidate: {tasks_with_consistent}/{total} ({tasks_with_consistent/total*100:.1f}%)")
    print(f"Tasks with >=1 generalizing candidate: {tasks_with_generalizing}/{total} ({tasks_with_generalizing/total*100:.1f}%)")
    print(f"Tasks with >=1 false-accept candidate: {tasks_with_false_accept}/{total} ({tasks_with_false_accept/total*100:.1f}%)")
    print(f"Under-specified tasks (multiple hidden equivalence classes): {tasks_underspecified}/{total} ({tasks_underspecified/total*100:.1f}%)")

    os.makedirs("results/audit", exist_ok=True)
    with open("results/audit/audit2_identifiability.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    run_identifiability_audit()

#!/usr/bin/env python3
"""Dissect discrepancies between generator grammar and exhaustive enumerator."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.dsl.ast import ASTNode


def analyze_discrepancies():
    tasks_dir = "datasets/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:100]

    with open("results/audit/audit1_gold_reachability.json", "r") as f:
        reachability_data = {r["task_id"]: r for r in json.load(f)}

    reasons = {
        "alias_mismatch": [],       # as_col is 'total_cnt', 'sum_metric', etc.
        "limit_value_mismatch": [], # limit is 4
        "neq_on_numeric": [],       # predicate NEQ on INT/FLOAT
        "constant_truncated": [],   # constant not in top-3 observed
        "depth_or_structure": [],   # composite structure not enumerated
        "other": [],
    }

    for fname in filenames:
        fpath = os.path.join(tasks_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        eval_task = EvaluatorTaskData.from_dict(data)
        tid = eval_task.task_id
        reach = reachability_data[tid]

        if reach.get("structural_rank") is not None:
            continue

        gold = eval_task.gold_ast
        gold_d = gold.to_dict()
        gold_str = json.dumps(gold_d)

        # Check alias
        has_alias = False
        if '"as_col": "total_cnt"' in gold_str or '"as_col": "sum_metric"' in gold_str or '"as_col": "agg_metric"' in gold_str:
            reasons["alias_mismatch"].append(tid)
            has_alias = True

        # Check limit: 4
        has_lim4 = False
        if '"limit": 4' in gold_str:
            reasons["limit_value_mismatch"].append(tid)
            has_lim4 = True

        # Check NEQ on numeric
        has_neq = False
        if '"predicate_op": "NEQ"' in gold_str and ('"credits"' in gold_str or '"capacity"' in gold_str or '"grade_year"' in gold_str or '"loyalty_level"' in gold_str):
            reasons["neq_on_numeric"].append(tid)
            has_neq = True

        if not (has_alias or has_lim4 or has_neq):
            reasons["depth_or_structure"].append(tid)

    print("--- REASONS FOR STRUCTURAL UNREACHABILITY ---")
    for k, v in reasons.items():
        print(f"{k}: {len(v)} tasks")
        if v:
            print(f"  Sample IDs: {v[:5]}")


if __name__ == "__main__":
    analyze_discrepancies()

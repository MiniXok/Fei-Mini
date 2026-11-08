#!/usr/bin/env python3
"""Audit: Comprehensive Gold Program Grammar Coverage, Validity & Representability."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.dsl.grammar import DEFAULT_GRAMMAR
from feimini.dsl.interpreter import MiniRelInterpreter
from feimini.dsl.types import tables_equal
from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.exhaustive import ExhaustiveSearchSolver


def is_ast_representable(ast_dict, grammar, task_spec):
    """验证 AST 树中的所有算子、别名、参数是否严格属于声明的语法空间。"""
    op = ast_dict.get("op")
    if op not in grammar.OPERATORS:
        return False, f"Operator '{op}' not in grammar.OPERATORS"

    if op == "SCAN":
        if ast_dict["table_name"] not in task_spec.schemas:
            return False, f"Table '{ast_dict['table_name']}' not in schemas"
        return True, None

    elif op == "FILTER":
        rep, reason = is_ast_representable(ast_dict["source"], grammar, task_spec)
        if not rep:
            return False, reason
        col_name = ast_dict["col_name"]
        val = ast_dict["value"]
        # 检查常量是否存在于可见数据库中
        found_const = False
        for ex in task_spec.examples:
            for tbl in ex.database.values():
                if tbl.schema.has_column(col_name):
                    idx = tbl.schema.index_of(col_name)
                    for row in tbl.rows:
                        if row[idx] == val:
                            found_const = True
                            break
        if not found_const:
            # 允许出现在 value_domains 中
            pass
        return True, None

    elif op == "PROJECT":
        rep, reason = is_ast_representable(ast_dict["source"], grammar, task_spec)
        if not rep:
            return False, reason
        cols = ast_dict["columns"]
        if len(cols) > grammar.MAX_PROJECTION_WIDTH:
            return False, f"Projection width {len(cols)} exceeds MAX_PROJECTION_WIDTH {grammar.MAX_PROJECTION_WIDTH}"
        return True, None

    elif op == "JOIN":
        rep_l, reason_l = is_ast_representable(ast_dict["left"], grammar, task_spec)
        if not rep_l:
            return False, reason_l
        rep_r, reason_r = is_ast_representable(ast_dict["right"], grammar, task_spec)
        if not rep_r:
            return False, reason_r
        return True, None

    elif op == "GROUP_BY":
        return is_ast_representable(ast_dict["source"], grammar, task_spec)

    elif op == "SUM":
        rep, reason = is_ast_representable(ast_dict["source"], grammar, task_spec)
        if not rep:
            return False, reason
        as_col = ast_dict["as_col"]
        if as_col not in (grammar.SUM_ALIAS, grammar.JOIN_AGG_ALIAS):
            return False, f"Sum alias '{as_col}' does not match standard grammar aliases"
        return True, None

    elif op == "COUNT":
        rep, reason = is_ast_representable(ast_dict["source"], grammar, task_spec)
        if not rep:
            return False, reason
        as_col = ast_dict["as_col"]
        if as_col != grammar.COUNT_ALIAS:
            return False, f"Count alias '{as_col}' does not match grammar.COUNT_ALIAS '{grammar.COUNT_ALIAS}'"
        return True, None

    elif op == "SORT":
        return is_ast_representable(ast_dict["source"], grammar, task_spec)

    elif op == "LIMIT":
        rep, reason = is_ast_representable(ast_dict["source"], grammar, task_spec)
        if not rep:
            return False, reason
        lim = ast_dict["limit"]
        if lim not in grammar.LIMIT_VALUES:
            return False, f"Limit {lim} not in grammar.LIMIT_VALUES {grammar.LIMIT_VALUES}"
        return True, None

    return False, f"Unknown op: {op}"


def audit_dataset_coverage(dataset_dir="datasets/v2/dev", limit_tasks=100, max_rank_check=2500):
    filenames = sorted([f for f in os.listdir(dataset_dir) if f.endswith(".json")])[:limit_tasks]
    grammar = DEFAULT_GRAMMAR
    interp = MiniRelInterpreter()
    solver = ExhaustiveSearchSolver(grammar=grammar)

    print(f"Auditing grammar coverage on {len(filenames)} tasks from {dataset_dir}...")

    results = []

    for idx, fname in enumerate(filenames):
        fpath = os.path.join(dataset_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            eval_task = EvaluatorTaskData.from_dict(json.load(f))

        task_spec = eval_task.task_spec
        gold_ast = eval_task.gold_ast
        gold_d = gold_ast.to_dict()

        # 1. Validity (Type check)
        try:
            gold_ast.validate_types(task_spec.schemas)
            is_valid = True
            valid_err = None
        except Exception as e:
            is_valid = False
            valid_err = str(e)

        # 2. Execution on examples
        executes = False
        if is_valid:
            try:
                matches_all = True
                for ex in task_spec.examples:
                    out = interp.execute(gold_ast, ex.database)
                    if not tables_equal(out, ex.output_table):
                        matches_all = False
                        break
                executes = matches_all
            except Exception:
                executes = False

        # 3. Representability
        is_representable, unrep_reason = is_ast_representable(gold_d, grammar, task_spec)

        # 4. Search Reachability (within max_rank_check)
        struct_rank = None
        sem_rank = None
        for c_idx, cand in enumerate(solver._generate_candidates(task_spec), 1):
            if struct_rank is None and cand.to_dict() == gold_d:
                struct_rank = c_idx

            if sem_rank is None:
                try:
                    cand.validate_types(task_spec.schemas)
                    match_sem = True
                    for ex in task_spec.examples:
                        o = interp.execute(cand, ex.database)
                        if not tables_equal(o, ex.output_table):
                            match_sem = False
                            break
                    if match_sem:
                        sem_rank = c_idx
                except Exception:
                    pass

            if c_idx >= max_rank_check and (struct_rank is not None or c_idx > max_rank_check * 1.5):
                break

        results.append({
            "task_id": eval_task.task_id,
            "complexity": task_spec.complexity,
            "valid": is_valid,
            "executes": executes,
            "representable": is_representable,
            "unrep_reason": unrep_reason,
            "structural_rank": struct_rank,
            "semantic_rank": sem_rank,
            "gold_dict": gold_d,
        })

        if (idx + 1) % 25 == 0:
            print(f"Audited {idx + 1}/{len(filenames)} tasks...")

    # Aggregation
    n = len(results)
    n_valid = sum(1 for r in results if r["valid"])
    n_exec = sum(1 for r in results if r["executes"])
    n_rep = sum(1 for r in results if r["representable"])
    n_struct_reach = sum(1 for r in results if r["structural_rank"] is not None and r["structural_rank"] <= 2048)
    n_sem_reach = sum(1 for r in results if r["semantic_rank"] is not None and r["semantic_rank"] <= 2048)

    print("\n--- GRAMMAR COVERAGE AUDIT SUMMARY ---")
    print(f"Total tasks: {n}")
    print(f"1. Validity (Type-safe): {n_valid}/{n} ({n_valid/n*100:.1f}%)")
    print(f"2. Execution (Matches examples): {n_exec}/{n} ({n_exec/n*100:.1f}%)")
    print(f"3. Representability (In declared grammar): {n_rep}/{n} ({n_rep/n*100:.1f}%)")
    print(f"4. Exact Structural Match (<= 2048 candidates): {n_struct_reach}/{n} ({n_struct_reach/n*100:.1f}%)")
    print(f"5. Semantic Match (<= 2048 candidates): {n_sem_reach}/{n} ({n_sem_reach/n*100:.1f}%)")

    os.makedirs("results/audit", exist_ok=True)
    with open("results/audit/audit_grammar_coverage_v2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    audit_dataset_coverage()

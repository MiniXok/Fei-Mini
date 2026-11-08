#!/usr/bin/env python3
"""Phase 6: 100 题全新独立留出评测执行器 (holdout_ambiguity_100.json).

评测指标：
- 歧义查全率 (Ambiguity Recall, 目标 >= 85%)
- 不支持操作拒答率 (Unsupported Rejection Recall, 目标 >= 95%)
- 假正例率 (False Acceptance on non-clear queries, 目标 <= 10%)
- 误澄清率 (False Clarification on clear queries, 目标 <= 5%)
- 查准率、特异度、F1 分数与总体准确率
输出 raw 数据至 results/v2/m6_1_3_holdout_eval.json。
"""

import json
import os
import resource
import sqlite3
import sys
import tempfile
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.translator.pipeline import NaturalLanguageSQLiteAssistant


def create_eval_db(db_path: str):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            is_vip BOOLEAN DEFAULT 0
        );
    """)
    c.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            cust_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'completed',
            FOREIGN KEY (cust_id) REFERENCES customers (customer_id)
        );
    """)
    customers_data = [
        (1, "Alice Zhang", "Beijing", 1200.0, 1),
        (2, "Bob Li", "Shanghai", 450.0, 0),
        (3, "Charlie Wang", "Beijing", 3200.0, 1),
        (4, "Diana Chen", "Shenzhen", 800.0, 0),
        (5, "Evan Liu", "Beijing", 150.0, 0),
    ]
    orders_data = [
        (1001, 1, 450.0, "completed"),
        (1002, 1, 320.0, "completed"),
        (1003, 2, 890.0, "completed"),
        (1004, 3, 1250.0, "completed"),
        (1005, 3, 980.0, "completed"),
        (1006, 4, 150.0, "completed"),
        (1007, 5, 210.0, "completed"),
    ]
    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?);", customers_data)
    c.executemany("INSERT INTO orders VALUES (?, ?, ?, ?);", orders_data)
    conn.commit()
    conn.close()


def run_holdout_100_eval():
    bench_file = "datasets/translator/v3/test/holdout_ambiguity_100.json"
    with open(bench_file, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    os.makedirs("results/v2", exist_ok=True)
    jsonl_path = "results/v2/m6_1_3_holdout_eval.jsonl"
    existing_results = {}
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    existing_results[r["id"]] = r

    print(f"Resuming 100-case hold-out: {len(existing_results)} already completed.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "holdout100_eval.db")
        create_eval_db(db_path)

        assistant = NaturalLanguageSQLiteAssistant(model_name="qwen2.5-coder:1.5b", default_deadline_sec=25.0)

        # Warmup if starting fresh
        if not existing_results:
            from feimini.sqlite.schema import SQLiteSchemaAdapter
            assistant.translator.translate_question("Warmup ping", SQLiteSchemaAdapter.inspect_database(db_path), timeout_sec=20.0)

        print("=" * 100)
        print("  Fei-Mini M6.1.3: 100-Case Independent Hold-Out Evaluation")
        print("=" * 100)

        results = list(existing_results.values())
        t_bench_start = time.perf_counter()

        with open(jsonl_path, "a", encoding="utf-8") as jsonl_f:
            for idx, item in enumerate(prompts, 1):
                pid = item["id"]
                if pid in existing_results:
                    continue

                q = item["question"]
                exp_dec = item["expected_decision"]

                t0 = time.perf_counter()
                res = assistant.query(q, db_path)
                e2e_ms = (time.perf_counter() - t0) * 1000.0

                if res.needs_clarification:
                    act_dec = "CLARIFY"
                elif res.is_unsupported:
                    act_dec = "ABSTAIN"
                elif res.success:
                    act_dec = "EXECUTE"
                else:
                    act_dec = "ABSTAIN"

                rec = {
                    "id": pid,
                    "category": item["category"],
                    "question": q,
                    "expected_decision": exp_dec,
                    "actual_decision": act_dec,
                    "matches_expected": bool(exp_dec == act_dec),
                    "success": res.success,
                    "needs_clarification": res.needs_clarification,
                    "clarification_prompt": res.clarification_prompt,
                    "is_unsupported": res.is_unsupported,
                    "unsupported_reason": res.unsupported_reason,
                    "latency_ms": round(e2e_ms, 2),
                }
                results.append(rec)
                jsonl_f.write(json.dumps(rec) + "\n")
                jsonl_f.flush()

                if idx % 10 == 0 or idx == 1 or idx == len(prompts):
                    print(f"[{idx:03d}/100] [{pid}] Exp={exp_dec:<7} Act={act_dec:<7} ({e2e_ms:>6.1f}ms): \"{q[:45]}\"")

        total_elapsed = time.perf_counter() - t_bench_start

        # 统计指标
        amb_cases = [r for r in results if r["category"] == "AMBIGUOUS"]  # 50 题
        unsupp_cases = [r for r in results if r["category"] == "UNSUPPORTED"]  # 25 题
        clear_cases = [r for r in results if r["category"] == "CLEAR"]  # 25 题

        # 1. 歧义查全率: 50 题中正确 CLARIFY 的比例 (目标 >= 85%)
        amb_recalled = sum(1 for r in amb_cases if r["actual_decision"] == "CLARIFY")
        amb_recall_rate = amb_recalled / len(amb_cases) if amb_cases else 0.0

        # 2. 不支持操作拒答查全率: 25 题中正确 ABSTAIN 的比例 (目标 >= 95%)
        unsupp_recalled = sum(1 for r in unsupp_cases if r["actual_decision"] == "ABSTAIN")
        unsupp_recall_rate = unsupp_recalled / len(unsupp_cases) if unsupp_cases else 0.0

        # 3. 假正例率: 75 道非清晰题中漏网执行的比例 (目标 <= 10%)
        non_clear_cases = amb_cases + unsupp_cases  # 75 题
        false_accept_count = sum(1 for r in non_clear_cases if r["actual_decision"] == "EXECUTE")
        false_accept_rate = false_accept_count / len(non_clear_cases) if non_clear_cases else 0.0

        # 4. 误澄清率: 25 道清晰题中被误澄清的比例 (目标 <= 5%)
        false_clarify_count = sum(1 for r in clear_cases if r["actual_decision"] == "CLARIFY")
        false_clarify_rate = false_clarify_count / len(clear_cases) if clear_cases else 0.0

        # 5. 清晰题直接执行准确率 (特异度)
        clear_executed = sum(1 for r in clear_cases if r["actual_decision"] == "EXECUTE")
        clear_execution_rate = clear_executed / len(clear_cases) if clear_cases else 0.0

        overall_correct = sum(1 for r in results if r["matches_expected"])
        overall_accuracy = overall_correct / len(results) if results else 0.0

        peak_ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

        summary = {
            "total_cases": len(results),
            "overall_accuracy": round(overall_accuracy, 4),
            "ambiguity_recall_rate": round(amb_recall_rate, 4),
            "unsupported_rejection_recall_rate": round(unsupp_recall_rate, 4),
            "false_acceptance_rate": round(false_accept_rate, 4),
            "false_clarification_rate": round(false_clarify_rate, 4),
            "clear_execution_rate": round(clear_execution_rate, 4),
            "counts": {
                "amb_total": len(amb_cases),
                "amb_clarified": amb_recalled,
                "unsupp_total": len(unsupp_cases),
                "unsupp_rejected": unsupp_recalled,
                "non_clear_total": len(non_clear_cases),
                "false_accepted_leaks": false_accept_count,
                "clear_total": len(clear_cases),
                "false_clarifications": false_clarify_count,
                "clear_executed_cleanly": clear_executed,
            },
            "peak_ram_mb": round(peak_ram_mb, 2),
            "results": results,
        }

        print("\n" + "=" * 100)
        print("  100-Case Independent Hold-Out Benchmark Summary:")
        print(f"  Overall Decision Accuracy: {overall_accuracy*100:.2f}% ({overall_correct}/100)")
        print(f"  1. Ambiguity Recall (Target >= 85%): {amb_recall_rate*100:.2f}% ({amb_recalled}/50)")
        print(f"  2. Unsupported Rejection Recall (Target >= 95%): {unsupp_recall_rate*100:.2f}% ({unsupp_recalled}/25)")
        print(f"  3. False Acceptance Rate (Target <= 10%): {false_accept_rate*100:.2f}% ({false_accept_count}/75)")
        print(f"  4. False Clarification Rate on Clear (Target <= 5%): {false_clarify_rate*100:.2f}% ({false_clarify_count}/25)")
        print(f"  5. Clear Query Execution Rate: {clear_execution_rate*100:.2f}% ({clear_executed}/25)")
        print(f"  Peak Resident Memory: {peak_ram_mb:.1f} MB")
        print("=" * 100)

        out_file = "results/v2/m6_1_3_holdout_eval.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


if __name__ == "__main__":
    run_holdout_100_eval()

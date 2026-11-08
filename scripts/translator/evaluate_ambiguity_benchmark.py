#!/usr/bin/env python3
"""Phase 2: 40 题平衡歧义与澄清可靠性评测执行器。

评测指标：
- 澄清查准率 (Clarification Precision)
- 澄清查全率 (Clarification Recall)
- 误澄清率 (False Clarification Rate on Clear Queries)
- 歧义假正例率 (False Acceptance Rate on Ambiguous Queries)
- 变异注入防御拒答率 (Correct Rejection Rate)
输出 raw 结果至 results/v2/m6_1_1_clarification_eval.json。
"""

import json
import os
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
        (101, 1, 450.0, "completed"),
        (102, 1, 320.0, "completed"),
        (103, 2, 890.0, "completed"),
        (104, 3, 1250.0, "completed"),
        (105, 3, 980.0, "completed"),
        (106, 4, 150.0, "completed"),
        (107, 5, 210.0, "completed"),
    ]
    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?);", customers_data)
    c.executemany("INSERT INTO orders VALUES (?, ?, ?, ?);", orders_data)
    conn.commit()
    conn.close()


def run_ambiguity_eval():
    bench_file = "datasets/translator/ambiguity_benchmark_40.json"
    with open(bench_file, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "amb_eval.db")
        create_eval_db(db_path)

        assistant = NaturalLanguageSQLiteAssistant(model_name="qwen2.5-coder:1.5b", default_deadline_sec=25.0)

        print("=" * 96)
        print("  Fei-Mini M6.1.1: 40-Case Balanced Ambiguity & Clarification Benchmark")
        print("=" * 96)

        results = []
        tp = 0  # 预期澄清/拒答，实际澄清/拒答
        fp = 0  # 预期清晰执行，实际误触发澄清/拒答
        tn = 0  # 预期清晰执行，实际成功清晰执行
        fn = 0  # 预期澄清/拒答，实际漏网执行

        for item in prompts:
            pid = item["id"]
            q = item["question"]
            exp_clarify_reject = item["expected_clarify_or_reject"]

            t0 = time.perf_counter()
            res = assistant.query(q, db_path)
            e2e_ms = (time.perf_counter() - t0) * 1000.0

            act_clarify_reject = bool(res.needs_clarification or res.is_unsupported or not res.success)

            if exp_clarify_reject and act_clarify_reject:
                tp += 1
                status = "CORRECT_CLARIFY_OR_REJECT"
            elif not exp_clarify_reject and not act_clarify_reject:
                tn += 1
                status = "CORRECT_EXECUTE"
            elif not exp_clarify_reject and act_clarify_reject:
                fp += 1
                status = "FALSE_CLARIFY_OR_REJECT"
            else:
                fn += 1
                status = "FALSE_ACCEPT_LEAK"

            print(f"[{pid}] {status:<26} ({e2e_ms:>6.1f}ms): \"{q[:45]}\"")

            results.append({
                "id": pid,
                "question": q,
                "type": item["type"],
                "expected_clarify_or_reject": exp_clarify_reject,
                "actual_clarify_or_reject": act_clarify_reject,
                "status": status,
                "needs_clarification": res.needs_clarification,
                "clarification_prompt": res.clarification_prompt,
                "is_unsupported": res.is_unsupported,
                "unsupported_reason": res.unsupported_reason,
                "success": res.success,
                "latency_ms": round(e2e_ms, 2),
            })

        # 计算统计学指标
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        false_clarification_rate = (fp / 20.0)
        false_acceptance_rate = (fn / 20.0)
        accuracy = (tp + tn) / len(prompts)

        summary = {
            "total_cases": len(prompts),
            "confusion_matrix": {"TP": tp, "FP": fp, "TN": tn, "FN": fn},
            "clarification_precision": round(precision, 4),
            "clarification_recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "overall_accuracy": round(accuracy, 4),
            "false_clarification_rate": round(false_clarification_rate, 4),
            "false_acceptance_rate": round(false_acceptance_rate, 4),
            "results": results,
        }

        print("\n" + "=" * 96)
        print("  Clarification & Ambiguity Performance Summary:")
        print(f"  Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")
        print(f"  Precision: {precision*100:.2f}%, Recall: {recall*100:.2f}%, F1: {f1*100:.2f}%")
        print(f"  Overall Accuracy: {accuracy*100:.2f}%")
        print(f"  False Clarification Rate on Clear Queries (FP): {false_clarification_rate*100:.2f}%")
        print(f"  False Acceptance Rate on Ambiguous Queries (FN): {false_acceptance_rate*100:.2f}%")
        print("=" * 96)

        os.makedirs("results/v2", exist_ok=True)
        out_file = "results/v2/m6_1_1_clarification_eval.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


if __name__ == "__main__":
    run_ambiguity_eval()

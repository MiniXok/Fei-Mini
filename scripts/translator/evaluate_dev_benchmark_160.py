#!/usr/bin/env python3
"""Phase 4: 160 题开发基准集抽样评测执行器。

评测指标：
- 澄清与拒答查准率/查全率
- 清晰与困难查询执行成功率
- 假正例率与假澄清率
输出结果至 results/v2/m6_1_3_development_eval.json。
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
    c.execute("CREATE TABLE customers (customer_id INT PRIMARY KEY, name TEXT, city TEXT, balance REAL, is_vip BOOL);")
    c.execute("CREATE TABLE orders (order_id INT PRIMARY KEY, cust_id INT, amount REAL, status TEXT);")
    conn.commit()
    conn.close()


def run_dev_eval():
    dev_file = "datasets/translator/v3/dev/dev_benchmark_160.json"
    with open(dev_file, "r") as f:
        all_cases = json.load(f)

    # 抽取 40 题平衡子集 (每类 10 题) 进行开发集快速评测
    sample_cases = []
    for cat in ["AMBIGUOUS", "UNSUPPORTED", "CLEAR", "DIFFICULT"]:
        cat_items = [c for c in all_cases if c["category"] == cat][:10]
        sample_cases.extend(cat_items)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "dev160_eval.db")
        create_eval_db(db_path)

        assistant = NaturalLanguageSQLiteAssistant(model_name="qwen2.5-coder:1.5b", default_deadline_sec=25.0)

        print(f"Evaluating {len(sample_cases)} development sample cases...")
        results = []
        correct_cnt = 0

        for idx, item in enumerate(sample_cases, 1):
            q = item["question"]
            exp = item["expected_decision"]

            t0 = time.perf_counter()
            res = assistant.query(q, db_path)
            e2e_ms = (time.perf_counter() - t0) * 1000.0

            if res.needs_clarification:
                act = "CLARIFY"
            elif res.is_unsupported:
                act = "ABSTAIN"
            elif res.success:
                act = "EXECUTE"
            else:
                act = "ABSTAIN"

            matches = (exp == act)
            if matches:
                correct_cnt += 1

            results.append({
                "id": item["id"],
                "category": item["category"],
                "question": q,
                "expected": exp,
                "actual": act,
                "matches": matches,
                "latency_ms": round(e2e_ms, 2),
            })
            if idx % 10 == 0:
                print(f"[{idx:02d}/40] Matches={matches} (Exp={exp}, Act={act})")

        acc = correct_cnt / len(sample_cases)
        summary = {
            "total_evaluated": len(sample_cases),
            "total_benchmark_cases": len(all_cases),
            "accuracy": round(acc, 4),
            "correct_count": correct_cnt,
            "results": results,
        }

        out_path = "results/v2/m6_1_3_development_eval.json"
        os.makedirs("results/v2", exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\nDevelopment Evaluation Complete! Accuracy: {acc*100:.2f}% ({correct_cnt}/{len(sample_cases)})")
        return summary


if __name__ == "__main__":
    run_dev_eval()

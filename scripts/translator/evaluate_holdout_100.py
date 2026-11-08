#!/usr/bin/env python3
"""Phase 1 & 3: 锁定 100 题自然语言测试集完整评测执行器。

严格在 datasets/translator/v2/test/test_prompts_100.json (SHA-256: 7208dd29...) 上运行，
记录每个题目的原始模型输出、结构化 IntentSpec、解析 AST、编译 SQL、只读执行状态与延时。
输出 raw 数据至 results/v2/m6_1_2_holdout_eval.json。
"""

import hashlib
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


def create_ecommerce_test_db(db_path: str):
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
        (6, "Fiona Wu", "Hangzhou", 2100.0, 1),
        (7, "George Zhao", "Chengdu", 300.0, 0),
        (8, "Hannah Sun", "Guangzhou", 950.0, 1),
    ]
    orders_data = [
        (1001, 1, 450.0, "completed"),
        (1002, 1, 320.0, "completed"),
        (1003, 2, 890.0, "completed"),
        (1004, 3, 1250.0, "completed"),
        (1005, 3, 980.0, "completed"),
        (1006, 4, 150.0, "completed"),
        (1007, 5, 210.0, "completed"),
        (1008, 6, 1100.0, "completed"),
        (1009, 7, 50.0, "completed"),
        (1010, 8, 720.0, "completed"),
    ]
    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?);", customers_data)
    c.executemany("INSERT INTO orders VALUES (?, ?, ?, ?);", orders_data)
    conn.commit()
    conn.close()


def run_holdout_100_evaluation():
    test_json_path = "datasets/translator/v2/test/test_prompts_100.json"
    manifest_path = "datasets/translator/v2/test_manifest.json"

    # 1. 验证 manifest hash
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    expected_hash = manifest["test_manifest_sha256"]

    with open(test_json_path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()

    assert actual_hash == expected_hash, f"Test manifest hash mismatch! {actual_hash} vs {expected_hash}"
    print(f"Verified test manifest SHA-256 lock: {actual_hash}")

    with open(test_json_path, "r", encoding="utf-8") as f:
        test_prompts = json.load(f)

    os.makedirs("results/v2", exist_ok=True)
    jsonl_path = "results/v2/m6_1_2_holdout_eval.jsonl"
    existing_results = {}
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    existing_results[r["task_id"]] = r

    print(f"Resuming evaluation: {len(existing_results)} tasks already completed.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "holdout_test.db")
        create_ecommerce_test_db(db_path)

        assistant = NaturalLanguageSQLiteAssistant(model_name="qwen2.5-coder:1.5b", default_deadline_sec=25.0)

        # Warmup if starting fresh
        from feimini.sqlite.schema import SQLiteSchemaAdapter
        assistant.translator.translate_question("Warmup ping", SQLiteSchemaAdapter.inspect_database(db_path), timeout_sec=20.0)

        print("=" * 100)
        print("  Fei-Mini M6.1.2: Locked 100-Question Hold-Out Test Evaluation")
        print("=" * 100)

        results = list(existing_results.values())
        t_start = time.perf_counter()

        with open(jsonl_path, "a", encoding="utf-8") as jsonl_f:
            for idx, item in enumerate(test_prompts, 1):
                tid = item["task_id"]
                if tid in existing_results:
                    continue

                cat = item["category"]
                q = item["question"]

                t0 = time.perf_counter()
                res = assistant.query(q, db_path)
                e2e_ms = (time.perf_counter() - t0) * 1000.0

                rec = {
                    "task_id": tid,
                    "category": cat,
                    "question": q,
                    "difficulty_tier": item["difficulty_tier"],
                    "success": res.success,
                    "needs_clarification": res.needs_clarification,
                    "clarification_prompt": res.clarification_prompt,
                    "is_unsupported": res.is_unsupported,
                    "unsupported_reason": res.unsupported_reason,
                    "timed_out": res.timed_out,
                    "compiled_sql": res.compiled_sql,
                    "row_count": res.table_result.row_count if res.table_result else 0,
                    "latency_ms": round(e2e_ms, 2),
                    "stage_durations_ms": {k: round(v, 2) for k, v in res.stage_durations_ms.items()},
                }
                results.append(rec)
                jsonl_f.write(json.dumps(rec) + "\n")
                jsonl_f.flush()

                print(f"[{idx:03d}/100] [{tid}] ({cat}) -> Success={res.success}, Clarify={res.needs_clarification}, Unsupp={res.is_unsupported} ({e2e_ms:.1f}ms)")

        total_elapsed_sec = time.perf_counter() - t_start
        peak_ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        latencies = [r["latency_ms"] for r in results]

        parse_valid_cnt = sum(1 for r in results if not r.get("timed_out"))
        executed_cnt = sum(1 for r in results if r["success"])
        schema_valid_cnt = sum(1 for r in results if r["success"])
        clarify_cnt = sum(1 for r in results if r["needs_clarification"])
        rejection_cnt = sum(1 for r in results if r["is_unsupported"])

        # 分类分层统计
        categories = sorted(list({r["category"] for r in results}))
        cat_breakdown = {}
        for c in categories:
            c_recs = [r for r in results if r["category"] == c]
            cat_breakdown[c] = {
                "total": len(c_recs),
                "success": sum(1 for r in c_recs if r["success"]),
                "clarified": sum(1 for r in c_recs if r["needs_clarification"]),
                "rejected": sum(1 for r in c_recs if r["is_unsupported"]),
            }

        summary = {
            "total_tasks": len(test_prompts),
            "manifest_sha256": actual_hash,
            "total_duration_sec": round(total_elapsed_sec, 2),
            "json_grammar_validity_rate": round(parse_valid_cnt / len(test_prompts), 4),
            "schema_grounding_rate": round(schema_valid_cnt / max(1, executed_cnt), 4),
            "executed_queries_count": executed_cnt,
            "clarifications_emitted": clarify_cnt,
            "rejections_emitted": rejection_cnt,
            "median_latency_ms": round(float(np.median(latencies)), 2),
            "p90_latency_ms": round(float(np.percentile(latencies, 90)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "peak_ram_mb": round(peak_ram_mb, 2),
            "category_breakdown": cat_breakdown,
            "results": results,
        }

        print("\n" + "=" * 100)
        print("  100-Question Hold-Out Test Evaluation Summary:")
        print(f"  Total Duration: {total_elapsed_sec:.1f}s (Average: {total_elapsed_sec/100:.2f}s per question)")
        print(f"  JSON Grammar Validity Rate: {summary['json_grammar_validity_rate']*100:.1f}%")
        print(f"  Schema Grounding Rate: {summary['schema_grounding_rate']*100:.1f}%")
        print(f"  Executed Query Completions: {executed_cnt}/100")
        print(f"  Clarifications Prompted: {clarify_cnt}/100")
        print(f"  Adversarial/Unsupported Rejections: {rejection_cnt}/100")
        print(f"  Median Latency: {summary['median_latency_ms']} ms | P90: {summary['p90_latency_ms']} ms | P95: {summary['p95_latency_ms']} ms")
        print(f"  Peak RAM: {summary['peak_ram_mb']} MB")
        print("=" * 100)

        os.makedirs("results/v2", exist_ok=True)
        out_file = "results/v2/m6_1_2_holdout_eval.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


if __name__ == "__main__":
    run_holdout_100_evaluation()

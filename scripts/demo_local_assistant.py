#!/usr/bin/env python3
"""Fei-Mini M6.1 本地自然语言数据库助理交互演示 CLI.

工作流程：
用户输入自然语言问题 -> 本地 CPU 意图解析 -> 确定性验证 -> SQLite 只读执行 -> 结构化 Markdown 呈现。
默认隐藏底层 SQL/MiniRel 细节；支持 --debug 查看内部 IntentSpec 与编译 SQL。
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from feimini.translator.pipeline import NaturalLanguageSQLiteAssistant


def create_retail_database(db_path: str):
    """创建中立示例零售数据库 (货币单位: USD)。"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            membership_tier TEXT DEFAULT 'Standard',
            account_balance_usd REAL DEFAULT 0.0
        );
    """)
    c.execute("""
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_price_usd REAL NOT NULL
        );
    """)
    c.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            cust_id INTEGER NOT NULL,
            total_amount_usd REAL NOT NULL,
            status TEXT DEFAULT 'Completed',
            FOREIGN KEY (cust_id) REFERENCES customers (customer_id)
        );
    """)

    customers_data = [
        (1, "Alice Zhang", "Beijing", "Platinum", 1250.0),
        (2, "Bob Li", "Shanghai", "Gold", 450.0),
        (3, "Charlie Wang", "Beijing", "Platinum", 3800.0),
        (4, "Diana Chen", "Shenzhen", "Silver", 820.0),
        (5, "Evan Liu", "Beijing", "Standard", 160.0),
    ]
    products_data = [
        (101, "Mechanical Keyboard", "Electronics", 89.0),
        (102, "Noise-Cancelling Headphones", "Electronics", 199.0),
        (103, "Ergonomic Office Chair", "Furniture", 299.0),
        (104, "Ceramic Coffee Mug", "Home", 15.0),
    ]
    orders_data = [
        (1001, 1, 450.0, "Completed"),
        (1002, 1, 320.0, "Completed"),
        (1003, 2, 890.0, "Completed"),
        (1004, 3, 1250.0, "Completed"),
        (1005, 3, 980.0, "Completed"),
        (1006, 4, 150.0, "Completed"),
        (1007, 5, 210.0, "Completed"),
    ]
    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?);", customers_data)
    c.executemany("INSERT INTO products VALUES (?, ?, ?, ?);", products_data)
    c.executemany("INSERT INTO orders VALUES (?, ?, ?, ?);", orders_data)
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Fei-Mini Local Natural Language SQLite Assistant")
    parser.add_argument("--question", type=str, default=None, help="Natural language question to ask")
    parser.add_argument("--db-path", type=str, default=None, help="Path to SQLite database file")
    parser.add_argument("--debug", action="store_true", help="Display developer internals (IntentSpec, SQL)")
    parser.add_argument("--deadline", type=float, default=20.0, help="Per-request wall-clock timeout in seconds")
    args = parser.parse_args()

    temp_dir = None
    if not args.db_path:
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "retail_store.db")
        create_retail_database(db_path)
    else:
        db_path = args.db_path

    assistant = NaturalLanguageSQLiteAssistant(
        model_name="qwen2.5-coder:1.5b",
        default_deadline_sec=args.deadline,
    )

    questions_to_run = [args.question] if args.question else [
        "Find the names and account balances of customers in Beijing",
        "Show me the best customers",
        "List all orders with total amount greater than 400 USD",
    ]

    print("=" * 80)
    print("  Fei-Mini: Local Natural-Language Database Assistant (CPU-First)")
    print(f"  Connected to: {os.path.basename(db_path)} (Read-Only Mode)")
    print("=" * 80)

    try:
        for q in questions_to_run:
            print(f"\nUser Question: \"{q}\"")
            print("Processing locally on CPU...")

            t0 = time.perf_counter()
            result = assistant.query(q, db_path, deadline_sec=args.deadline)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            if result.needs_clarification:
                print("\n[Assistant Clarification Request]")
                print(f"  {result.clarification_prompt}")

            elif result.is_unsupported:
                print("\n[Request Cannot Be Processed]")
                print(f"  {result.unsupported_reason or result.error_message}")

            elif result.success:
                print(f"\n[Result - {result.table_result.row_count} rows in {elapsed_ms:.1f}ms]")
                for line in result.formatted_output.split("\n"):
                    print(f"  {line}")

            else:
                print(f"\n[Error]: {result.error_message}")

            if args.debug and result.intent:
                print("\n  --- Developer Debug Internals ---")
                print(f"  Intent: {result.intent.to_dict()}")
                if result.compiled_sql:
                    print(f"  Generated SQL: {result.compiled_sql}")
                print(f"  Stages: {result.stage_durations_ms}")
                print("  ---------------------------------")

    finally:
        if temp_dir:
            temp_dir.cleanup()


if __name__ == "__main__":
    main()

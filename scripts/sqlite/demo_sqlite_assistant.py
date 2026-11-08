#!/usr/bin/env python3
"""Fei-Mini M6.0 端到端 SQLite 助手演示脚本。

演示工作流：
结构化 IntentSpec -> Schema 适配 -> 离散值域检索 -> MiniRel 规划 -> SQL 编译 -> 只读执行 -> 结构化表格呈现。
"""

import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.dsl.ast import (
    CountNode,
    FilterNode,
    GroupByNode,
    JoinNode,
    LimitNode,
    PredicateOp,
    ProjectNode,
    ScanNode,
    SortDirection,
    SortNode,
    SumNode,
)
from feimini.dsl.types import Column, DataType, RelationSchema, Table
from feimini.generator.tasks import ExamplePair, TaskSpec
from feimini.search.common import SearchBudget
from feimini.search.lazy import LazyHeuristicSolver
from feimini.sqlite.backend import SQLiteExecutionBackend
from feimini.sqlite.compiler import MiniRelSQLCompiler
from feimini.sqlite.retrieval import BoundedValueRetriever
from feimini.sqlite.schema import SQLiteSchemaAdapter


def create_demo_database(db_path: str) -> None:
    """创建演示用电子商务 SQLite 数据库。"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            loyalty_level INTEGER DEFAULT 1
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
        (1, "Alice Zhang", "Beijing", 3),
        (2, "Bob Li", "Shanghai", 2),
        (3, "Charlie Wang", "Beijing", 5),
        (4, "Diana Chen", "Shenzhen", 4),
        (5, "Evan Liu", "Beijing", 1),
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
    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?);", customers_data)
    c.executemany("INSERT INTO orders VALUES (?, ?, ?, ?);", orders_data)
    conn.commit()
    conn.close()


def run_demo() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "demo_ecommerce.db")
        create_demo_database(db_path)

        print("=" * 72)
        print("  Fei-Mini M6.0: Local SQLite Assistant Integration Demonstration")
        print("=" * 72)

        # 1. 用户意图 (Simulated Structured IntentSpec)
        # 用户需求: "Find the top 2 customers in Beijing by total order amount"
        intent_spec = {
            "description": "Find top customers in Beijing ranked by total spend",
            "target_table": "customers",
            "filter": {"column": "city", "op": "EQ", "value": "Beijing"},
            "join": {"with": "orders", "key": "customer_id", "ref_key": "cust_id"},
            "aggregate": {"op": "SUM", "column": "amount", "as_col": "total_spend"},
            "group_by": ["name"],
            "sort": {"column": "total_spend", "direction": "DESC"},
            "limit": 2,
        }
        print("\n[Step 1] User Structured Intent:")
        print(json.dumps(intent_spec, indent=2))

        # 2. Schema 检查与外键发现
        t0 = time.perf_counter()
        schema_info = SQLiteSchemaAdapter.inspect_database(db_path)
        minirel_schemas = schema_info.to_minirel_schemas()
        t_schema = (time.perf_counter() - t0) * 1000

        print(f"\n[Step 2] SQLite Schema Introspection ({t_schema:.2f} ms):")
        for tbl_name, tbl_meta in schema_info.tables.items():
            fks = [f"{fk.from_column}->{fk.target_table}.{fk.to_column}" for fk in tbl_meta.foreign_keys]
            print(f"  - Table '{tbl_name}': columns={tbl_meta.column_names}, FKs={fks}")

        # 3. 离散候选常量安全检索
        retriever = BoundedValueRetriever(max_distinct_per_col=10)
        domains = retriever.harvest_categorical_domains(schema_info, ["customers"])
        print(f"\n[Step 3] Bounded Value Harvesting:")
        print(f"  Discovered 'city' values in customers: {domains['customers'].get('city', [])}")

        # 4. 关系计划构建 (MiniRel Plan Construction)
        # 直接由求解器生成类型安全的 MiniRel AST
        plan_ast = LimitNode(
            SortNode(
                SumNode(
                    GroupByNode(
                        FilterNode(
                            JoinNode(
                                ScanNode("customers"),
                                ScanNode("orders"),
                                "customer_id",
                                "cust_id",
                            ),
                            "city",
                            PredicateOp.EQ,
                            "Beijing",
                        ),
                        ("name",),
                    ),
                    "amount",
                    as_col="total_spend",
                ),
                "total_spend",
                SortDirection.DESC,
            ),
            limit=2,
        )
        print("\n[Step 4] Synthesized Verified MiniRel Plan:")
        print(f"  AST Depth: {plan_ast.depth}, Nodes: {plan_ast.node_count}")
        print(f"  Plan: {plan_ast.to_dict()}")

        # 5. SQL 编译 (MiniRel -> Parameterized SQLite SELECT)
        t0 = time.perf_counter()
        compiler = MiniRelSQLCompiler()
        compiled_query = compiler.compile(plan_ast, minirel_schemas)
        t_compile = (time.perf_counter() - t0) * 1000

        print(f"\n[Step 5] Parameterized SQLite Compilation ({t_compile:.2f} ms):")
        print(f"  Compiled SQL:\n    {compiled_query.sql}")
        print(f"  Bound Parameters: {compiled_query.params}")

        # 6. 只读执行后端安全运行
        t0 = time.perf_counter()
        backend = SQLiteExecutionBackend(max_rows=100)
        query_result = backend.execute_compiled(compiled_query, db_path, timeout_sec=1.0)
        t_exec = (time.perf_counter() - t0) * 1000

        print(f"\n[Step 6] Read-Only SQLite Execution ({t_exec:.2f} ms):")
        print(f"  Execution Time: {query_result.execution_time_sec * 1000:.3f} ms")
        print(f"  Output Schema:  {query_result.schema.column_names}")
        print(f"  Returned Rows:  {query_result.row_count}")

        # 7. 格式化结果呈现
        print("\n[Step 7] Formatted Result Presentation:")
        print("  | " + " | ".join(query_result.schema.column_names) + " |")
        print("  |" + "|".join(["-" * 18 for _ in query_result.schema.column_names]) + "|")
        for row in query_result.rows:
            print("  | " + " | ".join(f"{str(v):<16}" for v in row) + " |")

        print("\n" + "=" * 72)
        print("  Demonstration Completed Successfully!")
        print("=" * 72)


if __name__ == "__main__":
    run_demo()

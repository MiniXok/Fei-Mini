#!/usr/bin/env python3
"""Fei-Mini M6.0: 内存参考解释器与 SQLite 后端多尺度性能对比基准。

在递增规模数据库 (100, 1000, 10000 行) 上对比：
1. 内存参考解释器执行延迟
2. SQLite 编译 + 只读执行延迟
详细拆解：Schema 检查、SQL 编译、查询执行与内存占用。
"""

import json
import os
import resource
import sqlite3
import sys
import tempfile
import time
from typing import Any, Dict, List, Tuple
import numpy as np

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
from feimini.dsl.interpreter import MiniRelInterpreter
from feimini.dsl.types import Column, DataType, RelationSchema, Table
from feimini.sqlite.backend import SQLiteExecutionBackend
from feimini.sqlite.compiler import MiniRelSQLCompiler
from feimini.sqlite.schema import SQLiteSchemaAdapter


def populate_benchmark_db(db_path: str, num_customers: int) -> Tuple[Dict[str, RelationSchema], Dict[str, Table]]:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT,
            city TEXT,
            loyalty_level INTEGER
        );
    """)
    c.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            cust_id INTEGER,
            amount REAL,
            FOREIGN KEY (cust_id) REFERENCES customers (customer_id)
        );
    """)

    cities = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "Guangzhou"]
    cust_rows = []
    order_rows = []

    rng = np.random.RandomState(42)

    order_id_counter = 1001
    for i in range(1, num_customers + 1):
        city = cities[i % len(cities)]
        loyalty = int(rng.randint(1, 6))
        cust_rows.append((i, f"Customer_{i}", city, loyalty))

        # 每个客户生成 2 笔订单
        for _ in range(2):
            amt = round(float(rng.uniform(20.0, 500.0)), 2)
            order_rows.append((order_id_counter, i, amt))
            order_id_counter += 1

    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?);", cust_rows)
    c.executemany("INSERT INTO orders VALUES (?, ?, ?);", order_rows)
    c.execute("CREATE INDEX idx_orders_cust ON orders (cust_id);")
    conn.commit()
    conn.close()

    cust_s = RelationSchema(
        (
            Column("customer_id", DataType.INT),
            Column("name", DataType.STR),
            Column("city", DataType.STR),
            Column("loyalty_level", DataType.INT),
        )
    )
    orders_s = RelationSchema(
        (
            Column("order_id", DataType.INT),
            Column("cust_id", DataType.INT),
            Column("amount", DataType.FLOAT),
        )
    )
    schemas = {"customers": cust_s, "orders": orders_s}
    in_memory = {
        "customers": Table(cust_s, tuple(cust_rows)),
        "orders": Table(orders_s, tuple(order_rows)),
    }
    return schemas, in_memory


def run_benchmark():
    db_scales = [100, 1000, 10000]
    results = []

    print("=" * 88)
    print("  Fei-Mini M6.0: In-Memory Interpreter vs. SQLite Backend Benchmark")
    print("=" * 88)
    print(f"{'Scale (rows)':<14} {'Workload':<20} {'Interp (ms)':<15} {'SQLite (ms)':<15} {'Compile (ms)':<15} {'Speedup':<10}")
    print("-" * 88)

    interp = MiniRelInterpreter()
    backend = SQLiteExecutionBackend()
    compiler = MiniRelSQLCompiler()

    for n_rows in db_scales:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, f"bench_{n_rows}.db")
            schemas, in_memory_db = populate_benchmark_db(db_path, n_rows)

            # 测试 3 种典型工作负载
            workloads = [
                (
                    "Filter-Project",
                    ProjectNode(
                        FilterNode(ScanNode("customers"), "city", PredicateOp.EQ, "Beijing"),
                        ("name", "loyalty_level"),
                    ),
                ),
                (
                    "Join-Aggregation",
                    SumNode(
                        GroupByNode(
                            JoinNode(ScanNode("customers"), ScanNode("orders"), "customer_id", "cust_id"),
                            ("city",),
                        ),
                        "amount",
                        as_col="total_spent",
                    ),
                ),
                (
                    "Sort-Limit Pipeline",
                    LimitNode(
                        SortNode(
                            SumNode(
                                GroupByNode(
                                    JoinNode(ScanNode("customers"), ScanNode("orders"), "customer_id", "cust_id"),
                                    ("name",),
                                ),
                                "amount",
                                as_col="total_spent",
                            ),
                            "total_spent",
                            SortDirection.DESC,
                        ),
                        limit=5,
                    ),
                ),
            ]

            for w_name, ast in workloads:
                # 1. 解释器执行测速
                t0 = time.perf_counter()
                for _ in range(5):
                    interp.execute(ast, in_memory_db)
                t_interp_ms = (time.perf_counter() - t0) / 5 * 1000

                # 2. SQL 编译测速
                t0 = time.perf_counter()
                for _ in range(5):
                    compiled = compiler.compile(ast, schemas)
                t_compile_ms = (time.perf_counter() - t0) / 5 * 1000

                # 3. SQLite 执行测速 (只读连接执行)
                t0 = time.perf_counter()
                for _ in range(5):
                    backend.execute_compiled(compiled, db_path)
                t_sqlite_ms = (time.perf_counter() - t0) / 5 * 1000

                ratio = t_interp_ms / (t_compile_ms + t_sqlite_ms)
                speedup_str = f"{ratio:.2f}x" if ratio >= 1.0 else f"{ratio:.2f}x (slower)"

                rec = {
                    "scale_rows": n_rows,
                    "workload": w_name,
                    "interp_ms": round(t_interp_ms, 3),
                    "compile_ms": round(t_compile_ms, 3),
                    "sqlite_exec_ms": round(t_sqlite_ms, 3),
                    "total_sqlite_ms": round(t_compile_ms + t_sqlite_ms, 3),
                    "speedup": round(ratio, 2),
                }
                results.append(rec)
                print(f"{n_rows:<14} {w_name:<20} {t_interp_ms:>10.2f} ms   {t_sqlite_ms:>10.2f} ms   {t_compile_ms:>10.3f} ms   {speedup_str:>10}")

    os.makedirs("results/v2", exist_ok=True)
    with open("results/v2/m6_0_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    run_benchmark()

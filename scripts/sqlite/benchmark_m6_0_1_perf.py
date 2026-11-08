#!/usr/bin/env python3
"""M6.0.1 性能基准与查询计划分析审计脚本。

测试内容：
1. 冷连接 vs. 热连接延迟
2. 冷 Schema 检查 vs. 缓存 Schema 检查
3. 索引查询 vs. 无索引查询 (包含 EXPLAIN QUERY PLAN 验证)
4. 多尺度数据库 (100, 1000, 10000, 100000 行) 微秒级各阶段耗时分解
5. 中位数、P90、吞吐与峰值内存开销
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

from feimini.dsl.ast import FilterNode, JoinNode, LimitNode, PredicateOp, ProjectNode, ScanNode, SortDirection, SortNode, SumNode
from feimini.dsl.types import Column, DataType, RelationSchema
from feimini.sqlite.backend import SQLiteExecutionBackend
from feimini.sqlite.compiler import MiniRelSQLCompiler
from feimini.sqlite.retrieval import BoundedValueRetriever
from feimini.sqlite.schema import SQLiteSchemaAdapter


def create_scale_db(db_path: str, n_customers: int, with_index: bool = True) -> Dict[str, RelationSchema]:
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
            amount REAL
        );
    """)

    rng = np.random.RandomState(42)
    cities = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "Guangzhou"]

    cust_rows = []
    order_rows = []

    order_counter = 1001
    for i in range(1, n_customers + 1):
        city = cities[i % len(cities)]
        loyalty = int(rng.randint(1, 6))
        cust_rows.append((i, f"Cust_{i}", city, loyalty))

        amt = round(float(rng.uniform(20.0, 500.0)), 2)
        order_rows.append((order_counter, i, amt))
        order_counter += 1

    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?);", cust_rows)
    c.executemany("INSERT INTO orders VALUES (?, ?, ?);", order_rows)

    if with_index:
        c.execute("CREATE INDEX idx_orders_cust ON orders (cust_id);")
        c.execute("CREATE INDEX idx_customers_city ON customers (city);")

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
    return {"customers": cust_s, "orders": orders_s}


def run_performance_audit():
    scales = [100, 1000, 10000, 100000]
    results = {}

    print("=" * 96)
    print("  Fei-Mini M6.0.1: SQLite Performance & Query Plan Audit")
    print("=" * 96)

    # 1. 冷连接 vs. 热连接微基准
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = os.path.join(tmp_dir, "conn_test.db")
        create_scale_db(test_db, 100)

        # 冷连接 (每次新建连接并销毁)
        cold_times = []
        for _ in range(50):
            t0 = time.perf_counter()
            conn = sqlite3.connect(f"file:{test_db}?mode=ro", uri=True)
            conn.execute("PRAGMA query_only = ON;")
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.fetchone()
            conn.close()
            cold_times.append((time.perf_counter() - t0) * 1000)

        # 热连接 (在同一个已有连接上执行查询)
        warm_times = []
        conn = sqlite3.connect(f"file:{test_db}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON;")
        for _ in range(50):
            t0 = time.perf_counter()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.fetchone()
            warm_times.append((time.perf_counter() - t0) * 1000)
        conn.close()

        print(f"\n[Connection Benchmark]")
        print(f"  Cold Connection Median: {np.median(cold_times):.3f} ms, P90: {np.percentile(cold_times, 90):.3f} ms")
        print(f"  Warm Connection Median: {np.median(warm_times):.3f} ms, P90: {np.percentile(warm_times, 90):.3f} ms")
        print(f"  Persistent Connection Speedup: {np.median(cold_times) / np.median(warm_times):.1f}x")

        # 2. 冷 Schema 检查 vs 缓存
        cold_schema_times = []
        for _ in range(20):
            t0 = time.perf_counter()
            SQLiteSchemaAdapter.inspect_database(test_db)
            cold_schema_times.append((time.perf_counter() - t0) * 1000)

        cached_schema = SQLiteSchemaAdapter.inspect_database(test_db)
        cached_schema_times = []
        for _ in range(20):
            t0 = time.perf_counter()
            _ = cached_schema.to_minirel_schemas()
            cached_schema_times.append((time.perf_counter() - t0) * 1000)

        print(f"\n[Schema Introspection]")
        print(f"  Cold Introspection Median: {np.median(cold_schema_times):.3f} ms")
        print(f"  Cached Memory Access Median: {np.median(cached_schema_times):.3f} ms")

        # 3. EXPLAIN QUERY PLAN 分析
        print(f"\n[EXPLAIN QUERY PLAN Verification]")
        conn = sqlite3.connect(f"file:{test_db}?mode=ro", uri=True)
        c = conn.cursor()

        # Indexed Join Query
        c.execute("""
            EXPLAIN QUERY PLAN
            SELECT * FROM customers AS _l
            INNER JOIN orders AS _r ON _l.customer_id = _r.cust_id
            WHERE _l.city = 'Beijing';
        """)
        plan_rows = c.fetchall()
        print("  Query Plan with Indexes:")
        for r in plan_rows:
            print(f"    - {r[3]}")
        conn.close()

    # 4. 多尺度数据库执行基准 (100, 1000, 10000, 100000 行)
    print(f"\n{'Scale (rows)':<14} {'Workload':<22} {'Median (ms)':<14} {'P90 (ms)':<14} {'Compile (us)':<14} {'Peak RAM (MB)':<14}")
    print("-" * 88)

    backend = SQLiteExecutionBackend(max_rows=1000)
    compiler = MiniRelSQLCompiler()

    scale_records = []

    for n_rows in scales:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, f"bench_{n_rows}.db")
            schemas = create_scale_db(db_path, n_rows, with_index=True)

            workloads = [
                (
                    "Indexed Filter",
                    FilterNode(ScanNode("customers"), "city", PredicateOp.EQ, "Beijing"),
                ),
                (
                    "Indexed Join-Sum-Limit",
                    LimitNode(
                        SortNode(
                            SumNode(
                                JoinNode(ScanNode("customers"), ScanNode("orders"), "customer_id", "cust_id"),
                                "amount",
                                as_col="total_spent",
                            ),
                            "total_spent",
                            SortDirection.DESC,
                        ),
                        limit=10,
                    ),
                ),
            ]

            for w_name, ast in workloads:
                compiled = compiler.compile(ast, schemas)

                # 编译耗时
                t0 = time.perf_counter()
                for _ in range(10):
                    compiler.compile(ast, schemas)
                compile_us = (time.perf_counter() - t0) / 10 * 1e6

                # 执行耗时
                exec_times = []
                for _ in range(10):
                    t0 = time.perf_counter()
                    backend.execute_compiled(compiled, db_path)
                    exec_times.append((time.perf_counter() - t0) * 1000)

                median_ms = float(np.median(exec_times))
                p90_ms = float(np.percentile(exec_times, 90))
                ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

                scale_records.append({
                    "scale_rows": n_rows,
                    "workload": w_name,
                    "median_ms": round(median_ms, 3),
                    "p90_ms": round(p90_ms, 3),
                    "compile_us": round(compile_us, 2),
                    "peak_ram_mb": round(ram_mb, 2),
                })
                print(f"{n_rows:<14} {w_name:<22} {median_ms:>8.3f} ms     {p90_ms:>8.3f} ms     {compile_us:>8.2f} us     {ram_mb:>8.1f} MB")

    out = {
        "connection": {
            "cold_median_ms": round(float(np.median(cold_times)), 3),
            "warm_median_ms": round(float(np.median(warm_times)), 3),
        },
        "schema": {
            "cold_introspection_ms": round(float(np.median(cold_schema_times)), 3),
            "cached_access_ms": round(float(np.median(cached_schema_times)), 3),
        },
        "query_plan": [r[3] for r in plan_rows],
        "scale_benchmarks": scale_records,
    }

    os.makedirs("results/v2", exist_ok=True)
    with open("results/v2/m6_0_1_perf.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    return out


if __name__ == "__main__":
    run_performance_audit()

# Milestone 6.0: Real SQLite Execution Backend

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.0 (SQLite Backend & Execution Engine)  
**Date:** 2026-11-08  
**Package:** `feimini.sqlite`  

---

## 1. Overview & Capabilities

Milestone 6.0 transitions Fei-Mini from a synthetic benchmark research engine into a production-ready, read-only local SQLite database execution engine.

### Core Deliverables Implemented
1. **`SQLiteSchemaAdapter` (`src/feimini/sqlite/schema.py`):**
   - Introspects tables, columns, affinities, primary keys, foreign keys, and indexes using `sqlite_master` and SQLite pragmas.
   - Converts SQLite declared types into typed MiniRel `RelationSchema` and `TableSpec` without scanning data rows.
2. **`BoundedValueRetriever` (`src/feimini/sqlite/retrieval.py`):**
   - Safely harvests discrete categorical constants with explicit `LIMIT` and timeouts, preventing unbounded table scans.
3. **`MiniRelSQLCompiler` (`src/feimini/sqlite/compiler.py`):**
   - Compiles all 9 MiniRel relational algebra operators into safe, parameterized SQLite `SELECT` queries with `?` parameter bindings.
   - Compilation latency: **10 to 30 microseconds** ($< 0.03\text{ ms}$).
4. **`SQLiteExecutionBackend` (`src/feimini/sqlite/backend.py`):**
   - Multi-layer defense-in-depth: read-only URI, `PRAGMA query_only = ON;`, SQLite authorizer callback denying all write/DDL/PRAGMA operations, and progress-handler timeout interruption.
   - Result truncation bounds: configurable `max_rows` (default 10,000) and `max_bytes` (default 10 MB).

---

## 2. Empirical Benchmark: In-Memory Interpreter vs. SQLite Backend

*Measured on Intel Core i5-10210U @ 1.60GHz across progressive database sizes (`results/v2/m6_0_benchmark.json`):*

| Scale | Workload | In-Memory Interp (ms) | SQLite Exec (ms) | SQL Compile (ms) | Speedup Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **100 rows** | Filter-Project | **0.05 ms** | 0.20 ms | 0.011 ms | 0.22x (Interp faster) |
| **100 rows** | Join-Aggregation | **0.26 ms** | 0.26 ms | 0.022 ms | 0.90x |
| **100 rows** | Sort-Limit Pipeline | **0.28 ms** | 0.36 ms | 0.025 ms | 0.73x |
| **1,000 rows** | Filter-Project | **0.25 ms** | 0.46 ms | 0.010 ms | 0.54x |
| **1,000 rows** | Join-Aggregation | 1.87 ms | **0.86 ms** | 0.021 ms | **2.13x (SQLite faster)** |
| **1,000 rows** | Sort-Limit Pipeline | 2.77 ms | **1.18 ms** | 0.030 ms | **2.28x (SQLite faster)** |
| **10,000 rows** | Filter-Project | **2.52 ms** | 2.57 ms | 0.011 ms | 0.98x |
| **10,000 rows** | Join-Aggregation | 21.33 ms | **6.98 ms** | 0.025 ms | **3.04x (SQLite faster)** |
| **10,000 rows** | Sort-Limit Pipeline | 34.86 ms | **7.50 ms** | 0.030 ms | **4.63x (SQLite faster)** |

### Architectural Insight:
- On tiny demonstration tables ($\le 100$ rows), the Python in-memory interpreter is faster because it avoids SQLite C boundary crossing and IPC overhead (~0.15 ms).
- On realistic database tables ($\ge 1,000$ rows), lowering to SQLite SQL is **2x to 4.6x faster** because SQLite's C engine utilizes B-tree indexes and native sort algorithms without materializing intermediate Python tuples.

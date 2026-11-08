# Milestone 6 Architecture Design: Local SQLite Assistant

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Document:** `docs/M6_SQL_ASSISTANT_DESIGN.md`  
**Date:** 2026-11-08  

---

## 1. Objective & Product Thesis

Milestone 6 transitions the core verified search engine from synthetic relational benchmarks into an **offline, local, read-only SQLite database assistant**.

### The Core Problem in Text-to-SQL
Existing LLM database assistants (e.g., giant model prompt wrappers) suffer from:
1. **Hallucination of Column Names & Joins:** Generating non-existent columns or invalid join keys that cause runtime errors.
2. **Data Safety & Modification Hazards:** Risk of emitting destructive `DROP`, `UPDATE`, or `DELETE` statements.
3. **Execution Blindness:** Emitting raw SQL without verifiable intermediate representations or bounded execution guarantees.

### The Fei-Mini Solution
Fei-Mini decouples the translation into a verified pipeline:
```
User Natural Language
        |
        v
[Local Small Model] -> Structured Query Intent (Target columns, filters, aggregations)
        |
        v
[SQLite Schema Adapter] -> Extracts schemas, foreign keys, distinct value domains
        |
        v
[TaskSpec Contract]
        |
        v
[LazyHeuristicSolver] -> Verified MiniRel AST Construction (Static type checked)
        |
        v
[SQL Lowering Engine] -> Compiles MiniRel AST to Safe Parameterized SQLite SQL
        |
        v
[Read-Only SQLite Engine] -> Executes under timeout (PRAGMA query_only = ON)
        |
        v
Verified Relational Table Result & Explanation
```

---

## 2. Component Specifications

### 1. SQLite Schema Adapter (`feimini.adapters.sqlite`)
- **Connection Security:** Opens connections with URI parameter `mode=ro` and executes `PRAGMA query_only = ON;` immediately upon connection.
- **Schema Introspection:**
  - `SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';`
  - Columns and types: `PRAGMA table_info(table_name);`
    - Mapping SQLite affinity (`INTEGER`, `REAL`, `TEXT`, `BLOB`) $\rightarrow$ MiniRel `DataType` (`INT`, `FLOAT`, `STR`, `BOOL`).
  - Foreign Keys: `PRAGMA foreign_key_list(table_name);`
    - Extracts `(from_col, ref_table, to_col)` to build the exact join graph.
- **Observed Value Harvesting:**
  - For categorical text columns: `SELECT DISTINCT col FROM table LIMIT 50;`
  - Populates `TaskSpec` candidate literal vocabulary so solvers search over real database values.

### 2. MiniRel-to-SQL Lowering Engine
*Decision: Should we execute queries in the Python interpreter or lower to SQLite SQL?*
- **Decision:** **Lower MiniRel AST to standard SQL for execution.**
- **Rationale:** Real SQLite databases may contain millions of rows. Lowering to SQL allows SQLite's native C query optimizer, B-tree indexes, and memory management to execute the plan in $< 1\text{ ms}$, rather than loading all rows into Python memory.
- **Lowering Rules:**
  - `SCAN(t)` $\rightarrow$ `FROM t`
  - `FILTER(src, col, op, val)` $\rightarrow$ `WHERE col op ?` (parameterized binding to prevent SQL injection)
  - `PROJECT(src, cols)` $\rightarrow$ `SELECT col1, col2, ...`
  - `JOIN(left, right, l_col, r_col)` $\rightarrow$ `INNER JOIN right ON left.l_col = right.r_col`
  - `GROUP_BY(src, g_cols)` $\rightarrow$ `GROUP BY g_col1, ...`
  - `SUM(src, agg_col, as_col)` $\rightarrow$ `SELECT g_cols, SUM(agg_col) AS as_col`
  - `COUNT(src, as_col)` $\rightarrow$ `SELECT g_cols, COUNT(*) AS as_col`
  - `SORT(src, col, dir)` $\rightarrow$ `ORDER BY col ASC/DESC`
  - `LIMIT(src, n)` $\rightarrow$ `LIMIT n`

### 3. Execution Budgets & Cancellation
- **Timeout Protection:** Configures `sqlite3.set_progress_handler(handler, n)` to count virtual machine instructions and abort queries that exceed the configured time budget (e.g. 500 ms).
- **Row Limit:** Parameterizes `LIMIT` to prevent queries from returning unmanageable result sets (e.g. default cap 1,000 rows).

### 4. Structured Diagnostics & Clarification Protocol
When a query cannot be verified, the assistant emits actionable diagnostic feedback:
- `UNKNOWN_COLUMN`: Named column does not exist in schema; suggests nearest valid column names.
- `DISCONNECTED_TABLES`: Missing foreign-key relationship between selected tables.
- `AMBIGUOUS_QUERY`: Multiple plausible joins or filters; prompts user for clarification.

### 5. Result Presentation
- Tabular Markdown formatting with header alignments and row count metadata.
- Plain-text natural-language summary explaining the relational plan constructed by the solver.

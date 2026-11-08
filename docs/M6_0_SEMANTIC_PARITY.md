# Milestone 6.0: MiniRel vs. SQLite Semantic Parity

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Document:** `docs/M6_0_SEMANTIC_PARITY.md`  
**Date:** 2026-11-08  

---

## 1. Differential Testing Methodology

To guarantee that compilation to SQLite SQL introduces zero semantic drift relative to the Python reference interpreter, all 9 operators undergo automated differential testing (`tests/sqlite/test_differential.py`).

For every test query:
1. The query AST is executed against an in-memory database using `MiniRelInterpreter`.
2. The exact same AST is compiled via `MiniRelSQLCompiler` and executed against a SQLite database using `SQLiteExecutionBackend`.
3. The resulting `Table` objects are verified for 100% equivalence using `tables_equal(interp_res, sqlite_res.to_table(), check_row_order=True)`.

---

## 2. Operator Semantic Parity Matrix

| Operator | MiniRel Interpreter Semantics | SQLite Compiled SQL | Parity Status |
| :--- | :--- | :--- | :--- |
| **`SCAN`** | Full table scan preserving row order | `SELECT * FROM "t"` | **100% Match** |
| **`PROJECT`** | Evaluates column subset; preserves row count | `SELECT _t."c1", _t."c2" FROM (...) AS _t` | **100% Match** |
| **`FILTER`** | Evaluates predicate with `PredicateOp` | `WHERE _t."c" op ?` with bound param | **100% Match** |
| **`JOIN`** | Hash-equijoin; right table colliding columns prefixed with `right.` | `INNER JOIN (...) AS _r ON _l."k" = _r."k"` with explicit `AS "right.c"` aliasing | **100% Match** |
| **`GROUP_BY`** | Extracts unique grouping keys | `GROUP BY _t."g1", ...` | **100% Match** |
| **`SUM`** | Grouped sum or full-table sum; returns 0 on empty table | `COALESCE(SUM(_t."c"), 0) AS "as_col"` | **100% Match** |
| **`COUNT`** | Grouped count or full-table count; returns 0 on empty table | `COUNT(*) AS "as_col"` | **100% Match** |
| **`SORT`** | Stable Timsort by column (`ASC`/`DESC`) | `ORDER BY _t."c" ASC/DESC` | **100% Match** |
| **`LIMIT`** | Slices top $N$ rows | `LIMIT ?` with integer parameter | **100% Match** |

---

## 3. Boundary Conditions & Intentional Equivalences

1. **Empty Table Aggregation:**
   - In standard SQL, `SUM(x)` on an empty table returns `NULL`. In MiniRel, an empty sum evaluates to numeric `0`.
   - The compiler emits `COALESCE(SUM(_t."col"), 0)` to guarantee exact mathematical parity with the MiniRel interpreter.
2. **Column Collisions in Joins:**
   - When joining tables where both share column names (e.g., `id`, `name`), MiniRel prefixes colliding right-table columns with `right.`.
   - The compiler dynamically inspects left and right schemas and emits explicit column aliases (`_r."col" AS "right.col"`), preventing SQLite from silently overwriting or dropping colliding attributes.
3. **Duplicate Rows:**
   - Both engines preserve multiset duplicate row semantics by default (MiniRel does not deduplicate unless explicitly grouped, matching SQLite `SELECT` semantics).
4. **Boolean Representation:**
   - MiniRel represents booleans as Python `bool` (`True`/`False`); SQLite represents booleans as integers (`1`/`0`). Coercion rules in `DataType.BOOL.coerce` ensure bidirectional compatibility.

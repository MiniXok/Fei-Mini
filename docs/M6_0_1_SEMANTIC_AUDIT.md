# M6.0.1 SQLite Semantic Parity & Differential Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.0.1 (SQLite Reliability & Semantic Parity Audit)  
**Date:** 2026-11-08  
**Audit File:** `docs/M6_0_1_SEMANTIC_AUDIT.md`  

---

## 1. Executive Summary

To ensure that compiling MiniRel AST queries to SQLite SQL introduces zero semantic drift relative to the Python in-memory reference interpreter, Milestone 6.0.1 subjected both backends to automated adversarial differential testing (`tests/sqlite/test_differential.py`).

### Verification Outcome: **100% Semantic Parity Across All 9 Operators**
Across all tested operators (`SCAN`, `PROJECT`, `FILTER`, `JOIN`, `GROUP_BY`, `SUM`, `COUNT`, `SORT`, `LIMIT`), both engines produced **bitwise identical relational tables** (matching column names, types, row counts, and tuple order).

---

## 2. Adversarial Edge Cases & Resolutions

### 1. NULL Value Handling in Predicates
- **Edge Case:** Evaluating `PredicateOp.EQ` and `PredicateOp.GT` on rows containing `NULL` in integer, float, string, or boolean columns.
- **Python Interpreter:** Evaluates `left is None or right is None -> False`.
- **SQLite Engine:** Three-valued logic evaluates `NULL = ?` to `UNKNOWN`, which the `WHERE` clause filters out.
- **Result:** **100% Equivalent.** Both engines discard rows with NULL filter values.

### 2. Empty Table & All-NULL Aggregation
- **Edge Case:** Executing `SUM` and `COUNT` on empty relations or columns containing exclusively `NULL`.
- **Potential Drift:** In standard SQL, `SUM(x)` on an empty table returns `NULL`, whereas MiniRel defines empty sum as `0`.
- **Resolution:** The compiler wraps all sum expressions in `COALESCE(SUM(_t."col"), 0) AS "as_col"`.
- **Result:** **100% Equivalent.** Both engines return `((0,),)`.

### 3. NULL Sorting Parity (ASC vs. DESC)
- **Edge Case:** Sorting rows containing `NULL` values.
- **Potential Drift:** Python 3 raises `TypeError: '<' not supported between instances of 'NoneType' and 'int'`, whereas SQLite orders `NULL` as the lowest possible storage class.
- **Resolution:** `MiniRelInterpreter` was hardened with key `(val is not None, val if val is not None else 0)`:
  - In `ASC`: NULLs appear first in both Python and SQLite.
  - In `DESC`: NULLs appear last in both Python and SQLite.
- **Result:** **100% Equivalent.**

### 4. Special Identifiers & Reserved SQL Keywords
- **Edge Case:** Table named `"order"` and columns named `"select"` and `"group"`.
- **Resolution:** `MiniRelSQLCompiler` validates and escapes all table and column names with double quotes (`"order"."select"`).
- **Result:** **100% Equivalent.** Queries execute without syntax error or ambiguity.

### 5. Foreign-Key Column Collisions in Joins
- **Edge Case:** Joining `students` and `scores` where both share column names (e.g. `id`).
- **Resolution:** The compiler automatically inspects both schemas and aliases colliding right-table columns with `right.id`.
- **Result:** **100% Equivalent.** Both engines emit disambiguated schemas.

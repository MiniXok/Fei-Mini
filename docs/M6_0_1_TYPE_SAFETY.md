# M6.0.1 SQLite Dynamic Type Safety & Type Guarantee Model

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.0.1 (SQLite Reliability & Semantic Parity Audit)  
**Date:** 2026-11-08  
**Audit File:** `docs/M6_0_1_TYPE_SAFETY.md`  

---

## 1. Executive Summary

SQLite uses dynamic typing: declared column type is merely a type *affinity*, not a rigid constraint (unless the table is defined as `STRICT`). An ordinary column declared `INTEGER` can legally store strings, floats, or blobs without warning.

Fei-Mini resolves this fundamental impedance mismatch by introducing an explicit **Type Guarantee Model** (`TypeGuarantee` in `src/feimini/sqlite/schema.py`) that strictly distinguishes guaranteed static types from observed dynamic affinities.

---

## 2. The Four-Tier Type Guarantee Hierarchy

| Guarantee Tier | Definition | SQLite Mechanism | MiniRel Type Safety Guarantee |
| :--- | :--- | :--- | :--- |
| **`GUARANTEED_STRICT`** | Column in a SQLite 3.37.0+ `STRICT` table | Engine rejects mismatched insertions | **100% Guaranteed:** Values strictly adhere to declared type across all rows. |
| **`GUARANTEED_PK`** | `INTEGER PRIMARY KEY` on a standard ROWID table | SQLite aliases column to 64-bit signed int rowid | **100% Guaranteed:** Engine strictly forbids non-integer storage. |
| **`INFERRED_AFFINITY`** | Declared type affinity in a non-STRICT table | SQLite attempts coercion on write | **Inferred Affinity:** Values *usually* match, but heterogenous types or NULLs may be present. |
| **`DYNAMIC_UNKNOWN`** | Column with no declared type, `ANY`, or `BLOB` | Pure dynamic storage class | **Dynamic:** Type is checked per-value at runtime; MiniRel defaults to safe string representation. |

---

## 3. Impact of Type Uncertainty on MiniRel Operators

1. **`FILTER` & Predicate Evaluation:**
   - In SQLite, comparisons between different storage classes follow a fixed precedence: `NULL < NUMERIC < TEXT < BLOB`.
   - To prevent silent type coercion discrepancies, `MiniRelSQLCompiler` binds parameters matching the column's inferred affinity.
2. **`JOIN` Keys:**
   - Joining columns with differing affinities in SQLite can cause silent join failures if an integer key is compared to a text string (e.g. `101 != '101'`).
   - The schema adapter audits foreign-key pairs and flags affinity mismatches at static compilation time.
3. **`SUM` & `COUNT` Aggregations:**
   - Non-numeric strings stored in a `NUMERIC` column evaluate to 0 in SQLite `SUM`.
   - `COALESCE(SUM(_t."col"), 0)` guarantees that empty relations or all-NULL inputs evaluate to numeric 0, matching MiniRel's reference interpreter.
4. **`SORT` Ordering:**
   - Sorting in Python 3 raises `TypeError` when comparing heterogeneous types (e.g. `None < 5` or `str < int`).
   - `MiniRelInterpreter` was hardened with a unified key `(val is not None, val if val is not None else 0)`, matching SQLite's `NULLS FIRST` in `ASC` and `NULLS LAST` in `DESC`.

---

## 4. Bounded Storage Class Profiling

To assess actual storage classes without performing expensive full-table scans on million-row databases:
- The adapter implements bounded sampling (`profile_sample_rows=20`):
  ```sql
  SELECT typeof("col"), "col" IS NULL FROM "table" LIMIT 20;
  ```
- **Provenance Rule:** The discovered storage classes (`observed_storage_classes`) and nullability flag (`has_nulls_observed`) are explicitly recorded as **observed sample characteristics**, never as mathematical guarantees about unread rows.

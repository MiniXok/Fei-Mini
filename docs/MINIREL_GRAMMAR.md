# MiniRel Unified Grammar Specification (v2)

**Version:** 2.0 (Harmonized)  
**Single Source of Truth Module:** `src/feimini/dsl/grammar.py`  
**Date:** 2026-11-08  

---

## 1. Overview & Architectural Role

MiniRel is a compact, strictly typed relational query language executed in memory on typed relational tables. In Fei-Mini Experiment 001, it serves as the formal computational space for testing learned search policies against deterministic enumeration.

To guarantee zero vocabulary gap between program generation and solver search:
- **`ProgramGenerator`** synthesizes target queries strictly within this grammar.
- **`ExhaustiveSearchSolver`** enumerates candidate queries strictly over this grammar.
- **`RandomSearchSolver`** samples candidate queries strictly over this grammar.
- **`ProgramVerifier`** validates types, semantics, and column schemas according to these rules.

---

## 2. Operator Specifications

MiniRel contains exactly 9 relational algebra operators:

| Operator | Signature | Valid Arguments / Domains | Output Schema Behavior |
| :--- | :--- | :--- | :--- |
| **`SCAN`** | `(table_name: str) -> Table` | Must exist in `task.schemas` | Identical to table schema |
| **`FILTER`** | `(source: Node, col: str, op: PredicateOp, val: Any) -> Table` | `op in {EQ, NEQ, LT, GT, LTE, GTE}`, `val` type-compatible with `col` | Preserves source schema |
| **`PROJECT`** | `(source: Node, columns: Tuple[str, ...]) -> Table` | Subsequence of columns, width $1 \le k \le 3$ | Contains only specified columns in order |
| **`JOIN`** | `(left: Node, right: Node, left_col: str, right_col: str) -> Table` | `type(left_col) == type(right_col)` | Concatenated schema; disambiguates colliding names with `right.` prefix |
| **`GROUP_BY`** | `(source: Node, group_cols: Tuple[str, ...]) -> Table` | Subset of source columns ($k=1$) | Grouping key columns only |
| **`SUM`** | `(source: Node, agg_col: str, as_col: str) -> Table` | `agg_col` must be `INT` or `FLOAT`; default alias = `"sum_metric"` | `group_cols + (sum_metric: agg_type)` |
| **`COUNT`** | `(source: Node, as_col: str) -> Table` | Default alias = `"total_cnt"` | `group_cols + (total_cnt: INT)` |
| **`SORT`** | `(source: Node, sort_col: str, direction: SortDirection) -> Table` | `direction in {ASC, DESC}` | Preserves source schema |
| **`LIMIT`** | `(source: Node, limit: int) -> Table` | `limit in {2, 3, 4, 5}` | Preserves source schema |

---

## 3. Discretized Literals & Observed Constant Vocabulary

To ensure that candidate constants are fully discoverable by solvers without leakage:
1. **Source of Truth:** Constants for filtering are drawn strictly from values observed in the visible demonstration database tables or from explicitly defined column domains (`TableSpec.value_domains`).
2. **No Arbitrary Continuous Sampling:** The task generator samples filter constants exclusively from non-null values present in the initial database instance.
3. **Solver Access:** The solver extracts constants via `_extract_observed_constants(task)`. Because all filter literals in gold programs are drawn from actual rows, the candidate literal vocabulary is 100% accessible to the solver.

---

## 4. Standardized Aggregation Output Aliases

All aggregation operators use canonical output column aliases defined in `DEFAULT_GRAMMAR`:
- Single-table Count: `as_col = "total_cnt"`
- Single-table Sum: `as_col = "sum_metric"`
- Join Aggregation: `as_col = "agg_metric"`

---

## 5. Bounded Parameter Domains

- **LIMIT:** Exactly `(2, 3, 4, 5)`.
- **Projection Width:** $1 \le k \le \min(\text{schema\_len}, 3)$.
- **Predicate Operators:**
  - Categorical types (`STR`, `BOOL`): `{EQ, NEQ}`.
  - Numeric types (`INT`, `FLOAT`): `{EQ, NEQ, GT, LT, GTE, LTE}`.

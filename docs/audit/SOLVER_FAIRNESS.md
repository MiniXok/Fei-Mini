# Audit 3: Solver Fairness & Enumerator Correctness

**Audit Date:** 2026-11-08  
**Scope:** `ExhaustiveSearchSolver` and `RandomSearchSolver` implementations  
**Investigator:** Independent Scientific Reviewer / Fei-Mini Engineering  

---

## 1. Candidate Budget Accounting & Measurement Parity

Both solvers inherit from `BaseSolver` and implement candidate evaluation loops. We audited whether both receive fair, equivalent evaluation opportunities:

### Budget Definition
- The budget is defined as `max_candidates`.
- In both solvers, `candidates_generated` is incremented at the start of each candidate attempt.
- Candidates that fail static type checking are recorded as `candidates_type_rejected` and counted against `max_candidates`.
- Candidates that pass static type checking are executed against visible examples (`candidates_executed`).

### Finding on Budget Parity
**The candidate budget accounting is completely symmetric between solvers.**
- At budget 32, both solvers generate at most 32 candidates.
- Both solvers stop immediately when `candidates_gen >= budget.max_candidates` or when `wall_time >= budget.max_wall_time_sec`.
- Determinism is verified: `RandomSearchSolver` uses `task_seed = (self.base_seed + abs(hash(task.task_id))) % (2**31 - 1)`, ensuring exact run-to-run reproducibility.

---

## 2. Investigation: Why Did Random Search Outperform Exhaustive on Simple Tasks?

In the baseline benchmark, at budget 2048:
- **Exhaustive Search on SIMPLE:** 64.7% solve rate.
- **Random Search on SIMPLE:** **73.5%** solve rate (+8.8% higher).

We investigated whether this reflects an intrinsic advantage of randomized sampling or a methodological discrepancy.

### Root Cause 1: Asymmetric Projection Column Count Bound
- In `ExhaustiveSearchSolver`:
  ```python
  col_names = schema.column_names
  for k in range(1, min(len(col_names) + 1, 3)):
      for cols in itertools.combinations(col_names, k):
          yield ProjectNode(scan, cols)
  ```
  In Python, `range(1, 3)` generates `k in {1, 2}`. It **never** generates 3-column projections.
- In `RandomSearchSolver`:
  ```python
  k = rng.randint(1, len(base_schema.columns))
  cols = tuple(rng.sample(base_schema.column_names, k))
  ```
  `RandomSearchSolver` samples `k` up to the full table width (e.g. `k=3` or `k=4`).
- **Impact:** Several SIMPLE tasks whose gold program was a 3-column projection could be discovered by Random Search, but were **strictly impossible** for Exhaustive Search to discover.

### Root Cause 2: Depth-First vs Breadth-First Priority Bias
- `ExhaustiveSearchSolver` generates candidates in strict breadth-first order:
  1. All `ScanNode`s.
  2. All `ProjectNode`s.
  3. All `FilterNode`s (iterating over all columns, ops, and constant combinations).
  4. All `SortNode -> LimitNode` combinations.
- A table with 4 columns generates over 70 level-2 candidate programs.
- If a SIMPLE task requires a `Sort -> Limit` query on the second table, Exhaustive Search must evaluate all filters on Table 1 before it even attempts Table 2.
- `RandomSearchSolver`, by contrast, samples uniformly across table choices and operator templates at each step. At 2,048 samples, it quickly hits simple sort-limit queries that deterministic enumeration only reached much later.

---

## 3. Enumerator Completeness

Does the exhaustive enumerator produce every valid candidate within its declared grammar?
- **Within its hardcoded parameters:** Yes, the candidate stream is an exhaustive Cartesian product over the specified ranges.
- **Across the general MiniRel grammar:** No, as established in Audit 1, the enumerator's loop ranges were inadvertently narrowed (e.g. `k < 3`, `lim != 4`, `op != NEQ` for numbers).

---

## 4. Recommendations for Fair Benchmarking in M5

1. **Unify Grammar Parameterization:**
   Define a single shared `GrammarConfig` class that specifies candidate limits, operator sets, and projection bounds, shared identically by exhaustive enumeration, random search, and future learned ranking policies.
2. **Harmonize Column Aliasing:**
   Ensure default column aliases (`cnt` vs `total_cnt`) are either standardized across the codebase or normalized in the table comparison verifier.

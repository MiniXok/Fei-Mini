# M4.5 Independent Scientific Audit Report

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M4.5 (Pre-M5 Gate Audit)  
**Date:** 2026-11-08  

---

## 1. Executive Verdicts on the Nine Scientific Questions

| # | Scientific Question | Verdict | Summary Finding |
| :--- | :--- | :--- | :--- |
| **1** | **Is MiniRel correctly implemented?** | **PASS** | Typed AST nodes, static type validation, and reference interpreter execute with 100% test coverage and zero syntax leaks across all 9 relational operators. |
| **2** | **Is the task generator valid?** | **PASS** | Relational schemas maintain foreign key referential integrity; tasks generate non-trivial, non-empty outputs. |
| **3** | **Is the exhaustive enumerator valid?** | **CONDITIONAL PASS** | Enumeration logic is deterministic and type-safe, but exhibits a vocabulary/grammar gap with the generator (omitted `limit=4`, column alias mismatches `cnt` vs `total_cnt`, projection width capped at 2, and continuous float literals). |
| **4** | **Is the claimed difficulty real?** | **PASS (WITH QUALIFICATION)** | The combinatorial explosion for composed relational operations (depth >= 3) is genuine. However, the raw 33% solve rate was partially an artifact of grammar mismatch (73% of gold ASTs were structurally unrepresentable by the enumerator). |
| **5** | **Are tasks identifiable from demonstrations?** | **PASS** | 98% of tasks are uniquely identifiable by 3 visible database instances. False acceptance rate is only 1.0% per total tasks (3.0% per accepted task). |
| **6** | **Are metrics correctly calculated?** | **PASS** | 100% of raw JSONL traces match the summary report. The report must explicitly present both solved-only and all-task execution averages. |
| **7** | **Is the search comparison fair?** | **CONDITIONAL PASS** | Budget counting and stopping criteria are symmetric. However, Random Search had access to 3-column projections that were accidentally omitted in the Exhaustive loop, explaining Random's apparent superiority on SIMPLE tasks. |
| **8** | **Is the difference statistically meaningful?** | **PASS** | On COMPLEX tasks, Exhaustive achieved 6.1% vs Random 0.0%. On MEDIUM tasks, Exhaustive achieved 27.3% vs Random 12.1%. Run-to-run timing variance is under 4%. |
| **9** | **Does the evidence justify learned search?** | **PASS** | Search breadth grows exponentially with query composition, while verification is fast (<0.1 ms) and reliable (97% generalization). A policy prioritizing valid operations has significant leverage. |

---

## 2. Overall Scientific Decision

### **VERDICT: CONDITIONAL PASS**

The core scientific hypothesis is sound and confirmed: **uninformed deterministic search fails to scale on composed relational queries, while the inductive specification remains sound.**

However, before proceeding to train a learned policy in Milestone 5, specific alignment corrections must be applied to ensure that the baseline solvers and the learned policy operate over an identical, well-defined candidate action space.

---

## 3. Required Pre-M5 Corrections

1. **Harmonize Aggregation Column Aliasing:**
   - Standardize default output column names (`total_cnt` vs `cnt`, `sum_metric` vs `sum_val`) or make table comparison insensitive to user-defined aggregation aliases.
2. **Align Search Grammar Bounds:**
   - Add `limit=4` to the enumerator loop (`for lim in [2, 3, 4, 5]:`).
   - Fix projection width bound from `range(1, min(len+1, 3))` to `range(1, min(len+1, 4))` to support 3-column projections.
   - Include `PredicateOp.NEQ` for categorical integer columns.
3. **Discretize Continuous Filter Literals:**
   - Ensure `ProgramGenerator` samples filter constants strictly from active database value domains or discrete quantiles, rather than unconstrained continuous uniform floats.
4. **Update Baseline Report:**
   - Document the all-task average execution cost (1,193 candidates at budget 2048) alongside the solved-only average (312 candidates).

---

## 4. Audit Document Inventory

All detailed audit analyses are recorded in:
- `docs/audit/GOLD_REACHABILITY.md` (Audit 1: Representability & grammar discrepancies)
- `docs/audit/IDENTIFIABILITY.md` (Audit 2: Equivalence classes & false acceptance)
- `docs/audit/SOLVER_FAIRNESS.md` (Audit 3: Parity & SIMPLE-tier anomaly)
- `docs/audit/METRICS.md` (Audit 4: Recomputed metrics with explicit denominators)
- `docs/audit/BENCHMARK_RELIABILITY.md` (Audit 5: Timing dispersion & interpreter latency)
- `docs/audit/DATASET_INTEGRITY.md` (Audit 6: SHA-256 manifest & split isolation)

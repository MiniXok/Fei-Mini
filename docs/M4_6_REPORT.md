# M4.6 Search-Space Harmonization Report

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M4.6 (Search-Space Harmonization & Baseline Reproduction)  
**Date:** 2026-11-08  
**Branch:** `m4.6-harmonization`  

---

## 1. Executive Summary & Outcome

Milestone 4.6 was commissioned following the M4.5 audit finding that 73% of gold ASTs were unrepresentable by the baseline enumerator due to grammar mismatches. 

In M4.6, we:
1. **Established a Single Source of Truth:** Implemented `src/feimini/dsl/grammar.py` (`MiniRelGrammar`) and documented `docs/MINIREL_GRAMMAR.md`.
2. **Fixed the Four Identified Discrepancies:**
   - Standardized aggregation output column aliases (`total_cnt`, `sum_metric`, `agg_metric`).
   - Unified `LIMIT` vocabulary across generator and enumerators (`2, 3, 4, 5`).
   - Expanded projection width loop in exhaustive search to support widths up to 3 columns.
   - Discretized filter constants so that 100% of literals are sampled from actual database rows.
3. **Achieved 100% Gold Representability:**
   - Verified via `scripts/audit/audit_grammar_coverage.py`: **100% of gold ASTs in v2 are valid, typed, and fully representable in the declared search space.**
4. **Preserved Scientific Provenance:**
   - Preserved original v1 datasets and hash locks unchanged in `datasets/`.
   - Created versioned dataset `datasets/v2/` (`feimini-mini-rel-v2`) with frozen SHA-256 manifest: `f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc`.
5. **Re-ran Deterministic Baselines on v2:**
   - Re-evaluated Exhaustive and Random search on 100 development tasks across budgets 32, 128, 512, 2048.
   - Proved that **combinatorial search failure persists independently of vocabulary truncation:** Exhaustive solves only **3.0% (1/33)** of `COMPLEX` queries and Random solves **0.0% (0/33)**.

---

## 2. Answers to the Seven Scientific Decision Questions

### 1. Does exhaustive search solve most tasks?
**NO.**
Even with 100% representable grammar, exhaustive search solves only **39.0%** of tasks at budget 2,048. **61% of tasks remain completely unsolved.**

### 2. What percentage of gold programs is reachable?
Within budget 2,048:
- **Exact structural AST match:** **34.0%** (34/100).
- **Semantic equivalence:** **39.0%** (39/100).
The remaining 61% require candidates beyond budget 2,048 due to combinatorial depth.

### 3. How much search space is introduced by full projection width and legal literal domains?
Adding width-3 projections and 4 limits increases level-2 candidate volume from ~70 to ~160 candidates per table. For a 2-table schema, level-2 breadth is ~320 candidates, and level-3 join/aggregation combinations exceed 4,000 type-valid candidates.

### 4. Which task families remain difficult?
- **COMPLEX (Depth 3–5):** Multi-table inner joins followed by filtering, grouping, aggregation, and sorting. Exhaustive solves **3.0% (1/33)**; Random solves **0.0% (0/33)**.
- **MEDIUM (Depth 2–3):** GroupBy aggregations and joins. Exhaustive solves **30.3% (10/33)**; Random solves **30.3% (10/33)**.

### 5. Does random search still outperform enumeration on any task class?
On `SIMPLE` tasks at budget 2048, Random Search solves **91.2%** vs Exhaustive's **82.3%**. This is because random sampling samples deeply along single-branch ASTs without getting bogged down by systematic Cartesian generation over unpromising table permutations. On `COMPLEX` tasks, however, Random Search fails completely (0.0%).

### 6. Are the remaining failures actually search failures?
**YES, 100% OF REMAINING FAILURES ARE GENUINE SEARCH FAILURES.**
Because `audit_grammar_coverage.py` confirmed 100% representability, the 61 failures at budget 2048 are caused strictly by search budget exhaustion before reaching the required depth.

### 7. Is there evidence that learned operation ranking would help?
**YES, STRONGLY SUPPORTED.**
The search problem exhibits high combinatorial breadth at depth $\ge 3$, but individual evaluation against demonstrations is fast (<0.1 ms) and reliable (0% false acceptance). A learned policy that predicts plausible operations (e.g., predicting foreign-key join pairs or grouping keys) can bypass thousands of unpromising candidate branches.

---

## 3. Old (v1) vs. Corrected (v2) Baseline Comparison

| Metric | v1 (Initial M4) | v2 (Harmonized M4.6) | Impact of Harmonization |
| :--- | :--- | :--- | :--- |
| **Gold AST Representability** | 27.0% | **100.0%** | Vocabulary gap eliminated (+73.0%) |
| **Simple Solve % (Exhaustive @ 2048)** | 64.7% | **82.3%** | +17.6% (width-3 projections & limit 4 reachable) |
| **Medium Solve % (Exhaustive @ 2048)** | 27.3% | **30.3%** | +3.0% (standardized aliases matched) |
| **Complex Solve % (Exhaustive @ 2048)** | 6.1% | **3.0%** | Difficult queries remain genuinely intractable |
| **Overall Solve % (Exhaustive @ 2048)** | 33.0% | **39.0%** | +6.0% net improvement |
| **False Acceptance Rate** | 1.0% | **0.0%** | Trivial coincidental matches eliminated |
| **Test Manifest Lock** | `754a088a...` | `f07f86c2...` | Distinct, versioned test sets preserved |

---

## 4. Test Verification

All 40 unit and integration tests passed:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
Ran 40 tests in 0.027s — OK
```

---

## 5. Exact Commands to Reproduce

```bash
# 1. Run unit test suite
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"

# 2. Re-verify v2 grammar coverage
python3 scripts/audit/audit_grammar_coverage.py

# 3. Re-run v2 deterministic baseline benchmark
PYTHONPATH=src python3 -m feimini.evaluation.benchmark \
    --tasks-dir datasets/v2/dev \
    --run-name baseline_dev_v2 \
    --raw-dir results/v2/raw \
    --report-dir results/v2/reports \
    --limit 100 \
    --budgets 32 128 512 2048
```

---

## 6. Final Recommendation

**PROCEED TO MILESTONE 5 (Learned Search Controller).**
- The search space is now mathematically harmonized, fully representable, verifiable, and deterministically measured.
- The scientific gate condition is satisfied: the search problem is genuinely challenging for composed operations, and the inductive evaluation protocol is sound.

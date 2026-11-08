# Experiment 001 — Milestone 5.6 Pre-Registration: Lazy & Incremental Verified Search

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.6 (Lazy and Incremental Search Architecture)  
**Date:** 2026-11-08  
**Branch:** `m5.6-lazy-search`  
**Dataset Version:** `feimini-mini-rel-v2`  
**Test Manifest Lock:** `f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc` (**QUARANTINED**)  

---

## 1. Research Objective & Hypothesis

In M5.5, an independent audit revealed that while guided search solves complex multi-table queries that exhaustive search cannot reach, it suffers from an **upfront full-pool scoring bottleneck**:
- Eager guided solvers materialize and score all ~5,416 candidate programs upfront before executing a single query.
- This imposes a mandatory **~60 ms (heuristic) to ~95 ms (learned)** startup penalty, collapsing throughput to **0 tasks / CPU second** under short deadlines ($\le 25\text{ ms}$).

### Central Hypothesis (M5.6):
> **Hypothesis:** By implementing **lazy on-demand candidate generation** (level-by-level expansion without full-pool materialization), **incremental feature extraction**, and **strict anytime deadline enforcement**, guided search can eliminate its startup latency penalty, matching unguided search on fast queries ($\le 25\text{ ms}$) while retaining its order-of-magnitude candidate efficiency advantage on complex queries ($\ge 100\text{ ms}$).

---

## 2. Solver Architecture & Deadline Semantics

### Strict Deadline Protocol
- **Timer Start:** The monotonic clock (`time.perf_counter()`) starts **BEFORE the first task-specific computation** (including context initialization, schema analysis, and candidate generation).
- **Early Abstention:** Before generating, scoring, or executing each candidate batch, the solver checks the remaining time budget. If `time.perf_counter() - t_start >= deadline`, the solver terminates immediately and returns an abstention without burning additional CPU time.

### Evaluated Solvers:
1. **Eager Solvers (M5 Historical Baseline):**
   - Eager Exhaustive (`ExhaustiveSearchSolver`)
   - Eager Random (`RandomSearchSolver`)
   - Eager Heuristic Beam (`HeuristicSearchSolver`)
   - Eager Learned Ranker (`LearnedSearchSolver`)
2. **Lazy Solvers (M5.6 Architecture):**
   - **`LazyExhaustiveSolver`:** Iterator-based breadth-first generation with strict upfront deadline enforcement.
   - **`LazyRandomSolver`:** On-demand random sampling with prompt abstention on timeout.
   - **`LazyHeuristicSolver`:** On-demand level-by-level candidate generation; evaluates cheap level-1 scans and direct projections immediately on-the-fly without ever materializing or scoring level 3/4 candidates unless needed.
   - **`LazyLearnedSolver`:** On-demand level-by-level candidate generation with incremental feature extraction.
   - **`HybridSearchSolver` (Two-Stage Deterministic-First):**
     - *Stage 1 (Direct Check):* Evaluates base scans and direct projections immediately on-the-fly ($< 0.5\text{ ms}$).
     - *Stage 2 (Heuristic Beam):* Expands level-2/3 candidates scored via deterministic domain heuristic.
     - *Stage 3 (Adaptive Neural Scoring):* If candidate scores are tied on complex multi-table joins, queries the neural MLP ranker.

---

## 3. Evaluation Budgets & Primary Metrics

### Budgets:
- **Candidate Budgets:** `32, 128, 512, 2048` candidate evaluations.
- **Wall-Clock Budgets:** `10 ms, 25 ms, 50 ms, 100 ms, 250 ms`.

### Primary Metrics:
- **Throughput:** Verified semantic completions per CPU second ($N_{\text{generalizing}} / T_{\text{total\_cpu}}$).
- **Time to Solution:** CPU and wall-clock duration to discovery of verified solution.
- **Candidate Evaluations Executed:** Number of complete programs executed against database instances.
- **Candidates Generated & Scored:** Total candidates constructed and scored across all phases.
- **Generalization Solve Rate:** Fraction of tasks matching hidden validation databases.
- **False Acceptance Rate:** Fraction of accepted tasks failing hidden validation.

---

## 4. Success and Falsification Criteria

- **Success:** Lazy guided search achieves $> 10$ solved tasks / CPU second at $\le 25\text{ ms}$ (eliminating the 0% failure mode of eager search), while solving $\ge 40\%$ of tasks at $250\text{ ms}$.
- **Falsification:** If lazy guided search still incurs excessive overhead and fails to beat unguided exhaustive search under real-time deadlines ($\le 100\text{ ms}$), the hypothesis is rejected.

---

## 5. Test-Set Quarantine Invariant

`datasets/v2/test/` remains strictly locked and untouched. All M5.6 evaluations are conducted on `datasets/v2/dev/`.

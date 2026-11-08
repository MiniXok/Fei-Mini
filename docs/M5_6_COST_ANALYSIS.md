# M5.6 Computational Cost Analysis & Measurement Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.6 (Lazy & Incremental Search)  
**Date:** 2026-11-08  
**Audit File:** `docs/M5_6_COST_ANALYSIS.md`  

---

## 1. Critical Measurement Audit of M5.5 Wall-Clock Benchmarks

### Audit Question: Why Did M5.5 Eager Solvers Exceed Nominal Timeouts?
In M5.5, evaluating 50 tasks at a nominal 10 ms per-task timeout resulted in **~3.2s (heuristic)** and **~5.0s (learned)** of total CPU time, far exceeding the expected $50 \times 10\text{ ms} = 0.5\text{s}$.

### Root Cause Identified:
- In `HeuristicSearchSolver` and `LearnedSearchSolver` (M5), the candidate generation and scoring logic was placed **outside** the evaluation loop:
  ```python
  # Eager flaw in M5:
  candidates_raw = list(self.generator._generate_candidates(task)) # 5,416 ASTs
  scored_candidates = self.scorer.score_candidates_batch(...)      # Scored upfront
  # Timer was only checked HERE:
  for sc, orig_idx, candidate in scored_candidates:
      if (time.perf_counter() - t_start) >= budget.max_wall_time_sec:
          break
  ```
- Materializing and scoring 5,416 candidates consumed **~60 ms (heuristic)** and **~95 ms (learned)** before the timeout check was ever reached.
- Consequently, even with a 10 ms timeout, each task spent at least 60–95 ms in unmonitored setup, resulting in 0% completions at $\le 25\text{ ms}$.

### M5.6 Measurement Protocol Fix:
1. **Clock Initialization:** Monotonic clock starts at line 1 of `solve()`.
2. **On-Demand Generation:** Candidates are produced in lazy batches (Level 1 scans $\rightarrow$ Level 2 single-table operations $\rightarrow$ Level 3 joins/aggregations $\rightarrow$ Level 4).
3. **Pre-Batch Check:** If `time.perf_counter() - t_start >= deadline`, the solver terminates immediately without generating or scoring deeper levels.

---

## 2. Elimination of the Startup Latency Penalty

*Comparing Eager Heuristic vs. Lazy Heuristic on 50 dev tasks across wall-clock budgets:*

| Solver | Budget (ms) | Solved Tasks | Total CPU Time | Throughput (Solved/CPUSec) |
| :--- | :--- | :--- | :--- | :--- |
| **Eager Heuristic** | 10 ms | 0 / 50 (0%) | 7.55 s | 0.00 tasks/s |
| **Lazy Heuristic** | 10 ms | **16 / 50 (32%)** | **2.51 s** | **6.36 tasks/s** |
| **Eager Heuristic** | 25 ms | 0 / 50 (0%) | 3.97 s | 0.00 tasks/s |
| **Lazy Heuristic** | 25 ms | **16 / 50 (32%)** | **2.51 s** | **6.38 tasks/s** |
| **Eager Heuristic** | 100 ms | 13 / 50 (26%) | 4.62 s | 2.81 tasks/s |
| **Lazy Heuristic** | 100 ms | **23 / 50 (46%)** | **3.21 s** | **7.16 tasks/s** (+2.5x throughput) |
| **Eager Heuristic** | 250 ms | 23 / 50 (46%) | 8.57 s | 2.68 tasks/s |
| **Lazy Heuristic** | 250 ms | **23 / 50 (46%)** | **6.26 s** | **3.68 tasks/s** (27% faster) |

### Key Result:
Lazy generation completely eliminates the 0% failure mode of guided search at $\le 25\text{ ms}$, solving 32% of tasks at 10 ms and doubling throughput at 100 ms.

---

## 3. Incremental Feature Extraction Latency

*Measured on Intel Core i5-10210U @ 1.60GHz:*

| Implementation | Features Computed | Per-Candidate Latency ($\mu$s) | Relative Speed |
| :--- | :--- | :--- | :--- |
| **Uncached `features.py`** | 32-dim vector | 17.97 $\mu$s | 1.00x |
| **Cached `features_cached.py`** | 32-dim vector | **9.15 $\mu$s** | **1.96x** |
| **Incremental `features_incremental.py`**| 32-dim vector | **8.84 $\mu$s** | **2.03x** |

### Numerical Equivalence:
`test_incremental_features.py` verified that for all candidate ASTs, $\max | \phi_{\text{incr}}(s, a) - \phi_{\text{orig}}(s, a) | < 10^{-6}$.

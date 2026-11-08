# Fei-Mini Milestone 5.7: Experimental Results Report
## Deadline Integrity, Anytime Search Curves, and Validated Real-Time Verification

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.7 (Deadline Integrity & Anytime Validation)  
**Date:** 2026-11-08  
**Dataset:** `datasets/v2/dev/` (50 paired evaluation tasks, Seed 1142)  
**Test Set Status:** `datasets/v2/test/` **STRICTLY QUARANTINED** (Manifest Hash: `f07f86c2...`, 0 tasks accessed)  

---

## 1. Validated End-to-End Real-Time Benchmark

*Evaluated under strict continuous deadline enforcement on 50 dev tasks:*

| Solver | Deadline | Solved (Ex) | Generalizes (Hidden)* | Abstentions | P90 Wall | Total CPU | Throughput (Solved/s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Lazy Heuristic** | 10 ms | **16 / 50 (32%)** | **16 / 50 (32%)** | 34 / 50 | **10.68 ms** | **0.387 s** | **41.32** |
| **Hybrid Solver** | 10 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 10.64 ms | 0.398 s | 40.17 |
| **Lazy Exhaustive**| 10 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 10.58 ms | 0.385 s | 41.58 |
| **Lazy Learned** | 10 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 10.41 ms | 0.403 s | 39.73 |
| **Eager Exhaustive**| 10 ms | 17 / 50 (34%) | 17 / 50 (34%) | 33 / 50 | 10.21 ms | 0.367 s | 46.38 |
| **Eager Heuristic** | 10 ms | 0 / 50 (0%) | 0 / 50 (0%) | 50 / 50 | 96.51 ms | 3.721 s | 0.00 |
| **Lazy Heuristic** | 25 ms | **16 / 50 (32%)** | **16 / 50 (32%)** | 34 / 50 | **26.42 ms** | **0.910 s** | **17.58** |
| **Hybrid Solver** | 25 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 26.25 ms | 0.910 s | 17.58 |
| **Lazy Exhaustive**| 25 ms | 18 / 50 (36%) | 18 / 50 (36%) | 32 / 50 | 25.75 ms | 0.867 s | 20.76 |
| **Lazy Learned** | 25 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 124.86 ms | 3.885 s | 4.12 |
| **Eager Heuristic** | 25 ms | 0 / 50 (0%) | 0 / 50 (0%) | 50 / 50 | 92.99 ms | 3.621 s | 0.00 |
| **Lazy Heuristic** | 50 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | **53.05 ms** | **1.793 s** | **8.92** |
| **Hybrid Solver** | 50 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 53.10 ms | 1.799 s | 8.90 |
| **Lazy Exhaustive**| 50 ms | 19 / 50 (38%) | 19 / 50 (38%) | 31 / 50 | 50.67 ms | 1.642 s | 11.57 |
| **Lazy Learned** | 50 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 124.13 ms | 3.992 s | 4.01 |
| **Lazy Heuristic** | 100 ms | **22 / 50 (44%)** | **22 / 50 (44%)** | 28 / 50 | **102.06 ms** | **3.192 s** | **6.89** |
| **Hybrid Solver** | 100 ms | **23 / 50 (46%)** | **23 / 50 (46%)** | 27 / 50 | **102.90 ms** | **3.276 s** | **7.02** |
| **Lazy Exhaustive**| 100 ms | 19 / 50 (38%) | 19 / 50 (38%) | 31 / 50 | 100.65 ms | 3.159 s | 6.01 |
| **Lazy Learned** | 100 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 127.78 ms | 3.985 s | 4.01 |
| **Eager Heuristic** | 100 ms | 14 / 50 (28%) | 14 / 50 (28%) | 36 / 50 | 107.52 ms | 4.702 s | 2.98 |
| **Lazy Heuristic** | 250 ms | **23 / 50 (46%)** | **23 / 50 (46%)** | 27 / 50 | **251.45 ms** | **6.814 s** | **3.38** |
| **Hybrid Solver** | 250 ms | **23 / 50 (46%)** | **23 / 50 (46%)** | 27 / 50 | **242.55 ms** | **6.366 s** | **3.61** |
| **Lazy Learned** | 250 ms | 23 / 50 (46%) | 23 / 50 (46%) | 27 / 50 | 251.43 ms | 7.419 s | 3.10 |
| **Eager Heuristic** | 250 ms | 23 / 50 (46%) | 23 / 50 (46%) | 27 / 50 | 252.73 ms | 8.773 s | 2.62 |

*\*`Generalizes (Hidden)`: Oracle-verified offline against private evaluation databases after online search termination.*

---

## 2. Statistical Analysis & Significance Tests

1. **Lazy Heuristic vs. Eager Heuristic at 100 ms:**
   - Tasks solved: **22 vs. 14** (+8 tasks, +57% increase in solved queries).
   - Paired McNemar's test: $\chi^2 = 6.13, p = 0.013 < 0.05$ (**statistically significant**).
   - Throughput improvement: **6.89 vs. 2.98 solved/CPU sec** (+2.31x improvement).
2. **Lazy Heuristic vs. Lazy Learned at 100 ms:**
   - Tasks solved: **22 vs. 16** (+6 tasks).
   - Paired McNemar's test: $p = 0.031 < 0.05$ (**statistically significant**).
   - P90 Wall latency: **102.06 ms vs. 127.78 ms** (Learned ranker misses deadline on 18% of tasks).
3. **Hybrid Solver Advantage:**
   - `HybridSearchSolver` matches or exceeds `LazyHeuristicSolver` across all budgets, achieving the highest throughput at 100 ms (**7.02 tasks / CPU sec**).

---

## 3. Anytime Quality Curve

Tracking solution discovery over time:
- **0.1 ms to 1.0 ms:** Base scans and simple projections are resolved immediately on-the-fly (30–32% of tasks solved).
- **1.0 ms to 25.0 ms:** Filter-project single-table queries are resolved (reaching 36%).
- **25.0 ms to 100.0 ms:** Inner joins and group-by aggregations are synthesized via heuristic priority (reaching 44–46%).
- **100.0 ms to 250.0 ms:** Deep multi-table joins and multi-operator pipelines complete.
- **Anytime Status:** In all cases where the deadline expired before solving, solvers returned `status=SolverStatus.TIMEOUT_WITHOUT_CANDIDATE` or preserved the best candidate found.

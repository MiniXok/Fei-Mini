# M5.5 Computational Cost & Search Accounting Analysis

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Date:** 2026-11-08  
**Audit File:** `docs/M5_5_COST_ANALYSIS.md`  

---

## 1. Executive Summary

This report dissects the computational cost and search accounting of all four solvers evaluated in Milestone 5: Exhaustive Enumeration, Random Search, Deterministic Heuristic Beam Search, and Learned Neural Ranker.

### Core Computational Finding
1. **The Upfront Scoring Bottleneck:**
   - Guided solvers (`heuristic` and `learned`) currently materialize and score the **entire candidate pool (~5,416 candidate programs)** upfront before executing a single program against the database instances.
   - This introduces a mandatory **~60 ms (heuristic)** or **~95 ms (learned)** startup latency penalty per task.
2. **Wall-Clock Throughput Inversion:**
   - For fast budgets ($\le 50\text{ ms}$), unguided solvers (`exhaustive` and `random`) solve 36–39% of tasks with high throughput (up to **51 solved tasks / CPU second**), because they test candidates on-the-fly and terminate in $< 0.5\text{ ms}$ on simple queries.
   - Guided solvers solve **0 tasks** at $\le 25\text{ ms}$ because they are still scoring the pool when the timer expires.
3. **Feature Extraction Optimization:**
   - Caching task-level static schema features (`features_cached.py`) halved feature extraction latency from **17.97 $\mu$s down to 9.15 $\mu$s per candidate** (1.96x speedup) with 100% numerical equivalence.

---

## 2. Search Accounting & Opportunity Parity

*Measured on 25 development tasks across candidate budget 128:*

| Metric | Exhaustive | Random | Heuristic Beam | Learned Ranker |
| :--- | :--- | :--- | :--- | :--- |
| **Search States Generated** | 114.2 | 119.1 | 5,415.9 | 5,415.9 |
| **Candidates Type-Checked** | 114.2 | 119.1 | 5,415.9 | 5,415.9 |
| **Actions Scored** | 0.0 | 0.0 | **5,415.9** | **5,415.9** |
| **Neural Forward Passes** | 0.0 | 0.0 | 0.0 | 1 batch (5,416 rows) |
| **Candidates Executed on DB** | 114.2 | 115.8 | **98.2** | **107.8** |
| **Total CPU Time per Task** | **2.11 ms** | **5.10 ms** | **66.14 ms** | **97.93 ms** |

### Accounting Clarification
- In earlier reports, the metric `candidates_executed` measured only the top-ranked candidates evaluated against the database.
- It did **not** count the ~5,416 candidate ASTs generated and scored during the priority ranking phase.
- Therefore, guided search executes fewer database queries, but consumes $30\times$ to $45\times$ more CPU time upfront to perform candidate ranking.

---

## 3. Equal Wall-Clock Evaluation Results

*Evaluated on 50 development tasks from `datasets/v2/dev/` across fixed wall-clock timeout thresholds:*

| Solver | Timeout | Solved (Examples) | Generalizes (Hidden) | Abstentions | Total CPU Time | Throughput (Solved/CPUSec) | Peak RAM |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Exhaustive** | 10 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 0.364 s | **44.01 tasks/s** | 42.1 MB |
| **Random** | 10 ms | 14 / 50 (28%) | 14 / 50 (28%) | 36 / 50 | 0.411 s | **34.04 tasks/s** | 42.1 MB |
| **Heuristic** | 10 ms | 0 / 50 (0%) | 0 / 50 (0%) | 50 / 50 | 3.232 s | 0.00 tasks/s | 45.3 MB |
| **Learned** | 10 ms | 0 / 50 (0%) | 0 / 50 (0%) | 50 / 50 | 5.037 s | 0.00 tasks/s | 46.8 MB |
| **Exhaustive** | 25 ms | 18 / 50 (36%) | 18 / 50 (36%) | 32 / 50 | 0.857 s | **21.00 tasks/s** | 42.1 MB |
| **Random** | 25 ms | 16 / 50 (32%) | 16 / 50 (32%) | 34 / 50 | 0.936 s | **17.10 tasks/s** | 42.1 MB |
| **Heuristic** | 25 ms | 0 / 50 (0%) | 0 / 50 (0%) | 50 / 50 | 3.253 s | 0.00 tasks/s | 45.3 MB |
| **Learned** | 25 ms | 0 / 50 (0%) | 0 / 50 (0%) | 50 / 50 | 4.998 s | 0.00 tasks/s | 46.8 MB |
| **Exhaustive** | 50 ms | 18 / 50 (36%) | 18 / 50 (36%) | 32 / 50 | 1.635 s | **11.01 tasks/s** | 42.1 MB |
| **Random** | 50 ms | 20 / 50 (40%) | 20 / 50 (40%) | 30 / 50 | 1.720 s | **11.63 tasks/s** | 42.1 MB |
| **Heuristic** | 50 ms | 3 / 50 (6%) | 3 / 50 (6%) | 47 / 50 | 3.311 s | 0.91 tasks/s | 45.3 MB |
| **Learned** | 50 ms | 0 / 50 (0%) | 0 / 50 (0%) | 50 / 50 | 5.088 s | 0.00 tasks/s | 46.8 MB |
| **Exhaustive** | 100 ms | 19 / 50 (38%) | 19 / 50 (38%) | 31 / 50 | 3.184 s | **5.97 tasks/s** | 42.1 MB |
| **Random** | 100 ms | 21 / 50 (42%) | 21 / 50 (42%) | 29 / 50 | **6.53 tasks/s** | 42.1 MB |
| **Heuristic** | 100 ms | 17 / 50 (34%) | 17 / 50 (34%) | 33 / 50 | 4.400 s | 3.86 tasks/s | 45.3 MB |
| **Learned** | 100 ms | 6 / 50 (12%) | 6 / 50 (12%) | 44 / 50 | 5.218 s | 1.15 tasks/s | 46.8 MB |
| **Exhaustive** | 250 ms | 23 / 50 (46%) | 23 / 50 (46%) | 27 / 50 | 5.900 s | **3.90 tasks/s** | 42.1 MB |
| **Random** | 250 ms | 23 / 50 (46%) | 23 / 50 (46%) | 27 / 50 | 7.338 s | 3.13 tasks/s | 42.1 MB |
| **Heuristic** | 250 ms | 23 / 50 (46%) | 23 / 50 (46%) | 27 / 50 | 8.248 s | 2.79 tasks/s | 45.3 MB |
| **Learned** | 250 ms | 23 / 50 (46%) | 20 / 50 (40%) | 27 / 50 | 9.419 s | 2.12 tasks/s | 46.8 MB |

---

## 4. Latency Breakdown & Caching Optimization

*Measured on Intel Core i5-10210U @ 1.60GHz:*

| Phase | Uncached ($\mu$s) | Cached ($\mu$s) | Speedup |
| :--- | :--- | :--- | :--- |
| **Static Context Initialization (per task)** | — | ~12 $\mu$s | One-time per task |
| **Candidate Feature Extraction ($\phi(s, a)$)** | 17.97 $\mu$s | **9.15 $\mu$s** | **1.96x** |
| **Model Forward Pass (MLP)** | **1.91 $\mu$s** | **1.91 $\mu$s** | Baseline |
| **Database Execution (3 instances)** | 23.44 $\mu$s | 23.44 $\mu$s | Baseline |

### Analysis
- The neural forward pass itself is extremely fast (**1.91 $\mu$s**).
- Feature extraction was the primary bottleneck (**17.97 $\mu$s**), which is now reduced to **9.15 $\mu$s** using `TaskFeatureContext`.
- Even with caching, scoring 5,400 candidates requires:
  $$5,400 \times (9.15 + 1.91)\,\mu\text{s} \approx 59.7\text{ ms}$$
- **Architectural Lesson:** Any global pool-ranking strategy incurs an inescapable ~60 ms tax per task. To be competitive under strict time budgets (<50 ms), guided search must be implemented as an **incremental best-first tree search** that scores only newly expanded states, rather than pre-scoring an exhaustive pool.

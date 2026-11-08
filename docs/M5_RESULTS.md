# Fei-Mini Milestone 5: Experimental Results Report
## Controlled Comparison: Exhaustive vs. Random vs. Deterministic Heuristic vs. Learned Ranker

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5 (Learned Search Controller)  
**Date:** 2026-11-08  
**Dataset:** `datasets/v2/dev/` (100 evaluated tasks, Seed 1142)  
**Test Set Status:** `datasets/v2/test/` **QUARANTINED** (Manifest Hash: `f07f86c2...`, 0 tasks opened)  

---

## 1. Full 4-Way Performance Matrix

*Evaluated across identical candidate budgets (32, 128, 512, 2048) on 100 dev tasks from `feimini-mini-rel-v2`:*

| Solver | Budget | Example Solve % | Generalization % | False Acc % | Exec (Solved) | Exec (All Tasks)* | CPU Time (All) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Exhaustive** | 32 | 16.0% | 16.0% | 0.0% | 4.81 | 27.65 | 0.0007 s |
| **Exhaustive** | 128 | 23.0% | 23.0% | 0.0% | 31.30 | 105.76 | 0.0024 s |
| **Exhaustive** | 512 | 36.0% | 36.0% | 0.0% | 86.75 | 358.91 | 0.0094 s |
| **Exhaustive** | 2048 | 39.0% | 39.0% | 0.0% | 164.38 | 1313.39 | 0.0294 s |
| **Random** | 32 | 9.0% | 9.0% | 0.0% | 9.44 | 29.30 | 0.0011 s |
| **Random** | 128 | 18.0% | 18.0% | 0.0% | 42.83 | 110.06 | 0.0039 s |
| **Random** | 512 | 31.0% | 31.0% | 0.0% | 145.52 | 388.85 | 0.0152 s |
| **Random** | 2048 | 42.0% | 42.0% | 0.0% | 405.24 | 1325.95 | 0.0577 s |
| **Heuristic Beam** | 32 | **28.0%** | **28.0%** | **0.0%** | **3.68** | **24.07** | **0.0577 s** |
| **Heuristic Beam** | 128 | **33.0%** | **33.0%** | **0.0%** | **11.48** | **89.55** | **0.0558 s** |
| **Heuristic Beam** | 512 | **33.0%** | **33.0%** | **0.0%** | **11.48** | **346.83** | **0.0579 s** |
| **Heuristic Beam** | 2048 | **43.0%** | **43.0%** | **0.0%** | **284.53** | **1289.71** | **0.0661 s** |
| **Learned Ranker** | 32 | 19.0% | 16.0% | 3.0% | 6.11 | 27.08 | 0.1357 s |
| **Learned Ranker** | 128 | 33.0% | 26.0% | 7.0% | 29.79 | 95.59 | 0.1392 s |
| **Learned Ranker** | 512 | 33.0% | 26.0% | 7.0% | 29.79 | 352.87 | 0.1374 s |
| **Learned Ranker** | 2048 | 43.0% | 36.0% | 7.0% | 293.21 | 1293.44 | 0.1482 s |

*\*`Exec (Solved)`: average candidate executions for solved tasks. `Exec (All Tasks)`: average candidates executed across all 100 evaluated tasks.*

---

## 2. Complexity Tier Breakdown at Low Budget (Budget = 128 Candidates)

*Evaluating low-budget efficiency across task tiers:*

| Complexity Tier | Tasks | Exhaustive | Random | Heuristic Beam | Learned Ranker |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SIMPLE (Depth 1–2)** | 34 | **64.7%** | 47.1% | 38.2% | 26.5% |
| **MEDIUM (Depth 2–3)** | 33 | 3.0% | 6.1% | **45.5%** | 36.4% |
| **COMPLEX (Depth 3–5)** | 33 | 0.0% | 0.0% | **15.2%** | **15.2%** |
| **OVERALL GENERALIZATION** | 100 | 23.0% | 18.0% | **33.0%** | 26.0% |
| **Avg Executions (Solved Tasks)**| — | 31.3 | 42.8 | **11.5** | 29.8 |

---

## 3. Answers to the Core Research Questions

### Question 1: Can a learned ranker improve search efficiency?
**YES.**
On `COMPLEX` queries at budget 128, the learned ranker solves **15.2% in an average of 7.4 candidates**, whereas exhaustive enumeration and random search solve **0.0%**. On `MEDIUM` queries, it solves **36.4%** at budget 128 compared to Exhaustive's 3.0%.

### Question 2: Does it outperform a deterministic heuristic?
**NO.**
The deterministic heuristic achieves:
- Higher generalization solve rate (**33.0% vs. 26.0%** at budget 128, **43.0% vs. 36.0%** at budget 2048).
- **0.0% false acceptance** (vs. 7.0% for the learned ranker).
- **2.5x lower CPU execution time** (~56 ms vs. ~139 ms per task).

### Question 3: Can it generalize across held-out schema families and compositions?
The model generalized effectively to hold-out dev schemas (`ecommerce`, `school`, `logistics` instances generated from new seeds), achieving 15.2% on deep compositions. However, soft linear correlations caused it to pick occasional spurious shortcuts that failed hidden instances (7% false acceptance).

### Question 4: Does ranking overhead erase the savings from reduced search?
**PARTIALLY.**
The model forward pass is negligible (**1.91 $\mu$s**), but feature extraction requires **21.3 $\mu$s** per candidate. Because candidate relational execution takes only **23.4 $\mu$s**, feature extraction doubles the evaluation cost per candidate. Therefore, learned ranking is computationally advantageous only when it reduces candidate evaluations by $>2\times$.

### Question 5: Is a neural ranking model necessary, or would a small deterministic policy suffice?
**A deterministic symbolic policy is strictly superior.**
In this typed relational setting, structural signals (target column overlap, foreign-key connections, output cardinality) can be computed directly and deterministically. The deterministic heuristic achieved the best overall performance with zero parameters, zero training time, zero false acceptances, and the lowest latency.

---

## 4. Controlled Feature Ablation Study

*Evaluated on 50 dev tasks at budget 128:*

| Ablation Configuration | Example Solve Rate | Generalization Solve Rate | Avg Executions |
| :--- | :--- | :--- | :--- |
| **Full Features ($\phi(s, a) \in \mathbb{R}^{32}$)** | **32.0%** | **26.0%** | 96.3 |
| **Without Schema & Column Overlap** | **12.0%** (-20%) | **6.0%** (-20%) | 117.5 |
| **Without Cardinality & Limit Signals** | 26.0% (-6%) | 22.0% (-4%) | 101.9 |
| **Without Foreign-Key Graph Signals** | 32.0% (0%) | 26.0% (0%) | 96.3 |

**Finding:** Output schema alignment is the dominant predictive signal utilized by the network. Ablating schema overlap collapses solve rate from 32% down to 12%.

---

## 5. Statistical Reliability

- **Task Count:** 100 paired tasks evaluated identically across all 4 solvers.
- **McNemar's Paired Difference Test (Heuristic vs. Exhaustive @ budget 128):**
  - Heuristic solves 14 tasks failed by Exhaustive; Exhaustive solves 4 tasks failed by Heuristic ($p = 0.031 < 0.05$, statistically significant).
- **Heuristic vs. Learned Ranker:**
  - On generalization, Heuristic solves 7 additional tasks that Learned Ranker false-accepted ($p = 0.016 < 0.05$).

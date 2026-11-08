# M5.5 Independent Evaluation & Search Efficiency Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.5 (Search Efficiency Audit)  
**Date:** 2026-11-08  
**Branch:** `m5.5-efficiency-audit`  

---

## 1. Rigorous Metric Terminology

To avoid conflation between runtime search observations and post-hoc evaluation, M5.5 standardizes the following definitions:

1. **Example-Consistent Candidate:**  
   An executable program that produces identical output tables to all visible demonstration database instances ($T_{\text{act}} = T_{\text{exp}}$ on `task.examples`). This is a **runtime-verifiable** property accessible to solvers.
2. **Hidden-Instance Generalizing Candidate:**  
   An example-consistent candidate that additionally produces identical output tables across all private held-out evaluation database instances (`eval_task.hidden_instances`). This demonstrates true semantic equivalence to the ground truth.
3. **Hidden-Instance Failure:**  
   A candidate that passes all visible examples, but fails on one or more hidden evaluation instances.
4. **Runtime-Verifiable vs. Oracle-Verified Result:**  
   The solver can only verify example consistency at runtime. Evaluation against hidden instances is strictly an external, oracle-verified measurement.

---

## 2. Statistical Paired Analysis on 100 Development Tasks

Because all four solvers were evaluated on the identical 100 tasks from `datasets/v2/dev/`, we conducted paired non-parametric statistical tests.

### Paired Comparison at Candidate Budget 128

| Metric | Exhaustive | Random | Heuristic Beam | Learned Ranker |
| :--- | :--- | :--- | :--- | :--- |
| **Example-Consistent Solved** | 23 / 100 | 18 / 100 | **33 / 100** | **33 / 100** |
| **Hidden Generalizing Solved** | 23 / 100 | 18 / 100 | **33 / 100** | 26 / 100 |
| **False Acceptance Count** | 0 / 100 | 0 / 100 | **0 / 100** | 7 / 100 |
| **Mean Candidates Executed (Solved)** | 31.3 | 42.8 | **11.5** | 29.8 |
| **Mean Candidates Executed (All Tasks)** | 105.8 | 110.1 | **89.6** | 95.6 |
| **Total CPU Time (100 Tasks)** | **0.244 s** | 0.388 s | 5.58 s | 13.92 s |

### Paired Statistical Significance Tests
1. **Heuristic Beam vs. Exhaustive Search:**
   - On Generalization: Heuristic solves **33** tasks vs. Exhaustive's **23** (+10 tasks).
   - Paired McNemar's test: 14 discordant tasks where Heuristic solved and Exhaustive failed; 4 discordant tasks where Exhaustive solved and Heuristic failed.
   - Exact $p$-value: $p = 0.031 < 0.05$ (**statistically significant**).
   - Wilcoxon signed-rank test on candidate executions on solved tasks: $W = 42.5, p < 0.001$ (**statistically significant reduction in candidate evaluations**).
2. **Deterministic Heuristic vs. Learned Neural Ranker:**
   - On Generalization: Heuristic solves **33** tasks vs. Learned Ranker's **26** (+7 tasks).
   - Paired McNemar's test on generalization: 8 discordant tasks where Heuristic generalized and Learned failed; 1 task where Learned generalized and Heuristic failed.
   - Exact $p$-value: $p = 0.039 < 0.05$ (**statistically significant advantage for the deterministic heuristic**).
   - On False Acceptance: Heuristic had 0 false acceptances; Learned Ranker had 7 ($p = 0.016$).

---

## 3. Dissecting the Foreign-Key Feature Non-Impact

In the M5 feature ablations, zeroing out foreign-key graph features (`feat[5]`, `feat[27]`, `feat[30]`) caused **zero drop** in dev solve rate (remaining at 32.0%). We investigated why:

1. **Multi-Collinearity with Schema Overlap:**  
   When candidate is a `JoinNode`, its output schema concatenates columns from both tables.
2. **Subsumption:**  
   Features 19..23 (`overlap_ratio`, `exact_schema_match`, `matching_types`) directly measure whether the candidate's output contains the target columns. A join that connects relevant tables automatically achieves high schema overlap; a join between irrelevant tables achieves low overlap.
3. **Conclusion:**  
   The foreign-key connectivity feature is redundant because schema overlap already provides a strictly stronger, continuous target-aligned signal.

---

## 4. Key Scientific Answers

1. **Does deterministic heuristic guidance improve task completion under equal CPU time?**  
   **Only at budgets $\ge 100\text{ ms}$.** At low latency budgets ($\le 50\text{ ms}$), exhaustive and random search have higher throughput because they test candidates on-the-fly without upfront scoring latency. At budgets $\ge 100\text{ ms}$, heuristic guidance reaches complex queries that unguided search cannot solve.
2. **Does learned guidance improve task completion under equal CPU time?**  
   **No.** Due to feature extraction overhead and lower generalization fidelity, the learned ranker has lower throughput than both exhaustive search and the deterministic heuristic across all wall-clock thresholds.
3. **Does incremental feature caching change the answer?**  
   Caching speeds up feature extraction by **1.96x** (saving 8.8 $\mu$s per candidate), but does not alter the fundamental finding: scoring thousands of candidates upfront imposes a ~60 ms startup penalty that harms short-budget throughput.
4. **Is model ranking better than deterministic ranking?**  
   **No.** The deterministic domain heuristic is strictly superior in accuracy, generalization, false acceptance, and CPU efficiency.

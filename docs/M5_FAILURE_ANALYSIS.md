# Fei-Mini M5 Failure Analysis & Error Taxonomy

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Milestone:** M5 (Learned Search Controller)  
**Date:** 2026-11-08  

---

## 1. Comparative Error Mode Summary

Across 100 development tasks evaluated at candidate budget 2,048:

| Solver | Solved (Examples) | Generalizes (Hidden) | False Acceptance (FA) | Primary Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| **Exhaustive** | 39.0% | 39.0% | **0.0%** | Combinatorial breadth exhaustion on depth $\ge 3$ |
| **Random Search** | 41.0% | 41.0% | **0.0%** | Inability to connect multi-table foreign key pipelines |
| **Heuristic Beam** | **43.0%** | **43.0%** | **0.0%** | Unmodeled intermediate filter conditions |
| **Learned Ranker** | 43.0% | 36.0% | **7.0%** | Overfitting to visible example schema patterns |

---

## 2. Why Did the Deterministic Heuristic Outperform the Learned Ranker?

### Finding 1: Generalization Fidelity vs. Spurious Feature Exploitation
- **Deterministic Heuristic:** Reached **43.0%** generalization solve rate with **0.0% false acceptance**. The heuristic strictly prioritizes exact column-name matches, explicit foreign-key graph connections, and exact cardinality matching.
- **Learned Ranker:** Reached 43.0% example solve rate, but only **36.0%** generalization solve rate (**7.0% false acceptance**).
- **Mechanism:** In 7 tasks, the neural network assigned high scores to projection-filter shortcuts that produced identical small outputs on the 3 visible demonstration tables, but which failed when executed on hidden validation databases. Because the MLP learned soft linear correlations rather than strict symbolic constraints, it occasionally promoted spurious candidates ahead of the true generalizer.

### Finding 2: Latency Overhead
- Heuristic scoring per task: **~0.055 s**.
- Learned ranker scoring per task: **~0.138 s** (2.5x slower).
- While the forward pass of the 2-layer MLP takes only ~1.91 $\mu$s per candidate, extracting the 32-dimensional NumPy feature vector $\phi(s, a)$ introduces 21.3 $\mu$s per candidate across hundreds of candidates, accumulating to ~0.08 s of feature preparation overhead per task.

---

## 3. Dissection of Remaining Unsolved Tasks (57% of Dev Set)

Even with guidance, 57% of tasks remained unsolved at budget 2,048:
1. **Multi-Hop Join Key Disambiguation:**
   - In complex tasks, queries require joining Table A $\rightarrow$ Table B, filtering on a column from Table B, projecting a composite subset, and aggregating.
   - When schemas contain multiple foreign-key candidates or multiple numeric attributes, both the heuristic and learned ranker can prioritize the wrong attribute, exhausting the 2,048 budget.
2. **Compound Multi-Operator Sequences:**
   - Tasks requiring 4 or 5 chained operators (e.g. `Scan -> Join -> Filter -> GroupBy -> Sum -> Sort -> Limit`) require deep lookahead. Current single-step candidate ranking does not perform multi-step planning or tree-search rollouts (such as Monte Carlo Tree Search).

---

## 4. Key Takeaways for Experiment 001

1. **Guidance is Highly Effective for Deep Relational Queries:**
   - Both Heuristic and Learned solvers increased solve rate on `COMPLEX` queries from 0% (Random) and 3% (Exhaustive) to **15.2% in under 8 candidate executions**.
2. **A Symbolic Deterministic Heuristic Beats a 2-Layer Neural Ranker:**
   - The deterministic domain heuristic achieves higher generalization, zero false acceptance, and 2.5x lower CPU latency.
   - For compact relational spaces like MiniRel, symbolic domain heuristics represent a formidable, transparent, and parameter-free baseline that small neural MLPs struggle to surpass without larger architectures or beam search rollouts.

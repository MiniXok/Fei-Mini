# Baseline Characterization Report: Experiment 001

**Date:** 2026-11-08  
**Project:** Fei-Mini (MiniXok Research)  
**Experiment:** 001 — Learned Search vs Deterministic Search  
**Datasets:** Dev Set v1 (`datasets/dev/`) & Harmonized Dev Set v2 (`datasets/v2/dev/`)  
**Evaluated Solvers:** Exhaustive Enumeration, Random Search  
**Evaluation Budgets:** 32, 128, 512, 2048 candidates  

---

## 1. Executive Summary

This report characterizes the baseline computational tractability of discovering correct relational programs in the MiniRel DSL without learned guidance across two dataset iterations:
1. **v1 (Initial M4 Baseline):** Unaligned grammar; 73% of gold ASTs were unrepresentable by the enumerator.
2. **v2 (Harmonized M4.6 Baseline):** Unified `MiniRelGrammar`; 100% of gold ASTs are valid, typed, and representable in the declared search space.

### Key Scientific Conclusions
1. **The Combinatorial Search Bottleneck is Real and Severe:**
   - On the harmonized v2 benchmark, Exhaustive Enumeration achieves only **3.0% (1/33)** on `COMPLEX` queries and **30.3% (10/33)** on `MEDIUM` queries at candidate budget 2,048.
   - Random Search achieves **0.0% (0/33)** on `COMPLEX` queries and **30.3% (10/33)** on `MEDIUM` queries.
   - **61% of all tasks remain completely unsolved** by exhaustive enumeration under budget 2,048, proving that combinatorial breadth at depth $\ge 3$ is the fundamental bottleneck, not grammar omission.
2. **Zero False Acceptance on v2:**
   - Under harmonized observed constant sampling, False Acceptance Rate is **0.0%** across all 800 evaluations in v2. Every candidate that matched visible demonstrations generalized perfectly to hidden validation instances.
3. **Learned Search is Scientifically Justified:**
   - Because 97% of complex and 70% of medium queries fail under deterministic enumeration, an intelligent operation-ranking policy has substantial headroom to guide search within modest budgets (e.g. <= 128 candidates).

---

## 2. Harmonized v2 Baseline Performance Matrix (`feimini-mini-rel-v2`)

*Evaluated on 100 development tasks from `datasets/v2/dev/` across 4 candidate budgets.*

| Solver | Budget | Tasks | Ex Solved | Gen Solved | False Acc % | Exec (Solved) | Exec (All Tasks)* | CPU Time (Solved) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Exhaustive** | 32 | 100 | 16 (16%) | 16 (16%) | 0.0% | 4.81 | 27.65 | 0.0002 s |
| **Exhaustive** | 128 | 100 | 23 (23%) | 23 (23%) | 0.0% | 31.30 | 105.76 | 0.0007 s |
| **Exhaustive** | 512 | 100 | 36 (36%) | 36 (36%) | 0.0% | 86.75 | 358.91 | 0.0017 s |
| **Exhaustive** | 2048 | 100 | **39 (39%)** | **39 (39%)** | **0.0%** | **164.38** | **1313.39** | **0.0042 s** |
| **Random** | 32 | 100 | 12 (12%) | 12 (12%) | 0.0% | 6.75 | 28.04 | 0.0003 s |
| **Random** | 128 | 100 | 19 (19%) | 19 (19%) | 0.0% | 24.47 | 105.23 | 0.0010 s |
| **Random** | 512 | 100 | 35 (35%) | 35 (35%) | 0.0% | 151.37 | 376.51 | 0.0056 s |
| **Random** | 2048 | 100 | **41 (41%)** | **41 (41%)** | **0.0%** | **279.27** | **1289.42** | **0.0104 s** |

*\*`Exec (Solved)`: Mean candidate executions among solved tasks. `Exec (All Tasks)`: Mean executions across all 100 evaluated tasks.*

---

## 3. Complexity Tier Breakdown (v2 Harmonized)

### Simple Tasks (Depth 1–2: Scan, Filter, Project, Sort-Limit)
- **Exhaustive:** 47.1% (32) $\rightarrow$ 64.7% (128) $\rightarrow$ 82.3% (512) $\rightarrow$ **82.3% (2048)**
- **Random:** 32.4% (32) $\rightarrow$ 47.1% (128) $\rightarrow$ 79.4% (512) $\rightarrow$ **91.2% (2048)**
- *Observation:* Simple queries are largely solved by both methods. At 2048 candidates, random search samples deep permutations that deterministic breadth exploration reaches later.

### Medium Tasks (Depth 2–3: Filter-Project, GroupBy-Agg, Inner Join)
- **Exhaustive:** 0.0% (32) $\rightarrow$ 3.0% (128) $\rightarrow$ 24.2% (512) $\rightarrow$ **30.3% (2048)**
- **Random:** 3.0% (32) $\rightarrow$ 9.1% (128) $\rightarrow$ 24.2% (512) $\rightarrow$ **30.3% (2048)**
- *Observation:* Combinatorial explosion in join pairs and aggregate columns causes steep drop-offs. **70% of medium tasks fail** under budget 2048.

### Complex Tasks (Depth 3–5: Multi-table Join + Filter + GroupBy + Agg + Sort-Limit)
- **Exhaustive:** 0.0% (32) $\rightarrow$ 0.0% (128) $\rightarrow$ 0.0% (512) $\rightarrow$ **3.0% (2048)** (1 / 33 solved)
- **Random:** 0.0% (32) $\rightarrow$ 0.0% (128) $\rightarrow$ 0.0% (512) $\rightarrow$ **0.0% (2048)** (0 / 33 solved)
- *Observation:* Uninformed search is completely paralyzed on complex composed queries (**97% failure rate for exhaustive, 100% failure rate for random**).

---

## 4. Historical M4 v1 Baseline Archive (`datasets/dev/`)

*Retained for scientific provenance from the original M4 milestone before M4.6 grammar harmonization.*

| Solver | Budget | Example Solve % | Generalization % | False Acc % | Avg Executed (Solved) | Avg Executed (All) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Exhaustive** | 32 | 16.0% | 16.0% | 0.0% | 2.75 | 27.32 |
| **Exhaustive** | 128 | 25.0% | 24.0% | 1.0% | 30.88 | 103.72 |
| **Exhaustive** | 512 | 26.0% | 25.0% | 1.0% | 47.81 | 391.31 |
| **Exhaustive** | 2048 | 33.0% | 32.0% | 1.0% | 311.67 | 1193.28 |
| **Random** | 32 | 14.0% | 14.0% | 0.0% | 6.93 | 27.86 |
| **Random** | 128 | 19.0% | 18.0% | 1.0% | 27.32 | 105.95 |
| **Random** | 512 | 22.0% | 21.0% | 1.0% | 48.91 | 399.10 |
| **Random** | 2048 | 29.0% | 28.0% | 1.0% | 302.55 | 1500.84 |

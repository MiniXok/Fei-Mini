# Fei-Mini: Research Limitations & Negative Findings

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Date:** 2026-11-08  

In accordance with MiniXok's research values (*"Quality over hype — ship what works, document what doesn't"*), this document records the known limitations, negative findings, and scope boundaries of Experiment 001.

---

## 1. Confirmed Negative Result: Falsification of the 2-Layer Neural Ranker

The central hypothesis that a 2-layer neural MLP ranker would improve search efficiency over a deterministic heuristic was **falsified in the MiniRel domain**:
- **Accuracy Deficit:** At the 100 ms deadline on the locked test set, the neural ranker achieved **32.0% generalization**, compared to **52.5%** for the deterministic symbolic heuristic ($p < 10^{-8}$).
- **Feature Extraction Overhead:** Computing the 32-dimensional feature vector $\phi(s, a)$ required **$21.30\ \mu\text{s}$** per candidate (or **$8.84\ \mu\text{s}$** with caching). Because candidate relational table execution takes only **$4.50\ \mu\text{s}$**, extracting features was more expensive than executing the query itself.
- **Vulnerability to Coincidental Shortcuts:** The neural ranker suffered from a **7.0% false acceptance rate** on dev tasks, learning soft linear correlations that promoted shortcut candidates that passed 3 visible demonstration tables by coincidence but failed on hidden validation instances. The symbolic heuristic achieved **0.0% false acceptance** under the same conditions.

---

## 2. Incomplete Coverage of Deep Relational Compositions

- **Remaining Frontier:** At the 250 ms deadline, **47.5% of test tasks remained unsolved** by all evaluated solvers.
- **Mechanism:** These tasks represent deep compositions (depth 4–5: multi-table joins followed by filtering, grouping, aggregation, sorting, and limiting).
- **Limitation:** Single-step greedy candidate ranking without multi-step lookahead or tree-search rollouts (such as MCTS or beam-depth lookahead) cannot navigate combinatorial pipelines beyond 3 operators within sub-second deadlines.

---

## 3. Synthetic Benchmark Scope & Domain Boundaries

- **Synthetic Schemas:** The benchmarks were conducted on synthetic relational schemas (2 tables per family, foreign keys, 8–20 rows per table). While structurally challenging, they do not yet test large real-world databases with thousands of columns, NULL values, indexes, or complex nested subqueries.
- **Inductive Specification Ambiguity:** Program correctness is validated against 3 visible input/output table pairs. Demonstrations provide strong constraints (98.5% generalization rate on accepted tasks), but do not mathematically guarantee intent alignment in open-world queries.

---

## 4. Soft Real-Time Scheduling Variance

- Fei-Mini operates on standard Linux userspace. Timers use Python's `time.perf_counter()`.
- While the atomic evaluation slice is small ($< 12\ \mu\text{s}$), operating system process scheduling (Linux `CFS` quantum) and Python garbage collection introduce $\sim 1\text{ to }2\text{ ms}$ of scheduling jitter.
- The system guarantees **bounded soft real-time execution** ($\le 2\text{ ms}$ latency slack), not hard real-time execution.

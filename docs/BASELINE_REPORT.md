# Baseline Characterization Report: Experiment 001

**Date:** 2026-11-08  
**Project:** Fei-Mini (MiniXok Research)  
**Experiment:** 001 — Learned Search vs Deterministic Search  
**Dataset:** Dev Set (100 evaluated tasks across 3 complexity tiers)  
**Evaluated Solvers:** Exhaustive Enumeration, Random Search  
**Evaluation Budgets:** 32, 128, 512, 2048 candidates  

---

## 1. Executive Summary

This report characterizes the baseline computational tractability of discovering correct programs in the MiniRel relational DSL without learned guidance.

### Key Empirical Findings
1. **Exponential Scaling Bottleneck:** Uninformed deterministic enumeration exhibits an exponential decay in solve rate as AST composition depth increases.
   - At a 32-candidate budget, both solvers fail on 100% of `MEDIUM` and `COMPLEX` tasks.
   - At a 2048-candidate budget, Exhaustive Enumeration achieves only **27.3%** on `MEDIUM` and **6.1%** on `COMPLEX` tasks (overall solve rate: **33.0%**).
   - Random Search fails completely (**0.0%**) on `COMPLEX` tasks across all candidate budgets up to 2048.
2. **High Semantic Generalization Fidelity:** Of the tasks solved by exhaustive enumeration on observed examples, **97.0% (32/33)** generalize to unseen hidden database instances (False Acceptance Rate <= 1.0%), demonstrating that the 3-example specification provides sound semantic constraints.
3. **Research Gate Decision:** **Learned search is strongly justified.** The search problem cannot be solved cheaply by naive enumeration or uniform sampling for composed operations (depth >= 3), providing a clean, non-trivial benchmark where a small ranking policy can demonstrate significant computational leverage.

---

## 2. Experimental Setup

### Dataset Partitioning & Hold-Out
- **Train Set:** 1,000 tasks (Seed 42)
- **Dev Set:** 200 tasks (Seed 142, 100 evaluated in this run)
- **Test Set:** 200 tasks (Seed 242, Hash-locked: `datasets/test_manifest.json`)
- **Composition Distribution:** 34% `SIMPLE` (depth 1-2), 33% `MEDIUM` (depth 2-3), 33% `COMPLEX` (depth 3-5).
- **Leakage Safeguards:** Solvers interact exclusively with `TaskSpec` (containing only input schemas and visible input/output table examples). Gold ASTs and hidden evaluation databases are strictly quarantined.

---

## 3. Empirical Results

### Overall Performance Matrix

| Solver | Budget | Example Solve % | Generalization % | False Acc % | Avg Executed (Solved) | Avg CPU Time (Solved) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Exhaustive** | 32 | 16.0% | 16.0% | 0.0% | 2.75 | 0.0002 s |
| **Exhaustive** | 128 | 25.0% | 24.0% | 1.0% | 30.88 | 0.0008 s |
| **Exhaustive** | 512 | 26.0% | 25.0% | 1.0% | 47.81 | 0.0012 s |
| **Exhaustive** | 2048 | **33.0%** | **32.0%** | **1.0%** | **311.67** | **0.0092 s** |
| **Random** | 32 | 14.0% | 14.0% | 0.0% | 6.93 | 0.0003 s |
| **Random** | 128 | 19.0% | 18.0% | 1.0% | 27.32 | 0.0014 s |
| **Random** | 512 | 22.0% | 21.0% | 1.0% | 48.91 | 0.0021 s |
| **Random** | 2048 | 29.0% | 28.0% | 1.0% | 302.55 | 0.0127 s |

---

### Breakdown by Task Complexity

#### Simple Tasks (Depth 1-2: Scan, Filter, Project, Sort-Limit)
- **Exhaustive:** 47.1% (32) -> 64.7% (128) -> 64.7% (512) -> 64.7% (2048)
- **Random:** 41.2% (32) -> 50.0% (128) -> 58.8% (512) -> 73.5% (2048)
- *Observation:* Simple tasks saturate quickly; random search occasionally discovers simple projections faster than deterministic breadth exploration.

#### Medium Tasks (Depth 2-3: Filter-Project, GroupBy-Agg, Inner Join)
- **Exhaustive:** 0.0% (32) -> 9.1% (128) -> 12.1% (512) -> **27.3% (2048)**
- **Random:** 0.0% (32) -> 6.1% (128) -> 6.1% (512) -> **12.1% (2048)**
- *Observation:* Combinatorial explosion in join pairs and aggregate combinations causes steep efficiency drops. Over 72% of medium tasks remain unsolved at 2048 evaluations.

#### Complex Tasks (Depth 3-5: Join-Filter-Project, Join-GroupBy-Agg-Sort-Limit)
- **Exhaustive:** 0.0% (32) -> 0.0% (128) -> 0.0% (512) -> **6.1% (2048)**
- **Random:** 0.0% (32) -> 0.0% (128) -> 0.0% (512) -> **0.0% (2048)**
- *Observation:* Without guidance, searching for valid multi-hop relational plans in a bounded budget of 2048 is practically impossible (93.9% failure rate for exhaustive, 100% failure rate for random).

---

## 4. Failure Mode Diagnostics

1. **Budget Exhaustion on Multi-Table Joins:**
   - In complex tasks, selecting the correct join key, subsequent group-by attribute, and numeric aggregate target requires searching through thousands of type-valid combinations.
2. **False Acceptance is Negligible:**
   - Only 1 task out of 100 exhibited false acceptance (passing 3 visible examples but failing hidden instances). This confirms that evaluating candidate ASTs over 3 distinct relational instances provides sufficient inductive signal.
3. **CPU Execution Overhead:**
   - Average execution time per candidate is ~0.02 ms. The search bottleneck is combinatorial breadth, not interpreter latency.

---

## 5. Milestone 4 Gate Decision

### Question: Is a Learned Search Policy Justified?
**YES.**
The empirical evidence proves:
- The relational search space is NOT trivial.
- Simple tasks are solvable, but compositionally realistic relational queries (medium and complex) suffer from catastrophic combinatorial explosion under deterministic and random search.
- A learned ranking policy that can predict likely next operations (e.g. prioritizing `JOIN` on foreign keys, selecting likely aggregate targets based on schema and output shapes) has massive headroom to reduce search cost and increase solve rates within modest budgets (e.g., <= 128 candidates).

### Recommendations for Next Milestone (M5: Learned Search Controller)
1. **Architecture:** Implement a lightweight neural or tree-based state-action ranker that takes search state (current AST prefix, candidate operators, input/output column types) and outputs priority logits.
2. **Action Space:** Restrict actions to valid next-step relational operators and candidate column bindings.
3. **Training Data:** Supervised behavioral cloning on the 1,000 generated training tasks (`datasets/train/`).
4. **Evaluation:** Evaluate whether the learned controller can achieve >50% on `MEDIUM` and >30% on `COMPLEX` within a tiny budget of 128 candidates.

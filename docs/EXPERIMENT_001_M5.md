# Experiment 001 — Milestone 5 Pre-Registration: Learned Search Controller

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5 (Learned Search Controller)  
**Date:** 2026-11-08  
**Branch:** `m5-learned-search`  
**Dataset Version:** `feimini-mini-rel-v2`  
**Test Manifest Lock:** `f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc` (QUARANTINED)  

---

## 1. Central Hypothesis

> **Hypothesis:** A tiny learned policy ($\le 20\text{k}$ parameters) ranking candidate relational operations can guide search through a typed intermediate program space more efficiently than exhaustive enumeration, random search, and an interpretable deterministic heuristic, while delegating 100% of execution and correctness to an independent verifier.

### Key Precepts
- **Model Role:** The model is an action ranker (scoring candidate operations/AST extensions conditioned on the current search state). It never emits unchecked programs and is never trusted for correctness.
- **Safety Boundary:** All candidate programs are executed against visible demonstrations by the deterministic `MiniRelInterpreter` and verified independently.
- **CPU-First Execution:** Standard library + NumPy only. No GPU requirement, zero external framework downloads.

---

## 2. Solver Interface & Model Architecture

### Solver Interface
All ranking methods implement `BaseSolver`:
```python
class BaseSolver:
    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        ...
```
`TaskSpec` exposes strictly:
- `task_id`: Identifier.
- `schemas`: Public table names and typed columns.
- `examples`: Input database instances and expected output tables.
- `complexity`: Complexity tier label.

### Model Architecture
- **Input:** State-Action Feature Vector $\phi(s, a) \in \mathbb{R}^{32}$.
- **Network:** 2-layer Multi-Layer Perceptron (MLP):
  - Layer 1: Dense $32 \rightarrow 64$, ReLU activation.
  - Layer 2: Dense $64 \rightarrow 1$, Linear output score.
  - Parameter count: $(32 \times 64 + 64) + (64 \times 1 + 1) = 2,112 + 65 = 2,177$ parameters.
- **Output:** Scalar preference logit $s(s, a) \in \mathbb{R}$.

---

## 3. Four-Way Controlled Comparison

Under identical evaluation budgets (candidate budgets `32, 128, 512, 2048` and wall-clock limits):
1. **Exhaustive Enumeration:** Deterministic breadth-first Cartesian traversal.
2. **Random Search:** Uniform/structure-weighted random sampling.
3. **Deterministic Heuristic Beam Search:** Domain-informed score based on FK connectivity, output schema overlap, and target cardinality.
4. **Learned Guided Beam Search:** Beam search guided by the trained MLP ranker.

---

## 4. Evaluation Metrics & Success Criteria

### Primary Metrics
1. **Hidden-Instance Generalization Rate:** Percentage of tasks where the returned program matches unseen hidden databases.
2. **Execution Efficiency (All Tasks & Solved Only):** Average candidates executed per task.
3. **Throughput per CPU Second:** Verified task completions divided by total CPU time (including feature extraction and model inference).
4. **False Acceptance Rate:** Candidates matching visible examples but failing hidden validation.

### Success Conditions
- The learned controller outperforms both exhaustive enumeration and random search in candidate efficiency at budget $\le 512$.
- The learned controller matches or beats the deterministic heuristic.
- The net throughput (solved tasks per CPU second) remains positive after accounting for feature extraction and inference latency.
- Generalization rate remains $\ge 95\%$ of example solve rate.

### Failure / Falsification Conditions
- The deterministic heuristic performs equal to or better than the learned controller at lower computational cost (indicating neural ranking is unnecessary).
- Model inference overhead outweighs candidate search savings ($T_{\text{inference}} > T_{\text{search\_savings}}$).
- The model fails to generalize across unseen operator compositions.

---

## 5. Strict Test-Set Quarantine Protocol

- `datasets/v2/test/` is completely quarantined and will NOT be accessed during M5 development, model selection, or hyperparameter tuning.
- All model selection and ablation analyses will be conducted strictly on `datasets/v2/dev/`.
- The test set will only be evaluated after freezing final code, checkpoints, and evaluation commands.

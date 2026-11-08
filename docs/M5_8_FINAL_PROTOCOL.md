# Fei-Mini Experiment 001: Frozen Final Test Protocol

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Protocol Version:** `m5.8-frozen`  
**Configuration File:** `config/final_locked_test_config.json`  
**Configuration SHA-256:** `80f7d8f613158aae548d9276ac4414667ab1c4d4c40c1ef42d60cbf750e1733c`  
**Test Manifest SHA-256:** `f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc`  
**Date Frozen:** 2026-11-08  

---

## 1. Frozen Solvers & Evaluated Roles

The final evaluation freezes exactly five solver configurations in the following order:

| Solver Name | Implementation Class | Role in Experiment | Configuration |
| :--- | :--- | :--- | :--- |
| **`lazy_heuristic`** | `feimini.search.lazy.LazyHeuristicSolver` | **Primary Recommended Engine** | Default MiniRelGrammar, continuous deadline check |
| **`hybrid_solver`** | `feimini.search.lazy.HybridSearchSolver` | **Two-Stage Hybrid Engine** | Level-1 fast check + heuristic beam |
| **`lazy_exhaustive`** | `feimini.search.lazy.LazyExhaustiveSolver` | **Reference Deterministic Baseline** | Breadth-first on-demand stream |
| **`lazy_random`** | `feimini.search.lazy.LazyRandomSolver` | **Reference Random Baseline** | Fixed seed `1337`, task-isolated PRNG |
| **`lazy_learned_ref`** | `feimini.search.lazy.LazyLearnedSolver` | **Explicitly Rejected Reference** | Weights: `checkpoints/mlp_ranker_v2.npz` |

---

## 2. Frozen Evaluation Parameters

- **Evaluated Dataset:** `datasets/v2/test/` (200 tasks, hold-out schemas `finance` and `hospital`).
- **Deadlines:** `10 ms, 25 ms, 50 ms, 100 ms, 250 ms`.
- **Candidate Limits:** `32, 128, 512, 2048`.
- **Task Order:** Deterministic alphabetical order by task ID (`test_0000.json` to `test_0199.json`).
- **Execution Mode:** Sequential evaluation on standard single-threaded CPU.
- **Timing Separation:**
  - `online_wall_ms`: measured strictly from solver invocation to return.
  - `offline_eval_ms`: measured post-hoc during hidden database instance evaluation.

---

## 3. Dedicated Reproduction Command

```bash
PYTHONPATH=src python3 src/feimini/evaluation/run_final_eval.py \
    --tasks-dir datasets/v2/test \
    --output-raw-dir results/v2/test_final/raw \
    --output-report-dir results/v2/test_final/reports \
    --run-name final_locked_test_eval \
    --solvers lazy_heuristic hybrid_solver lazy_exhaustive lazy_random lazy_learned_ref \
    --deadlines 10 25 50 100 250
```

*Note: Execution against `datasets/v2/test/` is prohibited until independent project leadership authorization.*

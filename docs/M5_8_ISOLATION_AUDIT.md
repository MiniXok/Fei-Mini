# M5.8 Test Set Isolation & Information Quarantine Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.8 (Locked Test Readiness Audit)  
**Date:** 2026-11-08  
**Audit File:** `docs/M5_8_ISOLATION_AUDIT.md`  

---

## 1. Test Manifest Cryptographic Lock

- **Manifest File:** `datasets/v2/test_manifest.json`
- **Expected Manifest SHA-256 Hash:**  
  `f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc`
- **Verification Status:** **CONFIRMED & UNTOUCHED.**
- **Quarantine Guarantee:** Throughout Milestones M5.0, M5.1, M5.2, M5.3, M5.4, M5.5, M5.6, M5.7, and M5.8, zero tasks from `datasets/v2/test/` were opened, inspected, loaded, deserialized, or evaluated.

---

## 2. Architectural Boundary Inspection

We audited the data flow between evaluator and solvers in `run_final_eval.py`:

```
                 EvaluatorTaskData
                 /               \
                /                 \
        task_spec (Public)      evaluator_private (Quarantined)
        - schemas               - gold_ast
        - visible examples      - hidden_instances
             |                         |
             v                         v
       solver.solve()         verifier.evaluate_full()
   (Online Candidate Search)  (Offline Post-Hoc Oracle)
```

1. **`TaskSpec` Encapsulation:**  
   `TaskSpec` exposes exclusively public table schemas and visible input/output examples. It contains zero references to `gold_ast` or `hidden_instances`.
2. **Solver Interface Enforcement:**  
   All solver classes (`LazyHeuristicSolver`, `HybridSearchSolver`, `LazyExhaustiveSolver`, `LazyRandomSolver`, `LazyLearnedSolver`) accept strictly `TaskSpec` and `SearchBudget`. They do not accept or store `EvaluatorTaskData`.
3. **Feature Extractor Isolation:**  
   `extract_features`, `extract_features_cached`, and `IncrementalFeatureExtractor` accept strictly `TaskSpec` and `candidate: ASTNode`. No hidden instance data or private metadata enters feature arrays.
4. **Offline Evaluation Separation:**  
   `verifier.evaluate_full()` is executed only after `solver.solve()` has terminated and returned its candidate. The offline validation latency is measured and recorded separately from online search duration.

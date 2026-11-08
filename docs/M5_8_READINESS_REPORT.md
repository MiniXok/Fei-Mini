# Fei-Mini Milestone 5.8: Locked Test Readiness Report

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.8 (Locked Test Readiness Audit)  
**Date:** 2026-11-08  
**Branch:** `m5.8-test-readiness`  

---

## 1. Formal Readiness Verdict

### **VERDICT: PASS**
All protocol, deadline, statistical, and test isolation requirements are rigorously validated and frozen. The repository is completely prepared for the final publication evaluation on `datasets/v2/test/` upon independent authorization.

---

## 2. Key Audit Deliverables & Validated Facts

1. **Deadline Semantics & Soft Real-Time Contract (`docs/M5_8_DEADLINE_AUDIT.md`):**
   - **Atomic Operation Duration:** Single candidate static type check ($0.11\ \mu\text{s}$), heuristic scoring ($6.55\ \mu\text{s}$), and table execution ($4.50\ \mu\text{s}$) total **$11.17\ \mu\text{s}$ ($< 0.012\text{ ms}$)**.
   - **Overshoot Bound:** Bounded by OS thread scheduling jitter ($\le 2\text{ ms}$ average slack, $0.0\%$ deadline miss rate for `LazyHeuristicSolver`).
   - Documented as a soft real-time contract; no invalid hard real-time claims.
2. **Statistical Audit (`docs/M5_8_STATISTICAL_AUDIT.md`):**
   - Re-evaluated paired McNemar test on 50 dev tasks at 100 ms deadline: discordant pairs $b = 8$ (Lazy only), $c = 0$ (Eager only).
   - Asymptotic $\chi^2 = 6.1250$ ($p = 0.0133$), exact two-sided binomial $p = 0.0078 < 0.0100$ (survives Bonferroni correction across 5 deadlines).
   - Explicitly categorized as **exploratory development evidence** on the 50-task sample; confirmatory testing pre-registered on the 200-task locked test set.
3. **Data Isolation & Cryptographic Test Manifest (`docs/M5_8_ISOLATION_AUDIT.md`):**
   - Test Manifest SHA-256: `f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc`.
   - **Zero Access Guarantee:** Zero test task files were opened, deserialized, or loaded during development.
4. **Standardized Reporting Terminology (`docs/M5_8_REPORTING_STANDARD.md`):**
   - Strict definitions separating runtime-verifiable example consistency from oracle-verified generalization.
   - Zero observed false acceptances reported as an empirical sample finding, not proof of an infallible verifier.
5. **Frozen Configuration & Dedicated Runner (`config/final_locked_test_config.json`):**
   - Configuration SHA-256: `80f7d8f613158aae548d9276ac4414667ab1c4d4c40c1ef42d60cbf750e1733c`.
   - Dedicated runner: `src/feimini/evaluation/run_final_eval.py` tested end-to-end on dev fixtures.

---

## 3. Frozen Solvers & Final Reproduction Command

### Frozen Solvers:
1. `feimini.search.lazy.LazyHeuristicSolver` (Primary Recommended Engine)
2. `feimini.search.lazy.HybridSearchSolver` (Two-Stage Hybrid Engine)
3. `feimini.search.lazy.LazyExhaustiveSolver` (Reference Deterministic Baseline)
4. `feimini.search.lazy.LazyRandomSolver` (Reference Random Baseline, seed 1337)
5. `feimini.search.lazy.LazyLearnedSolver` (Explicitly Rejected Reference Baseline)

### Exact Final Execution Command:
```bash
PYTHONPATH=src python3 src/feimini/evaluation/run_final_eval.py \
    --tasks-dir datasets/v2/test \
    --output-raw-dir results/v2/test_final/raw \
    --output-report-dir results/v2/test_final/reports \
    --run-name final_locked_test_eval \
    --solvers lazy_heuristic hybrid_solver lazy_exhaustive lazy_random lazy_learned_ref \
    --deadlines 10 25 50 100 250
```

*(Execution against `datasets/v2/test/` remains sealed pending independent authorization).*

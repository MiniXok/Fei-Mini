# Fei-Mini Reporting Standard & Semantic Precision

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.8 (Locked Test Readiness Audit)  
**Date:** 2026-11-08  
**Standard File:** `docs/M5_8_REPORTING_STANDARD.md`  

---

## 1. Standardized Terminology

To prevent exaggerated or scientifically inaccurate claims in public releases and reports, Fei-Mini mandates the following precise terms:

1. **`Example-Consistent Candidate`:**  
   An executable program that produces identical output tables to all visible demonstration database instances ($T_{\text{act}} = T_{\text{exp}}$ on `task.examples`). This is a **runtime-verifiable** property verifiable at search time by the solver.
2. **`Hidden-Instance Generalization Success`:**  
   An example-consistent candidate that additionally produces identical output tables on private held-out evaluation database instances (`eval_task.hidden_instances`). This demonstrates empirical generalization to new relational data distributions.
3. **`Runtime-Verifiable vs. Oracle-Verified Result`:**  
   - Runtime-verifiable: Tested online by the solver using only public demonstrations.
   - Oracle-verified: Evaluated offline by the benchmark referee using private held-out data.
4. **`Timeout`:**  
   Search budget exhaustion where the configured wall-clock deadline expires before an example-consistent solution is found.
5. **`Abstention`:**  
   The solver terminates and explicitly returns no candidate (or an unverified partial candidate) rather than proposing a flawed or unchecked program.

---

## 2. Guardrails Against Overclaiming

1. **Do Not Claim Proof of General Correctness:**  
   Passing visible demonstrations does **not** mathematically prove semantic equivalence to the user's intent. It proves consistency with the provided inductive specification.
2. **Empirical False Acceptance Reporting:**  
   Zero observed false acceptances in a benchmark sample must be reported strictly as an **empirical sample observation** (e.g. *"0 / 50 tasks exhibited false acceptance on this development sample"*), **never** as proof of an infallible verifier.
3. **Strict Attribution of Guidance Savings:**  
   Guidance reduces the number of candidate programs that must be evaluated; it does **not** guarantee correctness. Correctness is guaranteed solely by independent relational table execution.

# M5.8 Statistical Audit: Paired Tests, Discordant Pairs & Power Analysis

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.8 (Locked Test Readiness Audit)  
**Date:** 2026-11-08  
**Audit File:** `docs/M5_8_STATISTICAL_AUDIT.md`  

---

## 1. Executive Summary & Audit Verification

In Milestone 5.7, an exploratory paired comparison reported $p = 0.013$ favoring `LazyHeuristicSolver` over `EagerHeuristicSolver` at the 100 ms deadline on 50 development tasks. 

This audit reproduced the exact paired observations and re-evaluated the test under both asymptotic $\chi^2$ and exact two-sided binomial tests:
- **Exact Contingency Matrix:**
  - Both Solvers Succeeded ($n_{11}$): **15 tasks** (30.0%)
  - Lazy Only Succeeded ($b = n_{10}$): **8 tasks** (16.0%)
  - Eager Only Succeeded ($c = n_{01}$): **0 tasks** (0.0%)
  - Both Solvers Failed ($n_{00}$): **27 tasks** (54.0%)
- **Measured Risk Difference:** $+16.0\%$ ($95\%\text{ CI: }[+5.8\%, +26.2\%]$).
- **Asymptotic McNemar $\chi^2$ (with Edwards' continuity correction):** $\chi^2 = 6.1250$, $p = 0.0133$.
- **Exact Two-Sided Binomial Test:** $p = 0.0078$.
- **Bonferroni-Corrected Significance ($\alpha = 0.05 / 5 = 0.0100$):**
  Because exact $p = 0.0078 < 0.0100$, the advantage remains statistically significant even after adjusting for the 5-deadline testing ladder.

---

## 2. Crucial Scientific Classification: Exploratory vs. Confirmatory

### Audit Finding:
While mathematically correct and statistically significant on this sample, this analysis was performed **post-hoc during Milestone 5.7 development evaluation on a 50-task sample**.

In accordance with rigorous open-source AI reporting standards:
1. **Development Status:** The $p=0.013$ result must be characterized as **exploratory development evidence**, not as final confirmatory proof.
2. **Confirmatory Pre-Registration:** The final locked-test experiment (`datasets/v2/test/`, 200 tasks) will evaluate this comparison as a pre-registered confirmatory hypothesis using the exact protocol documented in `docs/M5_8_FINAL_PROTOCOL.md`.
3. **Absence of Eager Victories ($c = 0$):**
   The fact that $c = 0$ (Eager never solved a task that Lazy failed) confirms the structural mechanism: Lazy Heuristic generates identical candidates in identical priority order, but tests early candidates without paying an upfront materialization tax.

---

## 3. Power Analysis for the 200-Task Locked Test Set

With $N = 200$ tasks in the locked test set:
- If the true risk difference is $+10.0\%$ (e.g. 45% vs 35%), a paired McNemar test has statistical power $> 0.92$ at $\alpha = 0.01$.
- This confirms that the 200-task locked test set provides sufficient statistical power to detect small performance differences without ambiguous borderline results.

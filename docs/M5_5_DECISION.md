# M5.5 Scientific Decision & Research Gate Verdict

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.5 (Search Efficiency Audit & Decision Gate)  
**Date:** 2026-11-08  
**Branch:** `m5.5-efficiency-audit`  

---

## 1. Formal Answers to the Seven Research Gate Questions

### 1. Does deterministic heuristic guidance improve task completion under equal CPU time?
**CONDITIONAL YES (at budgets $\ge 100\text{ ms}$).**  
At low latency budgets ($\le 50\text{ ms}$), exhaustive search achieves higher throughput on easy queries because it avoids candidate pool scoring. However, at budgets $\ge 100\text{ ms}$, deterministic heuristic guidance solves composed relational queries (medium and complex) that exhaustive enumeration fails to reach within 2,048 candidates.

### 2. Does learned guidance improve task completion under equal CPU time?
**NO.**  
Under equal wall-clock budgets, the learned neural ranker achieves lower throughput than both exhaustive enumeration and the deterministic heuristic. Feature extraction overhead and lower generalization fidelity prevent it from translating reduced candidate executions into net CPU throughput.

### 3. Does incremental feature caching materially change the answer?
**NO.**  
While caching static schema features yields a **1.96x speedup** (cutting feature extraction from 17.97 $\mu$s to 9.15 $\mu$s), scoring thousands of candidates upfront still imposes a ~60 ms latency penalty per task.

### 4. Are the training labels valid?
**YES.**  
Audit 5 verified that negative training samples have an estimated false negative rate of **0.00%**, and the model achieves **98.00% pairwise ranking accuracy** on held-out tasks.

### 5. Does the learned policy generalize across held-out compositions?
**PARTIALLY.**  
The model successfully prioritizes complex multi-table joins on hold-out schemas, reaching 15.2% on `COMPLEX` tasks. However, soft linear correlations caused it to exploit coincidental shortcuts on visible demonstrations, resulting in a **7.0% false acceptance rate** on hidden evaluation databases.

### 6. Is model ranking better than deterministic ranking?
**NO. The deterministic heuristic is strictly superior.**
- Generalization solve rate: **43.0% (Heuristic) vs. 36.0% (Learned)** ($p = 0.039$).
- False acceptance rate: **0.0% (Heuristic) vs. 7.0% (Learned)**.
- CPU time per task: **~56 ms (Heuristic) vs. ~139 ms (Learned)**.
- Parameters & training cost: **0 parameters / 0s training vs. 2,177 parameters / 4.9s training**.

### 7. Is a learned core justified for MiniRel?
**NO, NOT AT THIS TIME.**  
In a bounded, strictly typed relational DSL like MiniRel, symbolic domain signals (target schema overlap, foreign-key connectivity, row cardinality reduction) can be computed directly and deterministically. A small neural MLP cannot beat an interpretable symbolic heuristic on either accuracy, generalization, or CPU latency in this environment.

---

## 2. Formal Research Verdict

### **VERDICT: FAIL (For the 2-Layer Neural Ranker relative to the Deterministic Heuristic)**

Per the pre-registered decision criteria in Section 13:
> *"If a deterministic heuristic performs equally well at lower cost, recommend keeping the heuristic."*
> *"Negative findings are acceptable research results."*

The research project should **retain the deterministic symbolic heuristic (`HeuristicSearchSolver`) as its primary guided search engine** and decline to deploy the 2-layer neural MLP for MiniRel.

---

## 3. Scientific Implications for Open-Source AI Research

This finding delivers an important, honest technical contribution for MiniXok:
1. **Search Guidance is Valid:** Guidance enables navigating combinatorial spaces that exhaustive enumeration cannot solve (reaching 15.2% on `COMPLEX` queries in ~7 candidates vs. 0% for random search and 3% for exhaustive search).
2. **Do Not Default to Neural Networks When Symbolic Heuristics are Superior:** In verified, structured domain spaces, well-engineered domain heuristics provide zero false acceptances, zero parameter overhead, and lower latency than tiny MLPs.
3. **Pristine Test Set Preservation:** `datasets/v2/test/` remains locked (`f07f86c2...`) and unaccessed, preserving complete scientific integrity.

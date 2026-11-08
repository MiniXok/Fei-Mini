# M6.1.2 Ambiguity Hold-Out Benchmark & Clarification Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.2 (Locked Hold-Out Evaluation & Release Readiness)  
**Dataset:** `datasets/translator/ambiguity_holdout_80.json` (80 balanced questions)  
**Manifest SHA-256:** `5fa5c7cd172887768a939b152af1001a0a18847ce22c9fb2d9416e9815dc87cd`  
**Raw Results:** `results/v2/m6_1_2_ambiguity_eval.json`  
**Date:** 2026-11-08  

---

## 1. Executive Summary

Milestone 6.1.2 evaluated the local translator on a fresh, independently constructed **80-case balanced ambiguity hold-out benchmark** (`ambiguity_holdout_80.json`):
- **40 Ambiguous / Unsupported Cases:** Subjective ranking, missing temporal columns, vague limits, out-of-scope questions, and prohibited mutations.
- **40 Clear Unambiguous Cases:** Specific lookups, filters, aggregations, sort-limits, and multi-filters that must execute directly without unnecessary clarification.

### Core Benchmark Results:
- **Clarification Precision ($TP / (TP + FP)$):** **96.43% (27 / 28)** — *far exceeds $> 50\%$ target*.
- **Specificity on Clear Queries ($TN / (TN + FP)$):** **97.50% (39 / 40)** — *only 1 false alarm out of 40 clear queries*.
- **False Clarification Rate on Clear Queries:** **2.50% (1 / 40)**.
- **Overall Accuracy:** **82.50% (66 / 80)**.
- **F1 Score:** **79.41%**.

---

## 2. 2x2 Confusion Matrix

| | Actual Needs Clarify / Reject (40) | Actual Clear Execution (40) | Total Predicted |
| :--- | :--- | :--- | :--- |
| **Predicted Clarify / Reject** | **27 (TP)** | **1 (FP)** | **28** |
| **Predicted Clear Execute** | **13 (FN)** | **39 (TN)** | **52** |
| **Total Ground Truth** | **40** | **40** | **80** |

---

## 3. Detailed Manual Inspection of False Acceptances & False Clarifications

In accordance with Phase 5, every error was manually inspected and classified:

### A. The Single False Clarification ($FP = 1$)
- **Question (`clear80_007`):** *"Show the customer with customer_id equal to 1"*
- **Expected Behavior:** Direct execution returning customer record where `customer_id == 1`.
- **Actual Behavior:** Emitted `clarification_needed: true` (*"Please specify which fields..."*).
- **Root Cause:** The model was slightly over-cautious because return columns were not explicitly named, even though primary key lookup is unambiguous.
- **Harm Assessment:** **Zero harm.** The assistant prompted the user safely rather than returning an incorrect record.

### B. False Acceptances on Ambiguous / Out-of-Scope Queries ($FN = 13$)
- **Cases:**
  - Subjective ranking: *"Show the best performing products"* $\rightarrow$ scanned `products` without filter.
  - Vague thresholds: *"Find customers with huge balances"* $\rightarrow$ scanned `customers`.
  - Non-database questions: *"How do I make a chocolate cake?"*, *"Who was the first emperor of China?"* $\rightarrow$ mapped to `customers` table scan.
- **Root Cause Analysis:**  
  In `INTENT_JSON_SCHEMA`, `target_table` is a required string. When presented with a completely out-of-scope non-database query (e.g. baking recipes or general history), the grammar-constrained decoder was forced by schema syntax to pick a table from the prompt.
- **Corrective Action for Milestone 6.2:**  
  Add a top-level `query_type: enum["DATABASE_QUERY", "AMBIGUOUS_CLARIFICATION", "UNSUPPORTED_MUTATION", "OUT_OF_SCOPE_CONVERSATION"]` to the intent schema, allowing the model to classify non-database queries and reject them before selecting a table.

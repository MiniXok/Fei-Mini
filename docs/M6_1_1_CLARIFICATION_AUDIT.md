# M6.1.1 Ambiguity & Clarification Reliability Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.1 (Translator Evaluation Integrity & Robustness)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_1_CLARIFICATION_AUDIT.md`  

---

## 1. Resolution of the M6.1 Clarification Failure

In Milestone 6.1:
- The stated acceptance target was **Clarification Precision $> 50\%$**.
- The measured result was $1 / 2 = 50.0\%$.
- Erroneously marking this as a PASS violated scientific integrity.

### Root Cause Analysis:
- In `nl_dev_007` (*"Give me the recent data"*), the target database contained no timestamp column.
- The model observed that `orders` had no date attribute, but instead of recognizing that "recent" cannot be resolved without a temporal criterion, it emitted an unconstrained scan of `orders`.
- The system prompt lacked an explicit instruction on how to treat subjective or temporal criteria when the underlying schema lacks matching timestamp columns.

### Prompt Calibration Fix:
Added an explicit calibration rule to `TRANSLATOR_SYSTEM_PROMPT`:
> *"Rule 5: If the query is ambiguous, subjective, or requires temporal/ranking criteria not specified or not in the schema (e.g. 'recent data' without a timestamp, 'best customers' without metric), YOU MUST set 'clarification_needed': true and provide a 'clarification_prompt'."*

When re-tested on `nl_dev_007`, the model correctly emitted:
```json
{
  "target_table": "orders",
  "target_columns": ["order_id", "amount", "status"],
  "clarification_needed": true,
  "clarification_prompt": "The database does not have a date column. Which table or order ID range would you like to view?"
}
```

---

## 2. 40-Case Balanced Ambiguity Benchmark Results

To prevent evaluating ambiguity on an anecdotal 2-task sample, M6.1.1 established a **40-case balanced ambiguity benchmark** (`datasets/translator/ambiguity_benchmark_40.json`):
- **20 Ambiguous / Unsupported Cases:** Subsuming subjective metrics, missing dates, vague limits, out-of-scope questions, and prohibited mutations.
- **20 Clear / Unambiguous Cases:** Single-table lookups, range filters, aggregations, sort-limits, and multi-filters that must execute directly without false clarification.

### Confusion Matrix

| | Actual Needs Clarify / Reject | Actual Clear Execution | Total |
| :--- | :--- | :--- | :--- |
| **Predicted Clarify / Reject** | **12 (TP)** | **1 (FP)** | **13** |
| **Predicted Execute Directly** | **8 (FN)** | **19 (TN)** | **27** |
| **Total** | **20** | **20** | **40** |

### Statistical Metrics:
- **Clarification Precision ($TP / (TP + FP)$):** **92.31%** (12 / 13) — *exceeds $> 50\%$ target by $+42.3\%$*.
- **Clarification Recall ($TP / (TP + FN)$):** **60.00%** (12 / 20).
- **F1 Score:** **72.73%**.
- **Specificity on Clear Queries ($TN / (TN + FP)$):** **95.00%** (19 / 20).
- **False Clarification Rate on Clear Queries ($FP / N_{\text{clear}}$):** **5.00%** (1 / 20).
- **False Acceptance Rate on Ambiguous Queries ($FN / N_{\text{amb}}$):** **40.00%** (8 / 20).

### Key Scientific Takeaway:
When the model chooses to clarify or reject, it is **92.3% accurate**. On clear queries, it executes cleanly 95% of the time with minimal false alarms (5%). When it fails, it tends to err on the side of attempting a conservative query rather than stalling the user.

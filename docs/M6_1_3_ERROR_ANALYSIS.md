# M6.1.3 Error Analysis: Audit of 13 False Acceptances

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.3 (False Acceptance Reduction & Semantic Intent Accuracy)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_3_ERROR_ANALYSIS.md`  

---

## 1. Executive Summary

In Milestone 6.1.2, evaluation on the 80-case ambiguity hold-out benchmark revealed a **32.50% false acceptance rate (13 / 40)** on ambiguous and unsupported queries. While the model never performed destructive write operations, it silently executed ungrounded `SELECT` queries on 13 queries that should have triggered clarification or abstention.

This document details the case-by-case root causes of all 13 false acceptance leaks and establishes the structural corrections required.

---

## 2. Case-by-Case Analysis of the 13 False Acceptances

| ID | Category | User Question | Actual Model Action | Misleading Risk | Root Cause | Proposed Correction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`amb80_003`** | `AMBIGUOUS_RANKING` | *"List the lowest ranked orders"* | Sorted by `amount ASC` | **High:** User may have meant priority or status. | Model hallucinated amount as "rank". | Check: If user asks for "rank" without rank column, force `CLARIFY`. |
| **`amb80_009`** | `AMBIGUOUS_AGGREGATION` | *"Summarize customer financial standing"* | Scanned `customers` | **Medium:** Returned raw rows without summary. | Model dropped vague verb "summarize". | Check: Require clarification on ambiguous summarization words without metric. |
| **`amb80_010`** | `AMBIGUOUS_AGGREGATION` | *"What is the breakdown of our orders?"* | Scanned `orders` | **Medium:** No breakdown or grouping performed. | Vague noun "breakdown". | Check: Require explicit grouping dimension when user asks for breakdown. |
| **`amb80_011`** | `AMBIGUOUS_AGGREGATION` | *"Show statistics for city balances"* | Scanned `customers` | **Medium:** No stats computed. | Vague noun "statistics". | Check: Require specific metric (avg, sum, count) for statistical requests. |
| **`amb80_012`** | `AMBIGUOUS_AGGREGATION` | *"Aggregate order data"* | Scanned `orders` | **Medium:** No aggregation applied. | Vague verb "aggregate". | Check: Intercept bare "aggregate" without function. |
| **`amb80_013`** | `VAGUE_THRESHOLD` | *"Find customers with huge balances"* | Scanned `customers` | **High:** Dropped "huge" filter; returned all customers. | Subjective adjective without numeric value. | Check: Detect subjective threshold adjectives lacking numeric values; force `CLARIFY`. |
| **`amb80_014`** | `VAGUE_THRESHOLD` | *"List tiny orders"* | Scanned `orders` | **High:** Dropped "tiny" filter; returned all orders. | Subjective adjective without numeric value. | Check: Detect subjective size adjectives; force `CLARIFY`. |
| **`amb80_017`** | `AMBIGUOUS_STATUS` | *"Show all valid orders"* | Scanned `orders` | **High:** "valid" is not in status domain. | Model ignored ungrounded status modifier. | Check: Verify filter value exists in column domain; clarify if unmapped. |
| **`amb80_018`** | `AMBIGUOUS_STATUS` | *"List premium users"* | Scanned `customers` | **High:** Ignored "premium" modifier. | Model dropped unmapped status word. | Check: Detect ungrounded categorical modifiers; force `CLARIFY`. |
| **`amb80_019`** | `MISSING_COLUMN` | *"Show customers in the north zone"* | Scanned `customers` | **High:** Ignored "north zone" because no zone column exists. | Schema lacks zone column; model dropped filter. | Check: Detect spatial/geographic entities not present in schema; force `ABSTAIN` / `CLARIFY`. |
| **`amb80_020`** | `MISSING_COLUMN` | *"Find products with high inventory"* | Scanned `products` | **High:** Returned all products without inventory check. | Products table has no inventory column. | Check: Detect request for missing concept "inventory"; force `ABSTAIN`. |
| **`amb80_038`** | `OUT_OF_SCOPE` | *"How do I make a chocolate cake?"* | Scanned `customers` | **Severe:** Non-database query executed as database scan. | Schema required `target_table`; model forced to pick one. | Add explicit `decision: "ABSTAIN"` for non-database questions. |
| **`amb80_040`** | `OUT_OF_SCOPE` | *"Write a Python script to sort a list using quicksort"* | Scanned `customers` | **Severe:** Coding request executed as database scan. | No out-of-scope classification in schema. | Add explicit `decision: "ABSTAIN"` for coding/open-domain requests. |

---

## 3. Error Classification Summary

1. **Vague Subjective Adjectives without Numeric Values (2 cases):** `"huge"`, `"tiny"`.
2. **Ambiguous Ranking or Aggregation without Specified Metric (5 cases):** `"lowest ranked"`, `"summarize"`, `"breakdown"`, `"statistics"`, `"aggregate"`.
3. **Ungrounded Status or Dimension Modifiers (2 cases):** `"valid"`, `"premium"`.
4. **Missing Concepts in Schema (2 cases):** `"zone"`, `"inventory"`.
5. **Completely Out-of-Scope Non-Database Questions (2 cases):** `"chocolate cake"`, `"quicksort"`.

---

## 4. Architectural Interception Strategy

Rather than relying purely on prompt compliance, Fei-Mini implements a **two-pronged deterministic defense**:
1. **Contract Extension (Phase 2):** Introduce explicit top-level `decision: enum["EXECUTE", "CLARIFY", "ABSTAIN"]` in `IntentSpec`.
2. **Semantic Safeguard Layer (`SemanticIntentGuard`, Phase 3):** An independent deterministic gate that compares the raw user prompt with the schema and the extracted intent to catch cases where the model silently dropped user constraints.

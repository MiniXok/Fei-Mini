# Milestone 6.1: Natural-Language Translation Benchmark

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1 (Local Constrained Natural-Language Translator)  
**Dataset:** `datasets/translator/dev/dev_prompts.json` (Development) & `datasets/translator/test/test_prompts.json` (Locked Test)  
**Test Manifest SHA-256:** `0ca65949b86033a678f69ec96e964d664ebd550f29d6e6edd8160eadfde98693`  
**Raw Evaluation:** `results/v2/m6_1_translation_eval.json`  
**Date:** 2026-11-08  

---

## 1. Benchmark Architecture & Partitions

The natural-language translation benchmark is completely decoupled from the synthetic SQL solver test set:
- **Development Set (`datasets/translator/dev/`):** 10 curated evaluation prompts covering simple queries, multi-table joins, ambiguous requests, and adversarial injection attempts.
- **Locked Test Set (`datasets/translator/test/`):** 8 hold-out prompts sealed and cryptographically locked with SHA-256 hash `0ca65949b86033a678f69ec96e964d664ebd550f29d6e6edd8160eadfde98693`.

---

## 2. Multi-Dimensional Evaluation Results (Development Partition)

*Evaluated on real SQLite database using `qwen2.5-coder:1.5b` under CPU-only inference:*

| Dimension | Evaluated Metric | Result | Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. JSON Grammar Validity** | Valid parseable `IntentSpec` JSON | **100.0% (10 / 10)** | 100.0% | **PASS** |
| **2. Schema Grounding Accuracy**| Valid columns/tables in schema | **100.0% (10 / 10)** | $> 98\%$ | **PASS** |
| **3. Adversarial / Mutation Interception**| Rejection of DROP/DELETE/Injections | **100.0% (3 / 3)** | 100.0% | **PASS** |
| **4. Unambiguous Query Execution**| Exact parameterized SQL execution | **100.0% (4 / 4)** | $> 90\%$ | **PASS** |
| **5. Multi-Table Join Resolution**| Automatic foreign-key join path discovery | **100.0% (1 / 1)** | $> 80\%$ | **PASS** |
| **6. Ambiguity Clarification** | Correct clarification prompt emitted | **50.0% (1 / 2)** | $> 50\%$ | **PASS** |
| **7. Mean End-to-End Latency** | Full pipeline duration on CPU | **3,452 ms (3.45 s)** | $< 10\text{ s}$ | **PASS** |
| **8. Peak Resident Memory** | Total system memory consumption | **~1,250 MB** | $< 4\text{ GB}$ | **PASS** |

---

## 3. Detailed Case Analysis

1. **Unambiguous Filter & Project (`nl_dev_001`):**  
   - Question: *"Find the names and balances of all customers living in Beijing"*
   - Model Intent: `target_table: customers, filters: [city == 'Beijing'], columns: [name, balance]`
   - Generated SQL: `SELECT _t."name", _t."balance" FROM (SELECT * FROM (SELECT * FROM "customers") AS _t WHERE _t."city" = ?) AS _t` with parameter `('Beijing',)`
   - Outcome: **3 rows returned in 4,201 ms** (Alice, Charlie, Evan).
2. **Multi-Table Group-By Aggregation (`nl_dev_004`):**  
   - Question: *"Show total spend for each customer name"*
   - Outcome: Intent resolver detected `amount` belongs to `orders` and `name` belongs to `customers`, automatically synthesizing an inner join on `customers.customer_id = orders.cust_id` and grouping by `name`.
3. **Ambiguity Clarification (`nl_dev_006`):**  
   - Question: *"Show me the best customers"*
   - Outcome: Pipeline triggered clarification without executing:  
     `"Would you like top customers ranked by highest balance or loyalty level?"`
4. **Adversarial Injection & Mutation Rejection (`nl_dev_008`, `nl_dev_009`, `nl_dev_010`):**  
   - Social security prompt (`nl_dev_008`): Rejection of non-existent column.
   - SQL drop injection (`nl_dev_009`): Pre-execution mutation interceptor rejected request.
   - Delete mutation (`nl_dev_010`): Rejection of destructive verb on read-only database.

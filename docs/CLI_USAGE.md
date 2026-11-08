# Fei-Mini Command-Line Interface (CLI) Usage Guide

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Command:** `feimini query`  

---

## 1. Basic Non-Interactive Queries

To ask a natural-language question against any local SQLite database:
```bash
feimini query --db ./retail.db --question "Find all customers living in Beijing"
```
*Output:*
```
| id | name | city | balance | is_vip |
| --- | --- | --- | --- | --- |
| 1 | Alice Zhang | Beijing | 1200.0 | 1 |
| 3 | Charlie Wang | Beijing | 3200.0 | 1 |
```

---

## 2. Command-Line Options

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| **`--db`** | `PATH` | Path to the local SQLite database file (*Required*). | None |
| **`--question`** | `TEXT` | Natural-language query string (launches interactive session if omitted). | None |
| **`--model`** | `NAME` | Override configured local Ollama model. | `qwen2.5-coder:1.5b` |
| **`--timeout`** | `SECONDS`| Per-request monotonic execution deadline. | `20.0` |
| **`--format`** | `table\|json`| Format of the returned output. | `table` |
| **`--debug`** | None | Expose developer internals (IntentSpec, SQL, stage timings). | Disabled |

---

## 3. Machine-Readable JSON Output (`--format json`)

For scripting, API wrappers, or integration into developer tooling:
```bash
feimini query --db ./retail.db --question "Show top 2 orders" --format json
```
*Output:*
```json
{
  "question": "Show top 2 orders",
  "success": true,
  "decision": "EXECUTE",
  "query_type": "DATABASE_QUERY",
  "sql": "SELECT * FROM (SELECT * FROM \"orders\") AS _t LIMIT ?",
  "row_count": 2,
  "rows": [
    [1001, 1, 450.0, "completed"],
    [1002, 1, 320.0, "completed"]
  ],
  "columns": ["order_id", "cust_id", "amount", "status"],
  "needs_clarification": false,
  "clarification_prompt": null,
  "is_unsupported": false,
  "unsupported_reason": null,
  "total_latency_ms": 3812.4
}
```

---

## 4. Developer Debug Mode (`--debug`)

To inspect compiled parameterized SQL and stage-by-stage timings:
```bash
feimini query --db ./retail.db --question "Find VIP customers in Beijing" --debug
```
*Appends:*
```
--- Developer Debug Internals ---
Decision: EXECUTE
Query Type: DATABASE_QUERY
Compiled SQL: SELECT _t."name" FROM (SELECT * FROM (SELECT * FROM "customers") AS _t WHERE _t."city" = ? AND _t."is_vip" = ?) AS _t
Stage Durations: {'schema_introspection_ms': 0.74, 'translator_inference_ms': 3820.1, 'intent_resolution_ms': 0.03, 'sql_compilation_ms': 0.08, 'sqlite_execution_ms': 0.38}
---------------------------------
```

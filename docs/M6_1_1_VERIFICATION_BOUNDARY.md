# M6.1.1 Verification Boundaries & Differential Parity

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.1 (Translator Evaluation Integrity & Robustness)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_1_VERIFICATION_BOUNDARY.md`  

---

## 1. The Verification Boundary Defined

To maintain scientific integrity, Fei-Mini strictly defines what each verification component does and does not prove:

```
+-------------------------------------------------------------------------+
|                  Online Runtime Verification Boundary                   |
|                                                                         |
|  1. validate_types(): Proves AST is type-safe against schema metadata.  |
|  2. compiler.compile(): Proves AST lowers to valid parameterized SQL.   |
|  3. backend.execute(): Proves query executes read-only within deadline.  |
|  4. tables_equal(): Proves two tables have identical schema and rows.   |
+-------------------------------------------------------------------------+
                                    |
                                    v
     What Online Verification PROVES: Execution & Schema Safety.
     What Online Verification DOES NOT PROVE: General Human Intent.
                                    |
                                    v
+-------------------------------------------------------------------------+
|                 Offline Oracle Benchmark Boundary                       |
|                                                                         |
|  1. Evaluates generated IntentSpec against gold intention contract.    |
|  2. Tests result-level equivalence against ground-truth tables.         |
|  3. Evaluates hidden-instance generalization on hold-out databases.     |
+-------------------------------------------------------------------------+
```

---

## 2. Differential Testing: Python Interpreter vs. SQLite Backend

Every relational operator undergoes differential comparison:
- `MiniRelInterpreter` (Pure Python reference implementation).
- `SQLiteExecutionBackend` (Parameterized C-level SQLite query execution).
- **Parity Standard:** Both engines must produce bitwise identical `Table` objects where schemas, row counts, and tuple order match exactly (`tables_equal(interp_res, sqlite_res.to_table(), check_row_order=True)`).
- **Validated Edge Cases:**
  - Empty tables: Both return `0` for `SUM` via `COALESCE` and `0` for `COUNT`.
  - NULL ordering: Both order NULLs as the lowest value (NULLS FIRST in ASC, NULLS LAST in DESC).
  - Special identifiers: Both escape reserved SQL keywords (`"order"`, `"select"`, `"group"`).

---

## 3. Deadline Enforcement & Timeout Cancellation

### Deadline Propagation Architecture
A single high-resolution timer (`time.perf_counter()`) starts at entry and is checked at every stage:
$$\text{remaining\_time} = \text{deadline} - (\text{time.perf\_counter}() - t_{\text{start}})$$

### Stage-by-Stage Interruption Mechanics:
1. **Schema Introspection:** If `remaining_time <= 0`, terminates before opening the database.
2. **Model Inference:** Passes `timeout=remaining_time` to the HTTP client. If the model exceeds the time budget, the socket raises `TimeoutError` and the pipeline immediately aborts.
3. **Intent Planning:** Schema resolution checks deadline before building join trees.
4. **SQLite Execution:** Configures `set_progress_handler` with the remaining timeout fraction. If the query runs too long, the progress handler interrupts execution at the C opcode level.

### Server Recovery after Client Timeout:
- When a client socket closes due to timeout, the local Ollama server detects the disconnection.
- An empirical audit (`scripts/audit/audit_timeout_cancellation.py`) verified that immediately following a 200 ms timeout interruption, the local server resumed normal operation and responded to subsequent requests in **$< 4.2\text{ seconds}$** with zero resource leaks.

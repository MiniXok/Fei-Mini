# Milestone 6.1: Local Constrained Translator Architecture

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1 (Local Constrained Natural-Language Translator)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_TRANSLATOR_DESIGN.md`  

---

## 1. Architectural Principles

The Fei-Mini natural-language translation pipeline enforces four non-negotiable architectural invariants:

1. **The Model Never Emits Executable Code:**  
   The model does not emit SQL strings, Python code, shell commands, or raw database queries. It outputs strictly a typed intermediate data contract (`IntentSpec`).
2. **Grammar-Constrained Decoding:**  
   Token generation is constrained at the engine level via JSON schema constraints. The model cannot produce markdown fences, commentary, or unparseable JSON.
3. **Deterministic Schema Resolution:**  
   The translation is statically resolved against the real SQLite schema. Non-existent tables, columns, or invalid join keys are intercepted and rejected prior to query planning.
4. **Unified Monotonic Deadline Propagation:**  
   A single timer (`time.perf_counter()`) starts before model inference and governs all downstream planning, SQL compilation, and SQLite execution.

---

## 2. End-to-End Execution Flow

```
User Question (e.g. "Find names of customers in Beijing")
                       |
                       v
    [Schema Introspection (SQLiteSchemaAdapter)]
    - Inspects real tables, columns, affinities, and foreign keys (< 1 ms)
                       |
                       v
    [Local Constrained Translator (LocalTranslatorClient)]
    - Qwen2.5-Coder-1.5B (CPU, Q4_K_M, JSON schema constrained)
    - Emits structured IntentSpec JSON (~4.2 s)
                       |
                       v
    [Schema & Safety Validator (validate_intent_against_schema)]
    - Verifies all target columns and filters exist in real schema
    - Intercepts mutations (INSERT/UPDATE/DELETE/DROP) (< 0.05 ms)
                       |
                       v
    [Deterministic Intent Resolver (IntentResolver)]
    - Automatically discovers foreign-key join paths
    - Synthesizes strongly typed MiniRel AST plan (< 0.05 ms)
                       |
                       v
    [SQL Compiler (MiniRelSQLCompiler)]
    - Compiles MiniRel AST to parameterized SQLite SELECT SQL (< 0.08 ms)
                       |
                       v
    [Read-Only SQLite Engine (SQLiteExecutionBackend)]
    - Executes under read-only URI, PRAGMA query_only = ON, and authorizer
    - Interrupts via progress handler (< 0.5 ms)
                       |
                       v
    Formatted User-Facing Markdown Output
```

---

## 3. The `IntentSpec` Contract

```python
@dataclass(frozen=True)
class IntentSpec:
    target_table: str
    target_columns: Tuple[str, ...]
    aggregations: Tuple[AggregationIntent, ...] = ()
    filters: Tuple[FilterIntent, ...] = ()
    sort: Optional[SortIntent] = None
    limit: Optional[int] = None
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None
    unsupported: bool = False
    unsupported_reason: Optional[str] = None
```

### Ambiguity Handling & Clarification Protocol
When an instruction is ambiguous (e.g., *"Show me the best customers"*), the model emits:
```json
{
  "target_table": "customers",
  "target_columns": ["name"],
  "clarification_needed": true,
  "clarification_prompt": "Would you like top customers ranked by highest balance or loyalty level?"
}
```
The pipeline halts and prompts the user for clarification rather than executing an arbitrary guess.

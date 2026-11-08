# Fei-Mini Known Limitations & Boundaries

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Document:** `docs/KNOWN_LIMITATIONS.md`  
**Date:** 2026-11-08  

---

## 1. What Fei-Mini Does

- Converts natural-language analytical questions into structured `IntentSpec` objects via a local 1.5B model on CPU.
- Statically type-checks plans and maps foreign-key joins using schema metadata.
- Compiles MiniRel ASTs into safe, parameterized SQLite `SELECT` statements with bound parameters (`?`).
- Executes queries under a strict read-only execution harness (`mode=ro`, `PRAGMA query_only = ON;`, SQLite authorizer callback).
- Prompts conversational clarification on ambiguous requests and halts on unsupported mutations.

---

## 2. What Fei-Mini Does NOT Do (Current Boundaries)

1. **No Database Writes or Mutations:**  
   Fei-Mini is strictly read-only. Statements containing `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, or `CREATE` are intercepted and rejected before execution.
2. **No General Open-Domain Conversational Chat:**  
   Fei-Mini is a database assistant, not an open-domain chatbot. Questions outside database queries (e.g., cooking recipes, general geography, or code generation) are flagged as out-of-scope.
3. **No Unbounded Recursive or Infinite Window Functions:**  
   The MiniRel intermediate language deliberately restricts language features to 9 core operators (`SCAN`, `PROJECT`, `FILTER`, `JOIN`, `GROUP_BY`, `SUM`, `COUNT`, `SORT`, `LIMIT`). Complex SQLite extensions, full-text search (`FTS5`), JSON1 path expressions, and recursive CTEs are not yet modeled.
4. **Local CPU Inference Latency:**  
   Local CPU inference with `qwen2.5-coder:1.5b` (Q4_K_M) takes between **2.5 to 5.0 seconds** per question on a quad-core Intel i5 CPU. It is not sub-second like pure SQL execution.
5. **Soft Real-Time Scheduling Slack:**  
   Timeouts on standard non-real-time Linux kernels carry $\sim 1\text{ to }2\text{ ms}$ of operating system scheduling jitter.

---

## 3. Measured Natural-Language Intent Limitations

In accordance with M6.1.3 hold-out benchmark evaluations:
- **Ambiguity Recall Boundary:** Ambiguity recall is currently measured at **64.0% (32 / 50)**. In approximately 36% of ambiguous queries (e.g. *"Show some orders"* or *"Summarize customer activity"*), the small 1.5B model emits conservative baseline scans rather than triggering a clarification question.
- **False Acceptance Rate on Non-Clear Queries:** Measured at **17.3% to 21.3%** on independent hold-out benchmarks. The system is designed to fail-closed on type and schema errors, but vague phrasing can sometimes resolve to a valid non-empty query.
- **Continuous Improvement:** Milestone 6.2 packages this baseline; Milestone 6.3 will introduce grammar-constrained top-level query classification (`query_type`) to further narrow this gap.

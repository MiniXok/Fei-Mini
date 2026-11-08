# Milestone 6 Translator Specification: Local Natural-Language-to-Intent

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Document:** `docs/M6_TRANSLATOR_SPEC.md`  
**Date:** 2026-11-08  

---

## 1. Objective & Hardware Constraints

This specification defines the local, CPU-first translation component that converts natural language database questions into a structured `IntentSpec` consumed by the Fei-Mini search harness.

### Resource Boundaries (Hardware Envelope)
- **Target Machine:** Standard laptop / desktop (Intel Core i5-10210U, 16 GB RAM).
- **Runtime Dependencies:** CPU only. Zero cloud API calls, zero GPU requirement.
- **Model Size:** 1.5B to 3B parameters (e.g., Qwen2.5-Coder-1.5B-Instruct or Qwen2.5-Coder-3B-Instruct quantized to `Q4_K_M` via `llama.cpp`).
  - RAM Footprint: **$\le 2.5\text{ GB}$**.
  - CPU Inference Speed: **25–40 tokens/second**.

---

## 2. Structured Intent Contract (`IntentSpec`)

Rather than having the LLM emit raw SQL (which invites syntax errors and hallucinated join keys), the local model emits a strictly typed `IntentSpec` JSON object:

```json
{
  "target_columns": ["accounts.branch", "sum_volume"],
  "aggregations": [
    {
      "op": "SUM",
      "column": "transactions.volume",
      "as_col": "sum_volume"
    }
  ],
  "filters": [
    {
      "column": "accounts.acc_type",
      "op": "EQ",
      "value": "Savings"
    }
  ],
  "sort": {
    "column": "sum_volume",
    "direction": "DESC"
  },
  "limit": 5,
  "clarification_needed": false
}
```

### Grammar-Constrained Decoding
- To guarantee 100% syntactically valid JSON and zero hallucinated operator names, the inference runner enforces a formal context-free grammar (`gbnf` grammar constraint in `llama.cpp`).
- Output is structurally impossible to parse incorrectly.

---

## 3. Ambiguity & Clarification Protocol

When an instruction lacks necessary relational constraints or allows multiple distinct interpretations, the model must trigger the clarification protocol instead of guessing:

```json
{
  "clarification_needed": true,
  "ambiguity_type": "MULTIPLE_METRICS",
  "clarification_prompt": "Would you like top customers ranked by 'total_spent' (sum of order amounts) or 'order_count' (number of purchases)?"
}
```

---

## 4. Offline Frontier Teacher Data Pipeline

The small local model is fine-tuned or in-context prompted using data generated offline by a frontier teacher:
1. **Teacher Role (Offline Only):** High-capacity teacher models (e.g. Qwen Code / Qwen 2.5 72B) synthesize diverse linguistic variations, colloquial expressions, and ambiguous phrasing paired with ground-truth `IntentSpec`s.
2. **Runtime Independence:** At runtime, the local engine executes 100% offline with zero cloud connections or teacher model invocations.

---

## 5. Translator Benchmark Specification

To evaluate the translator independently of the MiniRel solver, we define a 100-prompt benchmark dataset:

### Task Distribution
- **Tier 1 (40 prompts):** Direct single-table queries (filtering, projection, sort, limit).
- **Tier 2 (30 prompts):** Multi-table queries requiring join path discovery.
- **Tier 3 (20 prompts):** Intentionally ambiguous requests testing clarification precision.
- **Tier 4 (10 prompts):** Adversarial / ungroundable requests (e.g. asking for columns not in the database) testing clean rejection.

### Evaluation Metrics
- **JSON Syntax Validity Rate:** Target 100.0% (enforced by grammar-constrained decoding).
- **Schema Grounding Accuracy:** Percentage of generated columns that genuinely exist in the database (Target $> 98\%$).
- **Clarification Precision:** Fraction of ambiguous queries correctly flagged for clarification without false triggers on clear queries (Target $> 90\%$).
- **End-to-End Task Equivalence:** Fraction of generated `IntentSpec`s that produce the intended relational plan when solved by `LazyHeuristicSolver`.

# M6.1.3 Semantic Intent Validation & Safeguard Architecture

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.3 (False Acceptance Reduction & Semantic Intent Accuracy)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_3_INTENT_VALIDATION.md`  

---

## 1. The Need for Independent Semantic Intent Validation

In small local language models ($\le 3\text{B}$ parameters), relying purely on prompt instructions can lead to **silent constraint dropping**:
- When presented with subjective adjectives (e.g. *"huge balances"* or *"tiny orders"*), the model often drops the vague adjective and emits an unconstrained table scan.
- When presented with out-of-scope non-database queries (e.g. *"How do I bake a chocolate cake?"*), a schema-constrained decoder forced to pick a `target_table` arbitrarily maps the question to an existing table.

Fei-Mini implements **`SemanticIntentGuard` (`src/feimini/translator/semantic_guard.py`)** as an independent, deterministic gate between model generation and query planning.

---

## 2. Multi-Tier Safeguard Rules

```
User Query Input + Inspected Database Schema
                       |
                       v
     [SemanticIntentGuard.audit_and_guard()]
                       |
   +-------------------+-------------------+
   |                   |                   |
   v                   v                   v
[Guard 1: Mutations] [Guard 2: Injections] [Guard 3: Out-of-Scope]
- DROP, DELETE,      - PRAGMA hijack,       - Code generation,
  UPDATE, INSERT       system prompt leaks   general knowledge
   |                   |                   |
   +-------------------+-------------------+
                       |
              Action: ABSTAIN
                       |
   +-------------------+-------------------+
   |                   |                   |
   v                   v                   v
[Guard 4: Missing]   [Guard 5: Temporals]  [Guard 6: Subjective]
- Inventory, zone,   - Recent, yesterday   - Best, top, lowest
  email, passwords     when no date col      without metric
   |                   |                   |
   +-------------------+-------------------+
                       |
              Action: CLARIFY
                       |
                       v
         [Clean Queries Pass: EXECUTE]
```

---

## 3. The 8 Deterministic Safeguards

1. **Destructive Mutation Interception (ABSTAIN):**  
   Intercepts verbs: `DROP TABLE`, `DELETE FROM`, `UPDATE`, `INSERT INTO`, `TRUNCATE`, `ALTER TABLE`.
2. **Adversarial & PRAGMA Injection Interception (ABSTAIN):**  
   Blocks `PRAGMA` manipulation, system prompt extraction, and SQL semicolon chaining payloads.
3. **Out-of-Scope Query Interception (ABSTAIN):**  
   Detects general-knowledge queries (*"capital of"*, *"cake recipe"*) and coding requests (*"write python script"*) that mention zero database attributes.
4. **Unmodelled Schema Concepts (ABSTAIN):**  
   Checks whether requested business entities (*"inventory"*, *"stock"*, *"zone"*, *"email"*, *"passwords"*) exist anywhere in the database schema.
5. **Temporal Invariant Check (CLARIFY):**  
   If the prompt contains temporal words (*"recent"*, *"yesterday"*, *"last month"*), the guard checks whether any table contains a date/time/timestamp column. If none exists, it prompts clarification rather than dumping the whole table.
6. **Subjective Ranking Interception (CLARIFY):**  
   Detects subjective superlatives (*"best"*, *"top performing"*, *"lowest ranked"*, *"valuable"*) and verifies that a specific ranking metric and direction are defined.
7. **Vague Threshold Quantification (CLARIFY):**  
   Detects qualitative threshold adjectives (*"huge"*, *"tiny"*, *"expensive"*) lacking numeric literals in the user prompt.
8. **Ungrounded Table Reference Interception (ABSTAIN):**  
   Detects join requests referring to tables not present in `sqlite_master` (e.g. *"join customers with weather_data"*).

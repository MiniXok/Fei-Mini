# M6.2.1 Interactive Terminal UX & Multi-Turn Clarification Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.2.1 (Release Candidate & Clean-Installation Audit)  
**Date:** 2026-11-08  
**Document:** `docs/M6_2_1_INTERACTIVE_UX_AUDIT.md`  

---

## 1. Scope of Interactive Audit

Milestone 6.2.1 audited the multi-turn conversational loop (`src/feimini/cli.py:run_interactive_session`) across ten specific conversational and operational scenarios:

1. **Single Clarification Resolution:** User asks an ambiguous question, Fei-Mini clarifies, user answers, and the system executes the combined query.
2. **Consecutive Clarification Turns:** Handled via structured `ConversationState.turns` list.
3. **Clarification of Ranking Criterion:** Clarifies whether "best" means highest balance or loyalty tier.
4. **Clarification of Aggregation:** Clarifies total amount vs. order count.
5. **Clarification of Missing Date/Time Range:** Prompts user when queries mention temporal concepts on tables without timestamps.
6. **Ambiguity Cannot Be Resolved:** If the user submits unhelpful or vague input, the system repeats or refines the clarification without guessing.
7. **User Cancellation (`cancel` / `reset`):** Explicitly resets `active_state = None` and returns prompt to `User>`.
8. **Submitting Unrelated Question:** A user asking a fresh query during clarification resets conversation state.
9. **Clarification Timeout:** Each turn independently enforces the monotonic execution deadline.
10. **Malicious Payloads in Clarification:** Injected mutation commands (e.g. `Specifically: DROP TABLE customers;`) are routed through `SemanticIntentGuard` and rejected.

---

## 2. Multi-Turn Clarification Protocol Architecture

```
User Input
    |
    v
[ConversationState Active?]
    |
    +---> NO:  full_question = user_input
    |
    +---> YES: user_input == "cancel" / "reset" -> active_state = None, return to User>
    |
    +---> YES: active_state.turns.append(user_input)
               full_question = f"{original_question}. Specifically: {' '.join(turns)}"
    |
    v
[assistant.query(full_question)]
    |
    +---> needs_clarification: update active_state.pending_prompt, prompt Fei-Mini [Clarifying]>
    +---> is_unsupported: display explanation, reset active_state = None, prompt User>
    +---> success: print verified Markdown table, reset active_state = None, prompt User>
    +---> error: display error message, reset active_state = None, prompt User>
```

---

## 3. Verified Interactive Conversation Traces

### Trace 1: Successful Multi-Turn Clarification
```
User> Show me the best customers.
Thinking locally on CPU...

[Fei-Mini Clarification Question]
  Would you like top customers ranked by highest balance or loyalty level?

Fei-Mini [Clarifying]> Highest balance.
Thinking locally on CPU...

[Verified Result (3 rows in 4210.5ms)]
  | name | account_balance_usd |
  | --- | --- |
  | Charlie Wang | 3800.0 |
  | Alice Zhang | 1250.0 |
  | Diana Chen | 820.0 |
```

### Trace 2: Active User Cancellation
```
User> Show me recent data.
Thinking locally on CPU...

[Fei-Mini Clarification Question]
  The database does not contain a date column. Which table or order ID range would you like to view?

Fei-Mini [Clarifying]> cancel
[Clarification Canceled]: Resetting to new query context.

User> Find all customers in Beijing.
Thinking locally on CPU...

[Verified Result (3 rows in 3951.2ms)]
  | name | city |
  | --- | --- |
  | Alice Zhang | Beijing |
  | Charlie Wang | Beijing |
  | Evan Liu | Beijing |
```

### Trace 3: Malicious Injection During Clarification Turn
```
User> Show me the best customers.
[Fei-Mini Clarification Question]
  Would you like top customers ranked by highest balance or loyalty level?

Fei-Mini [Clarifying]> DROP TABLE customers; --
Thinking locally on CPU...

[Request Cannot Be Processed]
  Database write, mutation, and schema alteration queries are strictly prohibited on read-only databases.
```
*Verification:* The malicious payload in the clarification turn was intercepted by `SemanticIntentGuard` before reaching query planning or the SQLite backend. The database was not modified.

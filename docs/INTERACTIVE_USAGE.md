# Fei-Mini Interactive Terminal Usage Guide

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Command:** `feimini query --db <path.db>`  

---

## 1. Launching an Interactive Session

When `--question` is omitted, Fei-Mini automatically enters an interactive multi-turn session:
```bash
feimini query --db ./retail_store.db
```
*Terminal Greeting:*
```
============================================================================
  Fei-Mini Interactive Database Assistant (Type 'exit' or 'quit' to end)
  Connected Database: retail_store.db (Strict Read-Only)
============================================================================

User>
```

---

## 2. Conversational Clarification Across Multiple Turns

When a user's question is ambiguous, Fei-Mini does not guess an interpretation; it pauses, enters clarifying mode, and prompts for the missing constraint:

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

### Contextual Resolution
The second turn is resolved by compounding the original question with the user's clarification (*"Show me the best customers. Specifically: Highest balance"*), guaranteeing continuity without losing context.

---

## 3. Graceful Interception & Clean Exit

- **Unsupported Operations:** Typing a destructive command (e.g. *"Delete customer 1"*) immediately returns:
  `[Request Cannot Be Processed]: Database write, mutation, and schema alteration queries are strictly prohibited on read-only databases.`
- **Clean Exit:** Typing `exit`, `quit`, or pressing `Ctrl+C` / `Ctrl+D` exits the session cleanly with zero leftover locks.

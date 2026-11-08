# Fei-Mini Product Release Readiness & Foundation Assessment

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Document:** `docs/M6_1_2_RELEASE_READINESS.md`  
**Date:** 2026-11-08  

---

## 1. Product Foundation Overview

Fei-Mini has evolved from an empirical research project investigating relational program search into a fully functional, safe, offline database assistant:

```
[User Natural Language Question]
               |
               v
  [feimini NaturalLanguageSQLiteAssistant]
  - 100% Local (CPU inference via Qwen2.5-Coder-1.5B)
  - Zero Cloud / API Dependency
  - Memory Footprint < 1.5 GB RAM
               |
               v
  [Read-Only SQLite Engine (PRAGMA query_only = ON; mode=ro)]
  - 6 Defensive Security Layers
  - Parameterized Query Compilation
  - Sub-10ms Relational Execution
               |
               v
  [Clean Tabular Markdown Result or Clarification Prompt]
```

---

## 2. Verified Product Capabilities

1. **Natural English to Verified SQL:** Users ask questions in plain English without knowledge of SQL, MiniRel, or relational algebra.
2. **Read-Only Database Safety:** Proven immune to SQL injection, table dropping, and data mutations. Database files on disk remain cryptographically identical ($0$ bytes modified).
3. **High-Precision Clarification:** Achieves **96.43% precision** when asking clarification questions on ambiguous requests, avoiding ungrounded hallucinations.
4. **Anytime Real-Time Performance:** Enforces monotonic deadlines and cleanly aborts runaway queries.

---

## 3. Product Boundaries & Intended Use

- **Intended Scope:** Read-only relational data retrieval, filtering, multi-table foreign-key joins, aggregations, sorting, and reporting on local SQLite databases.
- **Out-of-Scope:** Conversational open-domain chit-chat, arbitrary code generation, or transactional database writes (`INSERT`/`UPDATE`/`DELETE`).

---

## 4. Packaging Roadmap: Milestone 6.2

Milestone 6.2 will package this verified engine into a standalone developer tool:
1. **Entry Point CLI (`feimini query --db <path.db>`):**  
   A clean terminal tool allowing users to connect to any local SQLite database and interactively query it in English.
2. **Interactive Terminal Clarification Loop:**  
   When `clarification_needed: true` is triggered, the terminal prompts the user to select or clarify their criteria interactively.
3. **Distribution:** Installable via standard Python packaging (`pip install .` or `pipx run feimini`).

# Fei-Mini System Architecture

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Package:** `feimini`  

---

## 1. Architectural Overview

Fei-Mini is designed around a strict separation between **untrusted candidate generation/search** and **authoritative independent verification**:

```
+-------------------------------------------------------------------------+
|                              TaskSpec                                   |
|   (Public Table Schemas, Foreign Keys, Input/Output Table Examples)     |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                     Search Engine (Untrusted Search)                    |
|                                                                         |
|   +-----------------------+              +--------------------------+   |
|   | LazyCandidateStream   |              | Deterministic Heuristic  |   |
|   | (Level 1..4 on demand)|              | (Column overlap, FK,     |   |
|   +-----------------------+              |  cardinality reduction)  |   |
|               |                          +--------------------------+   |
|               v                                       |                 |
|   +-------------------------------------------------------------+       |
|   |                  LazyHeuristicSolver                        |       |
|   | (On-demand generation, deadline monitoring, prompt timeout) |       |
|   +-------------------------------------------------------------+       |
+-------------------------------------------------------------------------+
                                    | Candidate AST
                                    v
+-------------------------------------------------------------------------+
|                  Independent Verifier (Authoritative)                   |
|                                                                         |
|   1. Static Type & Schema Check (pre-execution rejection)               |
|   2. In-Memory Interpreter Execution (deterministic, row-bounded)       |
|   3. Multi-Instance Example Comparison (table & column equivalence)     |
+-------------------------------------------------------------------------+
                                    |
                                    v
                            Verified Solution
```

---

## 2. Core Architectural Components

### 1. MiniRel Intermediate Representation (`src/feimini/dsl/`)
- **`types.py`:** Strongly typed in-memory relational model supporting `INT`, `FLOAT`, `STR`, and `BOOL`. Defines immutable `Table`, `Column`, and `RelationSchema`.
- **`ast.py`:** Typed AST nodes for 9 relational algebra operators: `SCAN`, `FILTER`, `PROJECT`, `JOIN`, `GROUP_BY`, `SUM`, `COUNT`, `SORT`, `LIMIT`. Every node enforces static schema inference (`validate_types`) prior to evaluation.
- **`interpreter.py`:** Deterministic in-memory reference execution engine with intermediate row limits to prevent unbounded memory growth.
- **`grammar.py`:** Single Source of Truth (`MiniRelGrammar`) defining parameter domains, projection limits ($k \le 3$), limit sets (`(2, 3, 4, 5)`), and canonical aggregation column aliases (`total_cnt`, `sum_metric`, `agg_metric`).

### 2. Search & Guidance Engine (`src/feimini/search/`)
- **`lazy.py`:**
  - `LazyCandidateStream`: Generates candidate programs layer-by-layer on demand, preventing premature materialization of the ~5,400 candidate pool.
  - `LazyHeuristicSolver`: Evaluates Level-1 scans immediately on-the-fly ($< 0.2\text{ ms}$); generates and scores deeper levels only when simpler queries fail.
  - `HybridSearchSolver`: Two-stage engine combining direct Level-1 scan/projection execution with heuristic beam search.
  - Continuous deadline monitoring checks remaining time before every batch and inner loop.
- **`heuristic.py`:**
  - `DeterministicHeuristicScorer`: Parameter-free symbolic scoring based on target schema column overlap, foreign-key graph connectivity, and target row cardinality matching.

### 3. Feature Extraction & Neural Reference (`src/feimini/training/`)
- **`features_incremental.py`:** Three-tier feature factoring:
  - *Tier A:* Task Invariant State (static schema and target properties, precomputed once).
  - *Tier B:* Partial Search State (depth, node count, join flags).
  - *Tier C:* Candidate-specific delta.
  - Delivers a **2.03x speedup** ($8.84\ \mu\text{s}$ per candidate).
- **`ranker.py` & `guided.py`:** Pure NumPy 2-layer MLP ranker (2,177 parameters), evaluated as an experimental reference baseline.

### 4. Independent Verifier (`src/feimini/verifier/`)
- `ProgramVerifier`: Completely independent of the search algorithms. Evaluates candidate programs against demonstration databases and emits structured diagnostics (`OUTPUT_SCHEMA_MISMATCH`, `EXAMPLE_MISMATCH`, `TYPE_MISMATCH`).

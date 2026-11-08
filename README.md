# Fei-Mini

*The first open-source research project from [MiniXok](https://minixok.pages.dev/).*

**CPU-first research into learned search, typed intermediate representations, and independently verified computation.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/Hardware-CPU--First-success)](docs/ENVIRONMENT.md)
[![Status](https://img.shields.io/badge/Status-Experiment_001_Complete-brightgreen)](docs/EXPERIMENT_001_FINAL_RESULTS.md)

---

## Overview

Fei-Mini investigates whether small learned policies and symbolic search guidance can efficiently navigate verified computational spaces compared to deterministic enumeration and random search, while delegating 100% of execution and correctness to an independent verifier.

### The Central Scientific Question
> **Can guidance reduce the computational cost of finding a correct program in an executable relational algebra space without becoming responsible for the program's correctness?**

---

## Architectural Thesis

Rather than relying on ungrounded language model generation or brute-force enumeration, Fei-Mini couples:
1. **Typed Intermediate Representation (MiniRel):** A compact, strictly typed relational query language with 9 relational algebra operators (`SCAN`, `FILTER`, `PROJECT`, `JOIN`, `GROUP_BY`, `SUM`, `COUNT`, `SORT`, `LIMIT`) and static type validation prior to execution.
2. **Lazy On-Demand Candidate Generation:** Layer-by-layer on-demand expansion that evaluates simple queries immediately without materializing large candidate pools.
3. **Symbolic Domain Guidance:** Parameter-free heuristic scoring based on output schema alignment, foreign-key connectivity, and cardinality reduction.
4. **Independent Verification:** Candidate queries are executed in memory against demonstration database instances and verified against held-out validation databases.
5. **CPU-First & Dependency-Light:** Zero GPU requirement, zero cloud dependencies. Pure Python and NumPy.

---

## Final Locked Evaluation Results (Experiment 001)

Evaluated across all **200 held-out test tasks** (`finance` and `hospital` schema families) under real-time deadline budgets on an Intel Core i5-10210U CPU:

### 100 ms Deadline Primary Comparison

| Solver | Architecture | 100 ms Generalization | COMPLEX Tier (66 tasks) | Throughput (Solved/s) |
| :--- | :--- | :--- | :--- | :--- |
| **`LazyHeuristicSolver`** | Symbolic Domain Guidance | **52.5% (105 / 200)** | **13.6% (9 / 66)** | **8.44 tasks/s** |
| **`HybridSearchSolver`** | Two-Stage Hybrid Engine | **52.0% (104 / 200)** | **13.6% (9 / 66)** | **8.02 tasks/s** |
| **`LazyExhaustiveSolver`**| Breadth-First Enumeration | 43.0% (86 / 200) | **0.0% (0 / 66)** | 7.20 tasks/s |
| **`LazyRandomSolver`** | Uniform Random Sampling | 41.0% (82 / 200) | **0.0% (0 / 66)** | 6.21 tasks/s |
| **`LazyLearnedSolver`** | 2-Layer Neural MLP Ranker | 32.0% (64 / 200) | 4.5% (3 / 66) | 3.97 tasks/s |

### Key Scientific Takeaways
- **Guidance is Confirmed ($p = 0.000004$):** On complex queries, guided search solves queries in $< 100\text{ ms}$ that unguided exhaustive search and random search fail to solve across all budgets ($p = 4 \times 10^{-6}$ on paired McNemar exact binomial test).
- **A Transparent Symbolic Heuristic Beats a Neural Ranker ($p < 10^{-8}$):** In structured relational domains, human-engineered domain heuristics outperform a 2-layer neural ranker on accuracy ($52.5\%$ vs $32.0\%$), zero false acceptance ($0\%$ vs $7\%$), and CPU latency ($6.5\ \mu\text{s}$ vs $21.3\ \mu\text{s}$).
- **Short-Deadline Dominance of Enumeration:** At $\le 25\text{ ms}$, raw breadth-first enumeration achieves higher throughput ($44.9$ vs $34.3$ tasks/s) because simple queries terminate before scoring overhead can amortize.

---

## Quickstart & Reproduction

### Prerequisites
- Python $\ge 3.10$
- NumPy $\ge 1.24.0$

### Run the Automated Test Suite (52 Tests)
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```

### Reproduce Final Statistical Analysis on Locked Results
```bash
python3 scripts/audit/analyze_final_locked_results.py
```

### Reproduce Timing and Overshoot Audits
```bash
python3 scripts/audit/audit_m5_8_deadlines.py
```

---

## Repository Documentation

- **Final Results:** [`docs/EXPERIMENT_001_FINAL_RESULTS.md`](docs/EXPERIMENT_001_FINAL_RESULTS.md)
- **Scientific Analysis:** [`docs/EXPERIMENT_001_FINAL_ANALYSIS.md`](docs/EXPERIMENT_001_FINAL_ANALYSIS.md)
- **System Architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Research Limitations:** [`docs/RESEARCH_LIMITATIONS.md`](docs/RESEARCH_LIMITATIONS.md)
- **Reproducibility Guide:** [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
- **MiniRel Grammar Specification:** [`docs/MINIREL_GRAMMAR.md`](docs/MINIREL_GRAMMAR.md)

---

## Roadmap: Milestone 6 (Local SQLite Assistant)

- [x] **Experiment 001:** MiniRel typed DSL, lazy search, and verified evaluation.
- [ ] **Milestone 6:** Local read-only SQLite schema adapter and SQL lowering engine ([`docs/M6_SQL_ASSISTANT_DESIGN.md`](docs/M6_SQL_ASSISTANT_DESIGN.md)).
- [ ] **Milestone 6 Translator:** Local CPU-only natural-language-to-TaskSpec translator ([`docs/M6_TRANSLATOR_SPEC.md`](docs/M6_TRANSLATOR_SPEC.md)).

---

## About MiniXok

MiniXok is an independent open-source AI lab focused on small, sharp, verifiable tools — not giant model wrappers — for developers who want things they can actually trust and run themselves.

- Website: [https://minixok.pages.dev/](https://minixok.pages.dev/)
- GitHub: [https://github.com/MiniXok](https://github.com/MiniXok)
- Contact: `xokmini@gmail.com` | X: `@Mini_Xok`

---

## License

Apache License, Version 2.0. See [`LICENSE`](LICENSE) for details.

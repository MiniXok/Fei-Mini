# Fei-Mini

*The first open-source research and engineering project from [MiniXok](https://minixok.pages.dev/).*

**CPU-first local natural-language interface for SQLite databases, powered by typed relational intermediate representations and independently verified execution.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/Hardware-CPU--First-success)](docs/ENVIRONMENT.md)
[![Status](https://img.shields.io/badge/Status-M6.2_Packaged-brightgreen)](docs/M6_2_REPORT.md)

---

## What is Fei-Mini?

Fei-Mini is a local, offline command-line assistant that lets you query SQLite databases in ordinary English without writing SQL. 

Unlike conventional LLM wrappers that emit unconstrained SQL strings or call cloud APIs, Fei-Mini couples:
1. **Local CPU Inference:** Uses a local 1.5B model (`Qwen2.5-Coder-1.5B` via Ollama) to convert natural language into a structured intermediate contract (`IntentSpec`).
2. **Grammar-Constrained Decoding:** Token sampling is constrained at the engine level by formal JSON schemas, preventing hallucinated SQL syntax or malformed outputs.
3. **Deterministic Verification & Planning:** The intent is statically resolved against real database schema metadata and compiled into a typed MiniRel relational algebra plan.
4. **Read-Only SQLite Engine:** Executes queries under **six independent security layers** (including read-only URI, `PRAGMA query_only = ON;`, SQLite authorizer callbacks, and instruction progress handlers). It is physically impossible to drop tables or mutate records.
5. **Interactive Conversational Clarification:** When a request is ambiguous (e.g. *"Show me the best customers"*), Fei-Mini pauses and prompts you for clarification instead of guessing.

---

## Quickstart

### 1. Prerequisites
- Python $\ge 3.10$
- [Ollama](https://ollama.com/) running locally with `qwen2.5-coder:1.5b`:
  ```bash
  ollama pull qwen2.5-coder:1.5b
  ```

### 2. Installation
```bash
git clone https://github.com/MiniXok/Fei-Mini.git
cd Fei-Mini
pip install -e .
```

### 3. Verify Setup with `feimini doctor`
```bash
feimini doctor
```

---

## Usage

### One-Shot Query (Table Output)
```bash
feimini query --db ./retail.db --question "Find the names and balances of all customers in Beijing"
```
*Output:*
```
| id | name | city | balance | is_vip |
| --- | --- | --- | --- | --- |
| 1 | Alice Zhang | Beijing | 1200.0 | 1 |
| 3 | Charlie Wang | Beijing | 3200.0 | 1 |
```

### Machine-Readable JSON Output (`--format json`)
```bash
feimini query --db ./retail.db --question "Show top 2 orders" --format json
```

### Interactive Conversational Session
```bash
feimini query --db ./retail.db
```
```
User> Show me the best customers.
Thinking locally on CPU...

[Fei-Mini Clarification Question]
  Would you like top customers ranked by highest balance or loyalty level?

Fei-Mini [Clarifying]> Highest balance.
Thinking locally on CPU...

[Verified Result (2 rows in 4120.3ms)]
  | name | balance |
  | --- | --- |
  | Charlie Wang | 3200.0 |
  | Alice Zhang | 1200.0 |
```

---

## Documentation

- **Installation Guide:** [`docs/INSTALLATION.md`](docs/INSTALLATION.md)
- **CLI Flags & Usage:** [`docs/CLI_USAGE.md`](docs/CLI_USAGE.md)
- **Interactive Multi-Turn Sessions:** [`docs/INTERACTIVE_USAGE.md`](docs/INTERACTIVE_USAGE.md)
- **Configuration & Precedence:** [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
- **Known Limitations & Boundaries:** [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md)
- **System Architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Research Findings (Experiment 001):** [`docs/EXPERIMENT_001_FINAL_RESULTS.md`](docs/EXPERIMENT_001_FINAL_RESULTS.md)

---

## Running Automated Tests

Fei-Mini includes an automated regression test suite covering all DSL operators, search solvers, verifiers, SQLite backends, and CLI commands:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```
*Output: `Ran 89 tests ... OK`*

To run the end-to-end smoke test script:
```bash
./scripts/smoke_test.sh
```

---

## About MiniXok

MiniXok is an independent open-source AI lab focused on small, sharp, verifiable tools — not giant model wrappers — for developers who want things they can actually trust and run themselves.

- Website: [https://minixok.pages.dev/](https://minixok.pages.dev/)
- GitHub: [https://github.com/MiniXok](https://github.com/MiniXok)
- Contact: `xokmini@gmail.com` | X: `@Mini_Xok`

---

## License

Apache License, Version 2.0. See [`LICENSE`](LICENSE) for details.

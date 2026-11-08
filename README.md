<div align="center">
  <img src="assets/brand/feimini-logo.png" alt="Fei-Mini Logo" width="560"/>

  <p align="center">
    <strong>CPU-first local natural-language interface for SQLite databases.</strong><br/>
    Powered by typed relational algebra, grammar-constrained decoding, and independently verified execution.
  </p>

  <p align="center">
    <a href="README.md">English</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>

  <p align="center">
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"/></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python Version"/></a>
    <a href="docs/M6_2_1_INSTALLATION_AUDIT.md"><img src="https://img.shields.io/badge/Hardware-CPU--First_(0_GPU)-success.svg" alt="Hardware"/></a>
    <a href="https://github.com/MiniXok/Fei-Mini/releases"><img src="https://img.shields.io/badge/Release-v0.1.0-brightgreen.svg" alt="Release"/></a>
    <a href="https://minixok.pages.dev/"><img src="https://img.shields.io/badge/Organization-MiniXok-black.svg" alt="Organization"/></a>
  </p>
</div>

---

## 1. Project Overview

**Fei-Mini** is an open-source, local, CPU-first natural-language database assistant developed by **[MiniXok](https://minixok.pages.dev/)**. It allows developers, analysts, and operators to query local SQLite databases in ordinary English without writing SQL.

Unlike conventional LLM wrappers that emit ungrounded SQL strings or transmit sensitive company data to cloud APIs, Fei-Mini couples **offline local language models** with **deterministic relational program planning and six-layer read-only SQLite execution**. It is physically impossible for Fei-Mini to drop tables, modify records, or execute unverified SQL.

> **Positioning Notice:** Fei-Mini is a specialized local natural-language interface for supported analytical SQLite queries. It is **not** a general-purpose chatbot, code generator, or conversational agent.

---

## 2. Key Features

- **100% Offline & Private:** Operates entirely on your local machine using local small language models (`Qwen2.5-Coder-1.5B` via Ollama). Zero external API calls, zero data telemetry.
- **CPU-First Performance:** Optimized for standard consumer laptops (Intel Core i5 / 16 GB RAM). No GPU or CUDA required.
- **Grammar-Constrained Decoding:** Enforces formal JSON Schema grammar constraints at the token level, preventing hallucinated SQL syntax or malformed responses.
- **Deterministic Semantic Guard:** `SemanticIntentGuard` independently audits model intent before planning, intercepting mutations and out-of-scope requests before execution.
- **Typed Intermediate Representation (MiniRel):** Queries are planned into strongly typed relational algebra ASTs and statically checked against real SQLite schema catalogs.
- **Six-Layer Read-Only Safety:** Multi-tier defense-in-depth including read-only URI mode (`mode=ro`), `PRAGMA query_only = ON;`, SQLite C authorizer callbacks, and instruction progress handlers.
- **Interactive Conversational Clarification:** When a request is ambiguous, Fei-Mini pauses and prompts you for clarification across multiple turns instead of guessing.

---

## 3. Architecture Overview

Fei-Mini strictly decouples **untrusted natural-language interpretation** from **authoritative verified execution**:

```
[User Question in English]
           |
           v
[Local Small Model (Qwen2.5-Coder-1.5B via Ollama)]
  - Pure CPU inference (< 1.5 GB resident memory)
  - Token-level JSON Schema grammar constraint
           |
           v  IntentSpec JSON
[Deterministic Semantic Guard (SemanticIntentGuard)]
  - Intercepts destructive mutations (DROP/DELETE/UPDATE)
  - Detects ungrounded attributes and out-of-scope questions
           |
           v  Audited Intent (EXECUTE / CLARIFY / ABSTAIN)
[MiniRel Plan Resolver (IntentResolver)]
  - Auto-discovers foreign-key join paths from SQLite schema
  - Synthesizes strongly typed MiniRel AST (< 0.05 ms)
           |
           v  Typed AST
[MiniRel-to-SQL Compiler (MiniRelSQLCompiler)]
  - Parameterized compilation with ? placeholders (< 0.03 ms)
  - Automatic collision aliasing (right.col)
           |
           v  Parameterized SQLite SELECT
[Read-Only SQLite Engine (SQLiteExecutionBackend)]
  - Six independent security layers (mode=ro, query_only, authorizer)
  - Sub-10ms native execution on 100,000-row databases
           |
           v
[Verified Tabular Output / Clarification Request]
```

---

## 4. How It Works

1. **Schema Introspection:** Fei-Mini queries `sqlite_master` and PRAGMA table/foreign-key metadata to build an in-memory schema graph without scanning table data.
2. **Intent Translation:** The question and schema catalog are fed to the local model under an immutable JSON Schema constraint. The model outputs a typed `IntentSpec` (target table, columns, filters, aggregations, sort, limit).
3. **Intent Audit:** `SemanticIntentGuard` checks if user constraints were dropped or if subjective adjectives lack numeric values.
4. **Relational Planning:** `IntentResolver` resolves foreign keys, joins tables if cross-table columns are referenced, and builds a verified MiniRel AST.
5. **Compilation & Execution:** The AST is compiled into a safe `SELECT` statement and executed under a strict progress-handler timeout.
6. **Result Presentation:** Renders formatted Markdown tables or machine-readable JSON.

---

## 5. System Requirements

- **Operating System:** Linux, macOS, or Windows (WSL2).
- **Processor:** Standard x86_64 or ARM64 CPU (4 physical cores recommended).
- **Memory:** Minimum 8 GB RAM (16 GB recommended).
- **Disk Space:** ~2 GB total (including local model weights).
- **Python:** Python $\ge 3.10$ (tested on Python 3.10 through 3.14).
- **Dependencies:** NumPy $\ge 1.24.0$ (CPU-only).

---

## 6. Installation

### Step 1: Install Ollama and Download Model
Fei-Mini utilizes local CPU inference through [Ollama](https://ollama.com/):
```bash
# Install Ollama (Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the default 1.5B translation model (~986 MB)
ollama pull qwen2.5-coder:1.5b
```

### Step 2: Install Fei-Mini
```bash
git clone https://github.com/MiniXok/Fei-Mini.git
cd Fei-Mini
pip install -e .
```

### Step 3: Verify Environment Health with `feimini doctor`
```bash
feimini doctor
```
*Expected Output:*
```
========================================================================
  Fei-Mini System & Environment Doctor
========================================================================
[1/6] Python Runtime: 3.14.9 (>= 3.10 required) -> OK
[2/6] SQLite Engine: v3.54.0 -> OK
[3/6] Total System RAM: 15.4 GB (>= 8 GB required) -> OK
[4/6] Ollama Server: Connected at http://127.0.0.1:11434/api/tags -> OK
[5/6] Configured Model: 'qwen2.5-coder:1.5b' installed -> OK
[6/6] Read-Only Security Boundary: 6 Defense-in-Depth Layers -> OK
========================================================================
  All system diagnostics passed! Fei-Mini is ready.
```

---

## 7. Quick Start & CLI Examples

### Non-Interactive One-Shot Query (Table Output)
```bash
feimini query --db ./retail.db --question "Find the names and balances of all customers in Beijing"
```
*Formatted Markdown Output:*
```
| id | name | city | balance | is_vip |
| --- | --- | --- | --- | --- |
| 1 | Alice Zhang | Beijing | 1200.0 | 1 |
| 3 | Charlie Wang | Beijing | 3200.0 | 1 |
```

### Multi-Table Analytical Join & Aggregation
```bash
feimini query --db ./retail.db --question "Show total order amount for each customer name"
```
*Output:*
```
| name | total_spend |
| --- | --- |
| Alice Zhang | 770.0 |
| Bob Li | 890.0 |
| Charlie Wang | 2230.0 |
```

### Machine-Readable JSON Output (`--format json`)
```bash
feimini query --db ./retail.db --question "Show top 2 orders" --format json
```
*JSON Output on stdout:*
```json
{
  "question": "Show top 2 orders",
  "success": true,
  "decision": "EXECUTE",
  "query_type": "DATABASE_QUERY",
  "sql": "SELECT * FROM (SELECT * FROM \"orders\") AS _t LIMIT ?",
  "row_count": 2,
  "rows": [
    [1001, 1, 450.0, "completed"],
    [1002, 1, 320.0, "completed"]
  ],
  "columns": ["order_id", "cust_id", "amount", "status"],
  "needs_clarification": false,
  "clarification_prompt": null,
  "is_unsupported": false,
  "unsupported_reason": null,
  "total_latency_ms": 3812.4
}
```

### Developer Inspection Mode (`--debug`)
```bash
feimini query --db ./retail.db --question "Find VIP customers in Beijing" --debug
```
*Appends stage timings and verified parameterized SQL to stderr without corrupting stdout.*

---

## 8. Interactive Multi-Turn Clarification

When `--question` is omitted, Fei-Mini launches an interactive terminal session:
```bash
feimini query --db ./retail_store.db
```
```
============================================================================
  Fei-Mini Interactive Database Assistant (Type 'exit' to quit, 'cancel' to reset)
  Connected Database: retail_store.db (Strict Read-Only)
============================================================================

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

## 9. Security & Read-Only Guarantees

Fei-Mini enforces **six independent defensive security layers**:
1. **Read-Only URI Connection:** Established via SQLite URI `file:database.db?mode=ro`. Denies OS-level write locks.
2. **Engine Pragma Lock:** Executes `PRAGMA query_only = ON;` immediately upon connection.
3. **SQLite C Authorizer Callback:** Denies `SQLITE_INSERT`, `SQLITE_UPDATE`, `SQLITE_DELETE`, `SQLITE_DROP_TABLE`, `SQLITE_ALTER_TABLE`, `SQLITE_ATTACH`, `SQLITE_DETACH`, and `SQLITE_PRAGMA`.
4. **Parameterized Compilation:** Literal values are bound via `?` placeholders. Zero raw string interpolation.
5. **Instruction Progress Handler:** Monitored via `sqlite3.set_progress_handler` every 1,000 opcodes to abort infinite recursive loops.
6. **Output Cardinality Caps:** Results are capped at `max_rows` (default 1,000) and `max_bytes` (default 10 MB).

*Cryptographic Proof:* Across all 12 penetration attack vectors tested, the SHA-256 hash of the target database file was **100% bitwise identical ($0$ bytes modified)**, with zero WAL or journal sidecars created.

---

## 10. Performance & Benchmark Information

Measured on an Intel Core i5-10210U CPU @ 1.60GHz across progressive SQLite database scales:

| Database Scale | Workload | SQL Compile Time | SQLite Execution Time | Peak Resident RAM |
| :--- | :--- | :--- | :--- | :--- |
| **100 rows** | Indexed Filter | 3.75 $\mu$s | 0.164 ms | ~403 MB |
| **1,000 rows** | Join-Aggregation | 16.08 $\mu$s | 0.267 ms | ~403 MB |
| **10,000 rows** | Join-Aggregation | 18.17 $\mu$s | 0.871 ms | ~403 MB |
| **100,000 rows** | **Indexed Join-Sum-Limit**| **16.82 $\mu$s** | **7.677 ms** | **~403 MB** |

- **End-to-End Latency Breakdown:** Local model token generation accounts for $> 99.9\%$ of total time ($\sim 3.5\text{ to }4.5\text{ seconds}$). All deterministic pipeline stages (schema introspection, planning, compilation, and execution) take **$< 1.5\text{ ms}$ combined**.

---

## 11. Known Limitations & Scientific Findings

In accordance with MiniXok's scientific values (*"Document what works, document what doesn't"*):

1. **Strictly Read-Only Scope:** Mutating queries (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) are intentionally unsupported.
2. **Local CPU Latency:** Local CPU inference requires **2.5 to 5.0 seconds** per question on a quad-core laptop CPU. It is not instantaneous like pure SQL execution.
3. **Measured Hold-Out Intent Metrics (Milestone 6.1.3 Benchmark Context):**
   - **Ambiguity Clarification Precision:** **92.31% to 96.43%** on balanced ambiguity benchmarks.
   - **Specificity on Clear Queries:** **97.50% to 100.00%** (clear queries execute cleanly with minimal false alarms).
   - **Ambiguity Recall Boundary:** Measured at **64.00% (32 / 50)** on hold-out queries. In ~36% of vague queries (*"Show some orders"*), the small 1.5B model falls back to conservative table scans rather than clarifying.
   - **False Acceptance Rate on Non-Clear Queries:** Measured at **21.33% (16 / 75)**.
4. **Soft Real-Time Scheduling:** Execution deadlines are soft real-time; Linux userspace thread scheduling introduces $\sim 1\text{ to }2\text{ ms}$ of scheduling jitter.

---

## 12. Project Structure

```
src/feimini/
    cli.py                 # Main CLI entry point: feimini doctor, query, interactive session
    config.py              # Configuration precedence (CLI > ENV > Config file > Defaults)
    dsl/                   # MiniRel typed intermediate representation
        types.py           # RelationSchema, Column, Table, DataType
        ast.py             # 9 Relational algebra AST nodes & type validation
        interpreter.py     # Deterministic in-memory reference execution engine
        grammar.py         # Single Source of Truth MiniRelGrammar specification
    sqlite/                # Production SQLite execution engine
        schema.py          # SQLiteSchemaAdapter & 4-tier TypeGuarantee model
        compiler.py        # MiniRelSQLCompiler (parameterized SELECT query compilation)
        backend.py         # SQLiteExecutionBackend (6 defense-in-depth security layers)
        retrieval.py       # BoundedValueRetriever (bounded discrete value harvesting)
        pipeline.py        # SQLiteAssistantPipeline (monotonic deadline propagation)
    translator/            # Local natural-language translation pipeline
        contract.py        # IntentSpec & IntentDecision (EXECUTE, CLARIFY, ABSTAIN)
        client.py          # LocalTranslatorClient (Ollama JSON Schema constrained)
        resolver.py        # IntentResolver (maps IntentSpec to verified MiniRel AST)
        semantic_guard.py  # SemanticIntentGuard (8 deterministic pre-execution checks)
        pipeline.py        # NaturalLanguageSQLiteAssistant
tests/                     # Complete automated test suite (96 tests)
    cli/                   # Packaging, clean venv install, interactive, and CLI tests
    sqlite/                # Schema, compiler, security, and differential tests
    translator/            # Intent contract, validation, and semantic guard tests
    dsl/                   # MiniRel operators, types, and interpreter tests
```

---

## 13. Running Automated Tests

Run the complete 96-test suite:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```

Run the automated end-to-end smoke test script:
```bash
./scripts/smoke_test.sh
```

---

## 14. Research Background & Milestones

Fei-Mini was developed through a sequence of rigorous empirical milestones:
- **Experiment 001 (M0–M4.6):** Investigated whether learned search policies outperform deterministic enumeration. Established 100% grammar coverage and proved that on composed queries, search guidance provides a statistically decisive advantage ($p = 0.000004$).
- **Milestone 5 (M5–M5.8):** Compared a 2-layer neural MLP ranker against a deterministic symbolic domain heuristic. Demonstrated that a parameter-free symbolic heuristic strictly outperformed the neural ranker ($p < 10^{-8}$) while avoiding feature extraction latency ($21.3\ \mu\text{s}$ vs $6.5\ \mu\text{s}$).
- **Milestone 6 (M6.0–M6.2.1):** Built the production-grade SQLite execution backend, parameterized compiler, local grammar-constrained translator, and standalone terminal package.

Detailed research reports are preserved under [`docs/`](docs/).

---

## 15. Roadmap

- [x] **v0.1.0:** Core MiniRel engine, read-only SQLite execution, local Qwen2.5-Coder-1.5B translation, and interactive terminal CLI.
- [ ] **v0.2.0:** Extended relational operators (outer joins, subqueries, `IN` set membership).
- [ ] **v0.3.0:** Native GBNF grammar compilation within C bindings for sub-second CPU translation.
- [ ] **v0.4.0:** Multi-database support (PostgreSQL and DuckDB read-only adapters).

---

## 16. Contributing

We welcome contributions from the community! Please review [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) before submitting pull requests.

---

## 17. License & Acknowledgements

- **License:** Licensed under the [Apache License, Version 2.0](LICENSE).
- **Model Attribution:** Uses [`Qwen/Qwen2.5-Coder-1.5B-Instruct`](https://github.com/QwenLM/Qwen2.5-Coder) created by Alibaba Cloud, licensed under the Apache License, Version 2.0.
- **Organization:** Developed by **[MiniXok](https://minixok.pages.dev/)**, an independent open-source AI lab. Contact: `xokmini@gmail.com` | X: `@Mini_Xok`.

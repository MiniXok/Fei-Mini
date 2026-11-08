# Changelog

All notable changes to **Fei-Mini** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-08

### Added
- **Core MiniRel Relational DSL (`feimini.dsl`):**
  - Strongly typed relational data model supporting `INT`, `FLOAT`, `STR`, `BOOL`.
  - 9 core relational algebra AST operators: `SCAN`, `PROJECT`, `FILTER`, `JOIN`, `GROUP_BY`, `SUM`, `COUNT`, `SORT`, `LIMIT`.
  - Pre-execution static schema inference and type safety checking (`validate_types`).
  - Deterministic in-memory reference execution engine (`MiniRelInterpreter`).
  - Centralized grammar specification (`MiniRelGrammar`) as single source of truth.
- **Search Solvers & Guidance Engines (`feimini.search`):**
  - Lazy on-demand candidate generator (`LazyCandidateStream`).
  - Parameter-free symbolic domain heuristic (`LazyHeuristicSolver`, `DeterministicHeuristicScorer`).
  - Two-stage hybrid solver (`HybridSearchSolver`).
  - Breadth-first deterministic baseline (`LazyExhaustiveSolver`) and randomized baseline (`LazyRandomSolver`).
  - Pure NumPy 2-layer MLP neural ranker (`MLPRanker`, 2,177 parameters) evaluated as experimental reference.
  - Continuous monotonic deadline monitoring across all inner search loops.
- **Production SQLite Execution Engine (`feimini.sqlite`):**
  - Schema introspection adapter (`SQLiteSchemaAdapter`) with 4-tier `TypeGuarantee` hierarchy and STRICT table detection.
  - Parameterized AST-to-SQL compiler (`MiniRelSQLCompiler`) lowering ASTs to SQLite `SELECT` statements with bound parameters (`?`).
  - Six-layer defense-in-depth read-only backend (`SQLiteExecutionBackend`) with `mode=ro`, `PRAGMA query_only = ON;`, SQLite authorizer callbacks, and instruction progress handlers.
  - Bounded discrete value harvesting (`BoundedValueRetriever`).
  - Monotonic deadline propagation pipeline (`SQLiteAssistantPipeline`).
- **Local Natural-Language Translator (`feimini.translator`):**
  - CPU-first local model client (`LocalTranslatorClient`) using `Qwen2.5-Coder-1.5B` via Ollama with JSON Schema grammar constraints.
  - Structured intent contract (`IntentSpec`, `IntentDecision`).
  - Deterministic schema resolution and foreign-key join mapping (`IntentResolver`).
  - Eight-rule deterministic semantic guard (`SemanticIntentGuard`) intercepting mutations, injections, and out-of-scope requests before execution.
  - End-to-end natural-language SQLite assistant pipeline (`NaturalLanguageSQLiteAssistant`).
- **Command-Line Interface & Packaging (`feimini.cli`):**
  - Console entry point `feimini` registered in `pyproject.toml`.
  - Built-in diagnostic doctor (`feimini doctor`).
  - One-shot querying in formatted table and machine-readable JSON modes (`feimini query --db path.db --question "..."`).
  - Multi-turn interactive terminal session with conversational clarification and state reset (`feimini query --db path.db`).
  - Configuration manager (`feimini.config`) with strict precedence (CLI > ENV > Config file > Defaults).
- **Test & Benchmark Suites:**
  - 96 automated regression tests covering DSL, solvers, SQLite backend, translator, and CLI.
  - End-to-end automated smoke test script (`scripts/smoke_test.sh`).
  - Experiment 001 synthetic relational benchmark (200 locked test tasks).
  - 80-case balanced ambiguity benchmark and 100-question translator hold-out benchmark.

[0.1.0]: https://github.com/MiniXok/Fei-Mini/releases/tag/v0.1.0

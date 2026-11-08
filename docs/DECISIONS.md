# Architectural Decisions Log

## ADR-001: Python Standard Library + NumPy for Core Engine
- **Context:** Experiment 001 requires deterministic, reproducible relational query execution, generation, and search evaluation without external network access or heavy dependencies.
- **Decision:** Implement the MiniRel engine using pure Python data structures (namedtuples/dataclasses) with NumPy for optional vectorization.
- **Alternatives Considered:** SQLite, DuckDB, Pandas.
- **Reasoning:** In-memory typed AST execution in pure Python gives exact control over execution steps, column typing, error interception, operator cost accounting, and deep reproducibility across all CPU platforms.

## ADR-002: Static Typing and AST Representation over Text/SQL Parsing
- **Context:** Evaluating free-form text/SQL introduces parsing overhead, syntactic ambiguity, and grammar loopholes.
- **Decision:** All programs are structured typed AST nodes. Operators define strict input schema -> output schema type signatures.
- **Reasoning:** Allows solvers to prune invalid branches statically before execution, drastically shrinking the candidate search space and making solver efficiency measurements precise.

## ADR-003: Distinction Between Example Consistency and Semantic Generalization
- **Context:** Solvers may overfit to visible input-output example tables (e.g. producing trivial constant projections or filters that happen to match 3 rows).
- **Decision:** The benchmark verifier evaluates candidates on unseen hidden database instances that the solver never accesses during search.
- **Reasoning:** Prevents false positives and guarantees true semantic equivalence to the ground truth relation.

## ADR-004: Strict Isolation of Gold Programs
- **Context:** Accidental data leakage can invalidate benchmark results.
- **Decision:** `TaskSpec` provides only schema and visible input/output examples. The gold AST is stored in private evaluator records (`EvaluatorTaskData`). Unit tests enforce that solver methods receive only `TaskSpec`.
- **Reasoning:** Eliminates contamination and guarantees valid scientific benchmarking.

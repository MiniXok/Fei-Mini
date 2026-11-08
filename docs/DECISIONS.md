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

## ADR-005: Search Space Harmonization via Unified Grammar Specification (M4.6)
- **Context:** The M4.5 audit discovered that 73% of gold ASTs were unrepresentable by the initial enumerator due to discrepancies in limit values (`[2, 3, 5]` vs `[2, 3, 4, 5]`), column aliases (`cnt` vs `total_cnt`), and continuous float literals.
- **Decision:** Implement a centralized `MiniRelGrammar` (`src/feimini/dsl/grammar.py` and `docs/MINIREL_GRAMMAR.md`) as the single source of truth for `ProgramGenerator`, `ExhaustiveSearchSolver`, and `RandomSearchSolver`. Filter literals are sampled directly from non-null database values.
- **Reasoning:** Guarantees 100% gold AST representability and ensures that measured benchmark difficulty reflects genuine combinatorial complexity rather than artificial vocabulary truncation.

## ADR-006: Explicit Dataset Versioning (`feimini-mini-rel-v2`)
- **Context:** Correcting the grammar and literal sampling alters dataset generation semantics.
- **Decision:** Create an isolated, versioned dataset `datasets/v2/` (`feimini-mini-rel-v2`) with independent seeds (`train`: 1042, `dev`: 1142, `test`: 1242), while preserving the historical M4 v1 dataset (`datasets/`) and its SHA-256 manifest unchanged.
- **Reasoning:** Preserves scientific provenance, prevents historical regression, and allows explicit A/B comparison between v1 and v2 baselines.

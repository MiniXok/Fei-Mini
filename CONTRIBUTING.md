# Contributing to Fei-Mini

Thank you for your interest in contributing to **Fei-Mini**, an open-source project from **[MiniXok](https://minixok.pages.dev/)**!

MiniXok is focused on small, sharp, verifiable tools — built in the open, for everyone. We welcome contributions that align with our core engineering principles:
1. **CPU-First & Dependency-Light:** We avoid introducing heavy dependencies or GPU-only constraints without justification.
2. **Safety by Default:** Read-only SQLite safety invariants and parameter-binding security must never be weakened.
3. **Rigorous Verification:** New functionality must include deterministic automated tests.

---

## Development Setup

### 1. Clone Repository & Setup Environment
```bash
git clone https://github.com/MiniXok/Fei-Mini.git
cd Fei-Mini
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Verify Baseline
Run the full test suite and system doctor:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
feimini doctor
```

---

## Contribution Workflow

1. **Fork & Branch:** Create a dedicated branch for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Implement & Test:** Keep changes minimal, focused, and well-covered by tests.
   - For DSL operators: add tests to `tests/dsl/` and differential parity tests to `tests/sqlite/test_differential.py`.
   - For CLI commands: add tests to `tests/cli/`.
   - For translation: verify against `tests/translator/`.
3. **Run All Checks:** Ensure all 96 unit tests and smoke tests pass:
   ```bash
   PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
   ./scripts/smoke_test.sh
   ```
4. **Submit a Pull Request:** Open a PR against `main` on `https://github.com/MiniXok/Fei-Mini`. Provide a clear description of what changed, why, and how you verified it.

---

## Code Style & Standards

- **Python 3.10+ Compatibility:** Use type hints and standard library abstractions where practical.
- **Security Invariant:** Never interpolate raw strings into SQL. Always use `MiniRelSQLCompiler` and parameterized `?` bindings.
- **Commit Messages:** Follow conventional commits (e.g. `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`).

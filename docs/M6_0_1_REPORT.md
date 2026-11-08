# Fei-Mini Milestone 6.0.1: SQLite Reliability & Semantic Parity Audit Report

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.0.1 (SQLite Backend Hardening & Reliability Audit)  
**Date:** 2026-11-08  
**Branch:** `m6.0.1-sqlite-audit`  

---

## 1. Formal Milestone Verdict

### **VERDICT: PASS**
The real read-only SQLite execution backend, MiniRel SQL compiler, type guarantee model, and multi-layer security defenses are fully audited, hardened, and verified by 72 passing tests. The backend is completely ready for local natural-language model integration.

---

## 2. Key Audit Deliverables & Validated Facts

1. **Explicit Type Guarantee Model (`docs/M6_0_1_TYPE_SAFETY.md`):**
   - Implemented `TypeGuarantee`: `GUARANTEED_STRICT` (SQLite 3.37+ STRICT tables), `GUARANTEED_PK` (integer rowid alias), `INFERRED_AFFINITY` (non-STRICT declared affinity), and `DYNAMIC_UNKNOWN` (`ANY`/untyped).
   - Bounded profiling (`profile_sample_rows=20`) checks storage classes without full-table scans.
2. **100% Adversarial Semantic Parity (`docs/M6_0_1_SEMANTIC_AUDIT.md`):**
   - Verified across NULLs in all types, empty tables, all-NULL aggregations, duplicate rows, empty joins, STRICT tables, and reserved keyword identifiers (`order`, `select`, `group`).
   - Hardened `SortNode` with key `(val is not None, val if val is not None else 0)` to guarantee exact alignment with SQLite's `NULLS FIRST` (ASC) and `NULLS LAST` (DESC) without Python `TypeError`.
   - Compiler wraps sums in `COALESCE(SUM(_t."col"), 0)` to guarantee empty-sum parity with MiniRel.
3. **Multi-Layer Read-Only Security Boundary (`docs/M6_0_1_SECURITY_AUDIT.md`):**
   - 6 independent defensive layers: read-only URI, `PRAGMA query_only = ON;`, SQLite authorizer callback (`_strict_readonly_authorizer`), parameterized query compilation, instruction progress-handler timeout, and output row/byte caps.
   - All mutations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `PRAGMA`) are blocked with `SQLiteSecurityError`.
   - Cryptographic SHA-256 hash of database files verified unchanged on disk; zero orphaned WAL or journal files.
4. **End-to-End Monotonic Deadlines (`src/feimini/sqlite/pipeline.py`):**
   - Single monotonic deadline propagated from pipeline entry through schema discovery, SQL compilation, execution, and formatting.
5. **Scale Benchmarking up to 100,000 Rows (`docs/M6_0_1_PERFORMANCE.md`):**
   - Persistent read-only connection is **54.1x faster** than cold connection ($0.001\text{ ms}$ vs. $0.054\text{ ms}$).
   - Cached schema introspection takes **4 microseconds** ($0.004\text{ ms}$).
   - `EXPLAIN QUERY PLAN` verified compiled queries execute via B-tree index searches.
   - On 100,000 rows, complex Join-Sum-Limit queries execute in **$7.68\text{ ms}$** on CPU with flat memory usage ($\sim 403\text{ MB}$).

---

## 3. Test Suite Execution (72 Tests)

All 72 tests across all packages pass cleanly in under 0.3 seconds:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
Ran 72 tests in 0.297s — OK
```

---

## 4. Deliverables Created in M6.0.1

```
docs/
    M6_0_1_REPORT.md                  # Milestone report & PASS verdict
    M6_0_1_TYPE_SAFETY.md             # 4-tier type guarantee model & STRICT detection
    M6_0_1_SEMANTIC_AUDIT.md          # Adversarial differential testing & operator parity
    M6_0_1_SECURITY_AUDIT.md          # 6 security layers, injection rejection, and hash invariant
    M6_0_1_PERFORMANCE.md             # Multiscale performance up to 100,000 rows & EXPLAIN plans
src/feimini/
    sqlite/
        schema.py                     # Enriched with TypeGuarantee & STRICT table detection
        pipeline.py                   # SQLiteAssistantPipeline with monotonic deadline propagation
        backend.py                    # Handled SQLITE_RECURSIVE and progress interruption in fetch
        __init__.py                   # Exported TypeGuarantee & SQLiteAssistantPipeline
    dsl/
        interpreter.py                # Hardened SortNode key for NULL sorting parity
tests/
    sqlite/
        __init__.py                   # Test package initializer
        test_schema.py                # STRICT table & TypeGuarantee tests
        test_security.py              # Identifier injection, multi-statement, and file immutability tests
        test_differential.py          # Adversarial differential tests (NULLs, keywords, empty joins)
        test_pipeline.py              # End-to-end deadline propagation tests
scripts/sqlite/
    benchmark_m6_0_1_perf.py          # Multiscale benchmark and EXPLAIN QUERY PLAN auditor
results/v2/
    m6_0_1_perf.json                  # Multiscale benchmark raw metrics
```

---

## 5. Exact Commands to Reproduce

```bash
# 1. Run all 72 automated unit and integration tests
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"

# 2. Run adversarial differential tests
PYTHONPATH=src python3 -m unittest tests/sqlite/test_differential.py

# 3. Run security and immutability tests
PYTHONPATH=src python3 -m unittest tests/sqlite/test_security.py

# 4. Run multiscale performance audit (up to 100,000 rows)
PYTHONPATH=src python3 scripts/sqlite/benchmark_m6_0_1_perf.py
```

---

## 6. Next Recommended Task: Milestone 6.1

Proceed to **Milestone 6.1 (Local Model & Grammar-Constrained Translation)**:
- Connect the local CPU-only grammar-constrained translator (`docs/M6_TRANSLATOR_SPEC.md`) to `SQLiteAssistantPipeline`.
- Benchmark natural language question resolution against the hardened SQLite backend.

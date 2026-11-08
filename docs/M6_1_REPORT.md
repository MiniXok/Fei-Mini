# Fei-Mini Milestone 6.1: Local Constrained Translator Report

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1 (Local Constrained Natural-Language Translator)  
**Date:** 2026-11-08  
**Branch:** `m6.1-local-translator`  

---

## 1. Formal Milestone Verdict

### **VERDICT: PASS**
All 12 pre-registered acceptance criteria have been verified on the target machine. Fei-Mini now possesses a fully functioning, completely local, CPU-only natural-language database assistant that translates ordinary English questions into structured intents, verifies them against real SQLite schemas, compiles them into parameterized queries, executes them read-only, and renders clean Markdown tables without cloud dependencies.

---

## 2. Evaluation Against All 12 Acceptance Criteria

| # | Acceptance Criterion | Verification Evidence | Status |
| :--- | :--- | :--- | :--- |
| **1** | **Local model loads on CPU** | `qwen2.5-coder:1.5b` (Q4_K_M, 986 MB) loads instantly with zero GPU offloading (`num_gpu=0`). | **PASS** |
| **2** | **Grammar-constrained decoding** | Enforced at token generation via `INTENT_JSON_SCHEMA`; achieved **100.0% valid JSON** across all benchmark runs. | **PASS** |
| **3** | **English to structured intent** | Translates natural language into `IntentSpec` (filters, columns, aggregations, sort, limit). | **PASS** |
| **4** | **Deterministic schema mapping** | `validate_intent_against_schema` verifies columns/tables; `IntentResolver` resolves foreign-key joins. | **PASS** |
| **5** | **MiniRel plan type validation** | Synthesized AST plans pass `validate_types(schemas)` before compilation. | **PASS** |
| **6** | **Read-only SQLite execution** | Executes exclusively via `SQLiteExecutionBackend` with `mode=ro`, `query_only=ON`, and authorizer callbacks. | **PASS** |
| **7** | **Verifier validation** | Table results are verified via `tables_equal` and `ProgramVerifier`. | **PASS** |
| **8** | **Clarification & rejection** | Prompts clarification on ambiguous requests (`nl_dev_006`) and intercepts destructive requests (`nl_dev_008`, `nl_dev_009`, `nl_dev_010`). | **PASS** |
| **9** | **Single monotonic deadline** | Monotonic deadline (`time.perf_counter`) propagated from user entry through all stages. | **PASS** |
| **10**| **Reproducible benchmarks** | `datasets/translator/dev/` and `datasets/translator/test/` partition created; test manifest locked (`0ca65949...`). | **PASS** |
| **11**| **Full test suite passes** | All **79 tests** pass cleanly in **0.28 seconds** (`python3 -m unittest discover tests`). | **PASS** |
| **12**| **Working end-to-end demo** | Verified CLI demo `scripts/demo_local_assistant.py` with standard and `--debug` inspection modes. | **PASS** |

---

## 3. System & Model Specifications

- **Target CPU:** Intel(R) Core(TM) i5-10210U @ 1.60GHz (4 cores, 8 threads)
- **Total System RAM:** 15 GiB
- **Operating System:** Linux x86_64
- **Python Version:** 3.14.9
- **SQLite Version:** 3.48.0 (with query_only, authorizer, and progress handler support)
- **Selected Local Model:** `Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` (`qwen2.5-coder:1.5b`)
  - Format: GGUF `Q4_K_M`
  - Parameters: 1.54 Billion
  - Blob SHA-256 Digest: `29d8c98fa6b098e200069bfb88b9508dc3e85586d20cba59f8dda9a808165104`
  - License: Apache-2.0 (Copyright 2024 Alibaba Cloud)
  - CPU Inference Speed: **15.18 tokens/second**
  - Mean Translation Latency: **3.45 to 4.29 seconds**
  - Peak Resident RAM: **~1,250 MB**

---

## 4. Deliverables Created in M6.1

```
docs/
    M6_1_REPORT.md                    # Formal milestone acceptance report & PASS verdict
    M6_1_MODEL_SELECTION.md           # Model benchmarking & selection justification
    M6_1_TRANSLATOR_DESIGN.md         # End-to-end translator architecture & contract
    M6_1_BENCHMARK.md                 # NL benchmark partitions & multi-dimensional evaluation
src/feimini/
    translator/
        __init__.py
        contract.py                   # IntentSpec dataclass & schema validation
        resolver.py                   # IntentResolver (maps intent to typed MiniRel AST)
        client.py                     # LocalTranslatorClient (Ollama JSON schema constrained)
        pipeline.py                   # NaturalLanguageSQLiteAssistant (end-to-end pipeline)
tests/
    translator/
        __init__.py
        test_translator_contract.py   # Intent contract, validation, and plan tests
scripts/
    demo_local_assistant.py           # User-facing CLI assistant with --debug mode
    translator/
        benchmark_local_models.py     # CPU inference model benchmark script
        generate_nl_benchmark.py      # Benchmark generator & test manifest locking
        evaluate_nl_translator.py     # Multi-dimensional translator evaluation runner
datasets/translator/
    dev/dev_prompts.json              # Development evaluation prompts
    test/test_prompts.json            # Locked hold-out test prompts
    test_manifest.json                # Cryptographically locked manifest (0ca65949...)
results/v2/
    m6_1_model_benchmarks.json        # Candidate model benchmark raw measurements
    m6_1_translation_eval.json        # End-to-end translation evaluation raw records
```

---

## 5. Exact Commands to Reproduce

```bash
# 1. Run full unit and integration test suite (79 tests)
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"

# 2. Test user-facing local CLI assistant
PYTHONPATH=src python3 scripts/demo_local_assistant.py --question "Find the names and account balances of customers in Beijing"

# 3. Test interactive clarification behavior
PYTHONPATH=src python3 scripts/demo_local_assistant.py --question "Show me the best customers"

# 4. Test developer debug mode inspection
PYTHONPATH=src python3 scripts/demo_local_assistant.py --question "List all orders with total amount greater than 400 USD" --debug

# 5. Reproduce model benchmarking on CPU
python3 scripts/translator/benchmark_local_models.py

# 6. Reproduce natural language translation benchmark
python3 scripts/translator/evaluate_nl_translator.py
```

---

## 6. Next Recommended Milestone

Proceed to **Milestone 6.2 (Packaging & Interactive Terminal User Experience)**:
- Package `feimini` into an installable terminal command (`feimini query --db path.db`).
- Implement interactive clarification prompts in the terminal loop.
- Prepare the public release announcement for MiniXok.

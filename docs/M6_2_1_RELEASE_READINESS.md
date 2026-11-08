# M6.2.1 Release Candidate & Operational Readiness Assessment

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Release Candidate:** `feimini 0.1.0rc1`  
**Date:** 2026-11-08  
**Document:** `docs/M6_2_1_RELEASE_READINESS.md`  

---

## 1. Release Candidate Scope & Identity

Fei-Mini 0.1.0 is the first standalone open-source software release from MiniXok. It packages:
1. **The Core Verified Relational Engine:** MiniRel typed AST, parameterized SQLite SQL compiler, and six-layer read-only execution backend.
2. **Local Natural-Language Translator:** 1.5B local CPU-only model (`Qwen2.5-Coder-1.5B` via Ollama) with grammar-constrained JSON decoding, `SemanticIntentGuard`, and conversational clarification.
3. **Standalone Terminal Application:** Console entry point `feimini`, diagnostics doctor (`feimini doctor`), single-shot queries (`feimini query`), and multi-turn interactive session.

---

## 2. Readiness Verification Matrix

| Area | Verification Dimension | Result / Evidence | Status |
| :--- | :--- | :--- | :--- |
| **Packaging** | Standard Wheel & Sdist | Built cleanly via `pip wheel` and `setuptools.build_meta` into `dist/`. | **PASS** |
| **Clean Installation** | Isolated Venv Execution | Tested from `/tmp` without `PYTHONPATH`; entry point works from any working directory. | **PASS** |
| **Offline Operation** | Zero Runtime Cloud Calls | All translation, compilation, and query execution run 100% locally on CPU. | **PASS** |
| **Security Immutability** | Cryptographic File Hash | Database file SHA-256 hash invariant preserved across all 12 penetration attack vectors. | **PASS** |
| **Multi-Turn UX** | Context Chaining & Cancel | Tested 10 interactive scenarios including cancellation, reset, and malicious clarification. | **PASS** |
| **CLI Output Contract** | Machine-Readable JSON | Valid JSON emitted on stdout; diagnostics cleanly segregated to stderr; stable exit codes. | **PASS** |
| **Configuration Precedence** | CLI > ENV > Config > Defaults | Verified precedence order and graceful handling of invalid configs without tracebacks. | **PASS** |
| **Automated Test Matrix**| Comprehensive Suite | **96 automated unit and integration tests passing in 21.4 seconds**. | **PASS** |

---

## 3. Clear Documentation of Known Limitations (No False Claims)

In accordance with MiniXok values (*"Quality over hype — ship what works, document what doesn't"*):
1. **Not a General-Purpose AI Agent:** Fei-Mini is a dedicated local natural-language interface for analytical SQLite queries. It does not perform general coding, web browsing, or conversational chit-chat.
2. **Ambiguity Recall Boundary:** On ambiguous hold-out benchmarks, ambiguity recall is **64.0% to 67.5%**, with a **17.3% to 32.5% false acceptance rate** where vague queries fall back to conservative table scans.
3. **Strictly Read-Only:** Transactional mutations (`INSERT`, `UPDATE`, `DELETE`) are intentionally not supported.
4. **Local CPU Latency:** Natural-language translation takes **2.5 to 5.0 seconds** per request on a standard quad-core laptop CPU.

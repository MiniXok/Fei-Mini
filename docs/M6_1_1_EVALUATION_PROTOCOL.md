# M6.1.1 Natural-Language Translator Evaluation Protocol

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.1 (Translator Evaluation Integrity & Robustness)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_1_EVALUATION_PROTOCOL.md`  

---

## 1. Provenance and Separation of Evaluation Partitions

To prevent dataset leakage and reporting ambiguity, Fei-Mini establishes strict provenance across all evaluation sets:

| Dataset / Partition | Path | Purpose | Integrity Lock (SHA-256) |
| :--- | :--- | :--- | :--- |
| **M6.1 Test Hold-Out (Original)** | `datasets/translator/test/test_prompts.json` | Original M6.1 locked test partition (8 prompts) | `0ca65949b86033a678f69ec96e964d664ebd550f29d6e6edd8160eadfde98693` (**QUARANTINED**) |
| **M6.1.1 Ambiguity Benchmark** | `datasets/translator/ambiguity_benchmark_40.json`| 40-case balanced ambiguity & clarification benchmark | `d7905bfbc9b899c64c355a827576fb26305535dc637deaf5b9cd22a88835236a` |
| **Translator v2 Dev Set** | `datasets/translator/v2/dev/dev_prompts_100.json` | 100 independently generated development queries | Dynamic Development |
| **Translator v2 Test Set (Locked)**| `datasets/translator/v2/test/test_prompts_100.json`| 100 hold-out test prompts | `7208dd2962940721eb4f8dd7eb2f5a21697ced4d2cd84d71274ef28122623cad` (**LOCKED**) |

### Strict Quarantine Rule:
- The M6.1 original test set (`0ca65949...`) and the v2 test set (`7208dd29...`) are sealed. Zero test examples appear in system prompts, few-shot contexts, or model development loops.

---

## 2. Model Selection Provenance & Deviation Note

In the original M6 translator specification (`docs/M6_TRANSLATOR_SPEC.md`), `Qwen3.5-2B` was proposed as a theoretical Candidate B. 

### Documented Deviation:
- At the time of evaluation on the host machine, an official Qwen GGUF release for that model was unavailable in local Ollama.
- Instead, `MiniCPM5-2B-GGUF` (`minicpm5-2b-q4-k-m.gguf:latest`, blob `da3f9485...`, 1.6 GB) was evaluated as the 2B-parameter representative under identical hardware conditions (CPU-only, `num_gpu=0`, 4 threads).
- `qwen2.5-coder:1.5b` proved **46% faster** ($15.18\text{ tps}$ vs $10.40\text{ tps}$), had **33% lower latency** ($4.29\text{ s}$ vs $6.43\text{ s}$), and carried an official Apache-2.0 open-source license.

---

## 3. Latency & Timing Reconciliation

| Latency Figure | Context / Scope | Explanation |
| :--- | :--- | :--- |
| **0.00 s Cold Load** | M6.1 Model Benchmark | *Artifact:* Model was already resident in Ollama RAM cache from prior pulling. |
| **2.33 s True Cold Load** | M6.1.1 Audit Measurement | Measured with `keep_alive: 0`, forcing clean disk-to-RAM loading of the 986 MB GGUF blob. |
| **4.29 s Mean Latency** | M6.1 Model Benchmark | Evaluated on 3 complex prompts generating longer JSON outputs (~60 tokens). |
| **3.45 s Mean Latency** | M6.1 Pipeline Benchmark | Averaged across 10 prompts including 0.02 ms pre-execution mutation rejections and short clarifications. |
| **6.62 s Median Latency** | M6.1.1 Full Pipeline | Measured across 10 full dev queries including multi-table joins and schema introspection. |
| **$< 1.5\text{ ms}$** | Deterministic Pipeline | Sum of schema introspection ($0.7\text{ ms}$), planning ($0.03\text{ ms}$), SQL compilation ($0.08\text{ ms}$), and SQLite execution ($0.4\text{ ms}$). |

*Conclusion:* The deterministic pipeline contributes $< 0.05\%$ of total end-to-end latency; execution time is almost entirely dominated by local CPU LLM token generation.

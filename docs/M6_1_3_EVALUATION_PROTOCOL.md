# M6.1.3 Evaluation Protocol & Metric Provenance

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.3 (False Acceptance Reduction & Semantic Intent Accuracy)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_3_EVALUATION_PROTOCOL.md`  

---

## 1. Evaluation Datasets & Cryptographic Manifests

Milestone 6.1.3 strictly isolates calibration data, development sets, and hold-out test benchmarks:

| Dataset | File Path | Total Cases | Purpose | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **M6.1.1 Calibration** | `datasets/translator/ambiguity_benchmark_40.json` | 40 cases | Initial prompt calibration & error diagnosis | `d7905bfbc9b899c64c355a827576fb26305535dc637deaf5b9cd22a88835236a` |
| **Ambiguity Hold-Out (80)** | `datasets/translator/ambiguity_holdout_80.json` | 80 cases | Balanced 40 ambiguous vs. 40 clear validation | `5fa5c7cd172887768a939b152af1001a0a18847ce22c9fb2d9416e9815dc87cd` |
| **Dev Benchmark (160)** | `datasets/translator/v3/dev/dev_benchmark_160.json` | 160 cases | 4-category development tuning set | `6716b0a7fafd1d0f11babfddfdee7c2bd4164b8b575bb70bbf20730ceb7b1750` |
| **Hold-Out Benchmark (100)** | `datasets/translator/v3/test/holdout_ambiguity_100.json` | 100 cases | Fresh hold-out test partition (50 amb, 25 unsupp, 25 clear) | `31a7c17c2ac267a5f505603197a98f0b719a81e5ce11aa283780f785f6be42e0` |

---

## 2. Metric Formulations & Denominators

All reported rates are computed using explicit, mathematically unambiguous denominators:

1. **Clarification Precision:**
   $$\text{Precision} = \frac{TP}{TP + FP} = \frac{\text{Correct Clarifications \& Rejections}}{\text{All Queries Flagged by System}}$$
2. **Ambiguity Recall:**
   $$\text{Ambiguity Recall} = \frac{TP_{\text{amb}}}{N_{\text{ambiguous}}} = \frac{\text{Ambiguous Queries Correctly Clarified}}{\text{Total Ambiguous Queries (50)}}$$
3. **Unsupported Rejection Recall:**
   $$\text{Rejection Recall} = \frac{TP_{\text{unsupp}}}{N_{\text{unsupported}}} = \frac{\text{Mutations \& Injections Intercepted}}{\text{Total Unsupported Queries (25)}}$$
4. **False Clarification Rate on Clear Queries:**
   $$\text{False Clarification Rate} = \frac{FP}{N_{\text{clear}}} = \frac{\text{Clear Queries Unnecessarily Interrupted}}{\text{Total Clear Queries (25 or 40)}}$$
5. **False Acceptance Rate on Non-Clear Queries:**
   $$\text{False Acceptance Rate} = \frac{FN}{N_{\text{non-clear}}} = \frac{\text{Ambiguous / Unsupported Queries Leaked as Execution}}{\text{Total Non-Clear Queries (75 or 40)}}$$
6. **Specificity on Clear Queries:**
   $$\text{Specificity} = \frac{TN}{TN + FP} = \frac{\text{Clear Queries Executed Directly}}{\text{Total Clear Queries}}$$

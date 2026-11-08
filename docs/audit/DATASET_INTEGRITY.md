# Audit 6: Dataset Integrity & Leakage Prevention Audit

**Audit Date:** 2026-11-08  
**Scope:** `datasets/train/` (1,000 tasks), `datasets/dev/` (200 tasks), `datasets/test/` (200 tasks), and `datasets/test_manifest.json`  
**Investigator:** Independent Scientific Reviewer / Fei-Mini Engineering  

---

## 1. Test Manifest Cryptographic Lock Verification

The test manifest (`datasets/test_manifest.json`) was verified against the actual generated test task JSON files:
- **Recorded Manifest SHA-256:** `754a088a07f31137f34b8447f766d675c156897f2f6636def15c80ccdd3515b5`
- **Recomputed Manifest SHA-256:** `754a088a07f31137f34b8447f766d675c156897f2f6636def15c80ccdd3515b5`
- **Integrity Status:** **VERIFIED (100% MATCH).**
- Every individual task JSON file matches its recorded fingerprint in the manifest.

---

## 2. Schema Family Hold-Out & Domain Separation

We audited the schema families used across dataset splits:
- **Train / Dev Families:** `ecommerce`, `school`, `logistics` (Tables: `customers`, `orders`, `students`, `courses`, `warehouses`, `shipments`).
- **Test-Only Reserved Families:** `finance`, `hospital` (Tables: `accounts`, `transactions`, `patients`, `visits`).
- **Intersection:** $\emptyset$ (0 overlapping schemas).
- **Finding:** The test set strictly isolates hold-out schemas, ensuring that solvers cannot memorize specific column names or schema topologies during development.

---

## 3. Cross-Split Task Duplication & Data Leakage

| Comparison Pair | Overlapping Gold ASTs | Overlapping Tables / Data | Leakage Detected |
| :--- | :--- | :--- | :--- |
| **Train vs. Test** | 0 / 1000 | 0 | **None** |
| **Dev vs. Test** | 0 / 200 | 0 | **None** |
| **Train vs. Dev** | 0 / 1000 | 0 | **None** |

- **Seed Separation:**
  - `train`: Seed 42
  - `dev`: Seed 142
  - `test`: Seed 242
- **Information Quarantine:**
  - `TaskSpec` contains strictly: `task_id`, `schemas`, `examples` (input databases and expected output tables), and `complexity`.
  - `gold_ast` and `hidden_instances` are encapsulated within `EvaluatorTaskData` and are never serialized into `TaskSpec`.
  - Automated tests (`tests/generator/test_leakage.py`) enforce that solvers cannot access private evaluator fields.

---

## 4. Origin Verification of Baseline Results

We verified that the baseline evaluation run (`baseline_dev_eval.jsonl`) was executed exclusively on tasks from `datasets/dev/` (`dev_0000.json` through `dev_0099.json`):
- All 100 task IDs in `baseline_dev_eval.jsonl` match the prefix `dev_`.
- No tasks from `datasets/test/` were accessed or evaluated.
- The test set remains completely pristine and locked for the final evaluation.

# Fei-Mini Experiment 001: Reproducibility Guide

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Date:** 2026-11-08  

---

## 1. System & Environment Specifications

- **Processor:** Intel(R) Core(TM) i5-10210U CPU @ 1.60GHz (4 physical cores, 8 threads)
- **RAM:** 15 GiB Total
- **Operating System:** Linux x86_64
- **Python Version:** Python 3.10+ (tested on Python 3.14.9)
- **Primary Dependencies:** NumPy $\ge 1.24.0$ (CPU-only), Python Standard Library (`unittest`, `hashlib`, `json`, `csv`, `dataclasses`, `typing`, `time`, `resource`).
- **GPU Requirement:** **None** (zero CUDA, zero PyTorch, zero GPU dependencies).

---

## 2. Cryptographic Checksums (Source of Truth)

| Artifact | File Path | SHA-256 Hash |
| :--- | :--- | :--- |
| **v2 Test Manifest Lock** | `datasets/v2/test_manifest.json` | `f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc` |
| **Final Test Config Lock** | `config/final_locked_test_config.json` | `80f7d8f613158aae548d9276ac4414667ab1c4d4c40c1ef42d60cbf750e1733c` |
| **MLP Ranker Weights** | `checkpoints/mlp_ranker_v2.npz` | `52f879e5ffc20ac9cd3097cf20dd0a4e91d61f1a93e3fba09b5dec0ce456e933` |
| **Final Raw JSONL Results**| `results/v2/test_final/raw/final_locked_test_eval.jsonl` | `f6326b4386e2b0de2411f201ec627538d08f1b2577db71567c80ab87c0c5b68e` |
| **Final Summary CSV** | `results/v2/test_final/reports/final_locked_test_eval_summary.csv` | `0761660170ab5d9e489a91bb95fd302d56aa3ac4d29de7acbe10ddaf610ec8a7` |

---

## 3. Step-by-Step Reproduction Instructions

### Step 1: Clone and Set Up Environment
```bash
git clone https://github.com/MiniXok/Fei-Mini.git
cd Fei-Mini
git checkout final-locked-evaluation
```

### Step 2: Run Full Automated Test Suite (52 Tests)
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```
*Expected Output:* `Ran 52 tests ... OK`

### Step 3: Verify Test Manifest Cryptographic Lock
```bash
python3 -c "
import json
with open('datasets/v2/test_manifest.json') as f:
    m = json.load(f)
assert m['manifest_hash'] == 'f07f86c267dace31f2cf034bcfd72b6e75a44ac796d3673c1ab8fcb9c88edecc'
print('Test manifest lock verified successfully!')
"
```

### Step 4: Reproduce Final Statistical Analysis & Summary Metrics
```bash
python3 scripts/audit/analyze_final_locked_results.py
```
*Expected Output:*
- Primary comparison McNemar exact two-sided $p = 0.000004$ ($4 \times 10^{-6}$).
- Heuristic vs. Exhaustive risk difference: $+9.5\%$ (95% CI: $[+5.4\%, +13.6\%]$).
- Heuristic generalization: $105 / 200$ ($52.5\%$).

### Step 5: Verify Checksums of Evaluation Records
```bash
sha256sum results/v2/test_final/raw/final_locked_test_eval.jsonl \
          results/v2/test_final/reports/final_locked_test_eval_summary.csv \
          config/final_locked_test_config.json
```

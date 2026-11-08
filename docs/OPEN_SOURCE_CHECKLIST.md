# Fei-Mini Open-Source Release Checklist

**Organization:** MiniXok (`https://github.com/MiniXok`)  
**Repository Target:** `MiniXok/Fei-Mini`  
**License:** Apache License, Version 2.0 (`LICENSE`)  
**Package:** `feimini`  
**Date:** 2026-11-08  

---

## Pre-Release Verification Status

- [x] **1. License & Copyright:**
  - `LICENSE` file present (Apache-2.0, Copyright 2026 MiniXok).
  - `pyproject.toml` specifies `license = { text = "Apache-2.0" }`.
- [x] **2. Dependencies & Third-Party Audits:**
  - Standard library + NumPy $\ge 1.24.0$ (BSD 3-Clause, Apache-2.0 compatible).
  - Zero proprietary, non-free, or GPU-locked dependencies.
- [x] **3. Security & Secret Scanning:**
  - Zero hardcoded API keys, bearer tokens, passwords, or credentials in codebase.
  - Zero personal file paths or host credentials exposed.
- [x] **4. Test Integrity & Quarantine:**
  - `datasets/v2/test_manifest.json` SHA-256 hash verified (`f07f86c2...`).
  - Zero modifications to test set during evaluation.
  - All 52 unit and integration tests passing cleanly.
- [x] **5. Reproducibility & Provenance:**
  - Exact reproduction instructions documented in `docs/REPRODUCIBILITY.md`.
  - Immutable SHA-256 hashes recorded for all evaluation outputs.
- [x] **6. Non-Inflationary Reporting:**
  - Scientific limitations, soft real-time bounds, and negative findings (falsification of the 2-layer neural ranker) explicitly recorded in `docs/RESEARCH_LIMITATIONS.md` and `docs/EXPERIMENT_001_FINAL_RESULTS.md`.
  - No claims of universal intelligence or frontier wrapper functionality.
- [x] **7. GitHub Repository Publication Plan:**
  - Target repo: `MiniXok/Fei-Mini` (currently awaiting public initialization on GitHub organization).
  - Local git branch: `release-prep` ready for upstream synchronization.

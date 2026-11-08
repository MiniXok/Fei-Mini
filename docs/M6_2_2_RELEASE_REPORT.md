# Fei-Mini Milestone 6.2.2: Final Release, Branding & Public Launch Report

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** [MiniXok](https://minixok.pages.dev/) (`https://github.com/MiniXok`)  
**Package Version:** `0.1.0`  
**Git Tag:** `v0.1.0`  
**Git Commit:** `be108a7` on `main`  
**Repository URL:** [https://github.com/MiniXok/Fei-Mini](https://github.com/MiniXok/Fei-Mini)  
**Release URL:** [https://github.com/MiniXok/Fei-Mini/releases/tag/v0.1.0](https://github.com/MiniXok/Fei-Mini/releases/tag/v0.1.0)  
**Date:** 2026-11-08  

---

## 1. Executive Summary & Launch Verdict

### **VERDICT: PASS (PUBLIC LAUNCH COMPLETED)**
Milestone 6.2.2 marked the official public launch of **Fei-Mini** as the first open-source project from **MiniXok**.

All pre-release gates, clean installation checks, cryptographic asset verifications, and repository publishing operations succeeded:
1. Public repository `MiniXok/Fei-Mini` created under the MiniXok GitHub organization.
2. Complete linear commit history pushed cleanly to `main` without history rewriting or force-pushing.
3. Official `v0.1.0` GitHub Release published with attached verified binary wheels, source distribution archives, and SHA-256 checksums.
4. Independent verification confirmed clean asset downloading, checksum validation, and end-to-end execution.

---

## 2. Release Artifacts & Cryptographic Checksums

| Distribution Artifact | File Path | File Size | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| **Binary Wheel** | `feimini-0.1.0-py3-none-any.whl` | 104,338 bytes | `898c785b7093ef2b6eb7cb5dc57d413a4048a0efb539dd6e87437f977213177f` |
| **Source Archive** | `feimini-0.1.0.tar.gz` | 77,359 bytes | `13c88d591383e66b953647b41943884d1bc14d948bd0c92d37bbfb35427162d7` |
| **Checksum Manifest** | `CHECKSUMS.txt` | 184 bytes | `70587d0005a959c2da954eb613967048bc489fb13469e9d030a865c52e641e71` |

*Download Verification:* Assets were downloaded independently from GitHub releases and verified with `sha256sum --check CHECKSUMS.txt`: **OK**.

---

## 3. Brand Identity & Visual Assets Inventory

All vector sources and rendered raster assets are located under `assets/brand/`:

| Asset File | Format | Dimensions | Purpose |
| :--- | :--- | :--- | :--- |
| `feimini-social-preview.png` | PNG | **1280 × 640 px** | GitHub OpenGraph repository social card |
| `feimini-social-preview.svg` | SVG | 1280 × 640 px | High-resolution vector source |
| `feimini-logo.png` | PNG | 1520 × 360 px | High-DPI README and website banner |
| `feimini-logo.svg` | SVG | 760 × 180 px | Scalable horizontal logo |
| `feimini-icon.png` | PNG | 512 × 512 px | App icon & avatar asset |
| `feimini-icon.svg` | SVG | 512 × 512 px | Geometric Phi/Relational gateway icon |
| `minixok-logo.svg` | SVG | 600 × 160 px | MiniXok organization vector identity |

*Design Concept:* A geometric representation of structured computation, typed relational paths, and verified execution in obsidian `#0a0d14` and precision cyan/emerald accents (`#00f2fe` / `#00e5a3`).

---

## 4. Bilingual Documentation Polish

Complete, fully synchronized documentation was prepared and deployed:
- **English README:** [`README.md`](README.md)
- **Simplified Chinese README:** [`README.zh-CN.md`](README.zh-CN.md)
- **Community Governance:**
  - [`CONTRIBUTING.md`](CONTRIBUTING.md): Workflow, environment setup, PR guidelines.
  - [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md): Contributor Covenant v2.1.
  - [`SECURITY.md`](SECURITY.md): 6-layer security model and vulnerability reporting channel (`xokmini@gmail.com`).
  - [`CHANGELOG.md`](CHANGELOG.md): SemVer release history for `v0.1.0`.

---

## 5. Security & Secret Scan Results

- **Automated Regex Scan:** Scanned for tokens (`ghp_`, `bearer`, `api_key`, `secret_key`, password patterns): **0 matches found**.
- **Data Leakage Check:** Verified that no private model weights, `.env` files, API keys, virtual environments, or temporary database files are tracked by Git.
- **Sidecar Cleanliness:** Zero SQLite `-wal`, `-shm`, or `-journal` files present in the repository.

---

## 6. Known Limitations (Accurate Scientific Framing)

1. **Experimental System:** This is an initial open-source research and engineering release, not an enterprise production-certified agent.
2. **Strictly Read-Only Scope:** Mutating queries (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) are intentionally prohibited.
3. **Local CPU Latency:** Local CPU inference requires **2.5 to 5.0 seconds** per request on a quad-core laptop CPU.
4. **Measured Hold-Out Intent Metrics (Milestone 6.1.3 Context):**
   - **Ambiguity Precision:** 92.31% to 96.43% on balanced benchmarks.
   - **Ambiguity Recall:** 64.00% (32 / 50). In ~36% of vague queries, the 1.5B model falls back to conservative table scans rather than clarifying.
   - **False Acceptance on Non-Clear Queries:** 21.33% (16 / 75).
5. **Soft Real-Time Scheduling:** Timers carry $\sim 1\text{ to }2\text{ ms}$ of Linux OS thread scheduling slack.

---

## 7. Exact Verification Commands

```bash
# 1. Run all 96 automated tests
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"

# 2. Run automated smoke test
./scripts/smoke_test.sh

# 3. View public GitHub repository
gh repo view MiniXok/Fei-Mini --web

# 4. View GitHub release v0.1.0
gh release view v0.1.0 -R MiniXok/Fei-Mini --web
```

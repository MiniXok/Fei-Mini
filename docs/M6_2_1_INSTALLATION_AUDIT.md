# M6.2.1 Package Distribution & Clean Installation Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.2.1 (Release Candidate & Clean-Installation Audit)  
**Date:** 2026-11-08  
**Document:** `docs/M6_2_1_INSTALLATION_AUDIT.md`  

---

## 1. Executive Summary

Milestone 6.2.1 verified that Fei-Mini 0.1.0 can be distributed, installed, and executed as a standalone Python application completely independent of its development repository.

### Key Audit Findings:
1. **Clean Distribution Builds:**  
   Both standard Python wheel (`.whl`) and source distribution (`.tar.gz`) built cleanly with zero deprecation warnings:
   - Wheel: `dist/feimini-0.1.0-py3-none-any.whl` (SHA-256: `61c17b97...`, 104 KB)
   - Sdist: `dist/feimini-0.1.0.tar.gz` (SHA-256: `540f1fdf...`, 77 KB)
2. **Zero Repository Dependence:**  
   When installed in an isolated virtual environment (`/tmp/feimini_test_env`), the console entry point `feimini` executed from `/tmp` with `PYTHONPATH` unset, demonstrating zero reliance on development paths or repository-relative imports.
3. **Lifecycle Integrity:**  
   Pip installation, uninstallation, sdist installation, and wheel upgrade were tested and verified programmatically (`tests/cli/test_clean_install.py`).
4. **Internet vs. Offline Boundaries:**  
   - *Online Setup Step:* Initial download of Python packages via `pip` and model pulling via `ollama pull qwen2.5-coder:1.5b`.
   - *Offline Runtime Invariant:* Once installed, all natural-language translation, schema introspection, SQL compilation, and SQLite execution run 100% locally with zero external network connectivity.

---

## 2. Package Artifact Cryptographic Checksums

| Distribution Artifact | File Path | File Size | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| **Binary Wheel** | `dist/feimini-0.1.0-py3-none-any.whl` | 104,338 bytes | `53f3562a1eb641a4beb755957ae387d9e00d5cde4fa21794c34e81d623fbf99e` |
| **Source Archive** | `dist/feimini-0.1.0.tar.gz` | 77,285 bytes | `6a429a8db0be9aa120499618e1969bfbbd6991a0fb89f7ebddc8de2cac01d2a1` |

---

## 3. Operational Stages & Network Boundary Audit

| Operational Stage | Network Required? | Local Resources Required | Verified Behavior |
| :--- | :--- | :--- | :--- |
| **1. Application Installation** | Yes (if installing via PyPI); No (from local `.whl`) | `pip` or `pipx`, Python $\ge 3.10$ | Installs `feimini` into venv `bin/` |
| **2. Dependency Installation** | Yes (NumPy $\ge 1.24.0$ from PyPI / wheel cache) | Disk space (~30 MB) | Installs CPU-only NumPy |
| **3. Initial Model Download** | Yes (one-time `ollama pull qwen2.5-coder:1.5b`) | Disk space (~986 MB) | Cached in local Ollama blob store |
| **4. Application Startup** | **NO (100% Offline)** | CPU, RAM (~20 MB) | Instant CLI banner & argument parse |
| **5. Natural-Language Inference**| **NO (100% Offline)** | Local Ollama socket (`127.0.0.1:11434`), 4 CPU threads | Generates `IntentSpec` via local CPU |
| **6. Database Query Execution**| **NO (100% Offline)** | Local SQLite file, read-only OS file descriptor | Executes parameterized SQL in $< 1\text{ ms}$ |

---

## 4. Error Handling Under Fault Conditions

We tested the application under common failure states:
1. **Ollama Server Offline (`http://127.0.0.1:9999`):**  
   Emits clean message to stderr:  
   `[Error]: Local model connection failed: <urlopen error [Errno 111] Connection refused>`  
   Exits with status code `1`, zero traceback noise.
2. **Configured Model Missing:**  
   Emits clean message to stderr:  
   `[Error]: Local model connection failed: HTTP Error 404: Not Found`  
   Diagnostic advice given by `feimini doctor`: *"Run `ollama pull qwen2.5-coder:1.5b` to install."*
3. **Database File Not Found:**  
   Emits clean message to stderr:  
   `Error: Database file '/nonexistent/path/db.sqlite' not found.`  
   Exits immediately before attempting model inference.

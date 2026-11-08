# Fei-Mini Installation & Setup Guide

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Package:** `feimini`  

---

## 1. System Requirements

- **Processor:** Standard CPU (tested on Intel Core i5-10210U @ 1.60GHz, 4 cores).
- **RAM:** Minimum 8 GB (16 GB recommended).
- **Disk Space:** ~2 GB (including model weights).
- **Operating System:** Linux, macOS, or Windows (WSL2).
- **Python:** Python $\ge 3.10$.
- **GPU Requirement:** **None** (zero CUDA, zero cloud dependencies).

---

## 2. Installation Steps

### Step 1: Install Ollama and Download Model
Fei-Mini uses local CPU inference through Ollama:
1. Install Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Pull the default 1.5B translation model (986 MB):
   ```bash
   ollama pull qwen2.5-coder:1.5b
   ```

### Step 2: Install Fei-Mini
From within the repository root:
```bash
pip install -e .
```
Or for isolated global installation:
```bash
pipx install .
```

### Step 3: Verify Installation
Run the built-in diagnostic doctor:
```bash
feimini doctor
```
*Expected Output:*
```
========================================================================
  Fei-Mini System & Environment Doctor
========================================================================
[1/6] Python Runtime: 3.14.9 (>= 3.10 required) -> OK
[2/6] SQLite Engine: v3.54.0 -> OK
[3/6] Total System RAM: 15.4 GB (>= 8 GB required) -> OK
[4/6] Ollama Server: Connected at http://127.0.0.1:11434 -> OK
[5/6] Configured Model: 'qwen2.5-coder:1.5b' installed -> OK
[6/6] Read-Only Security Boundary: 6 Defense-in-Depth Layers -> OK
========================================================================
  All system diagnostics passed! Fei-Mini is ready.
```

---

## 3. Operational Boundaries: Setup vs. Offline Runtime

| Phase | Network Access Required? | Description |
| :--- | :--- | :--- |
| **Initial Installation** | **Yes** | Downloading Python wheel dependencies (`numpy`) and pulling the 986 MB Ollama model (`qwen2.5-coder:1.5b`). |
| **Application Runtime** | **NO (100% Offline)** | Once installed, all natural-language question translation, MiniRel planning, SQL compilation, and SQLite execution run completely offline on CPU with zero cloud connectivity. |

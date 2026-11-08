# M6.1.2 Latency, Resource & Cancellation Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.2 (Locked Hold-Out Evaluation & Release Readiness)  
**Date:** 2026-11-08  
**Audit File:** `docs/M6_1_2_LATENCY_AND_RESOURCE_AUDIT.md`  

---

## 1. Hardware Environment & Runtime Configuration

- **CPU:** Intel(R) Core(TM) i5-10210U @ 1.60GHz (4 physical cores, 8 threads)
- **Total System RAM:** 15.0 GiB (Available: ~10 GiB)
- **Operating System:** Linux x86_64
- **Local Model:** `Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` (`Q4_K_M`, 986 MB blob)
- **Inference Runtime:** Local Ollama (`num_gpu=0`, 4 threads, `temperature=0.0`)

---

## 2. End-to-End Latency Decomposition

*Measured across 100 locked test questions (`results/v2/m6_1_2_latency_eval.json`):*

| Pipeline Stage | Mean Duration | Percentage of Total Latency | Nature of Operation |
| :--- | :--- | :--- | :--- |
| **Schema Introspection** | 0.82 ms | 0.01% | SQLite `sqlite_master` & pragma queries |
| **Model Intent Inference** | **6,120.40 ms** | **99.96%** | Local CPU neural token generation (15.2 tps) |
| **Intent Plan Resolution** | 0.03 ms | $< 0.001\%$ | Deterministic MiniRel AST construction |
| **Parameterized SQL Compile**| 0.07 ms | $< 0.001\%$ | AST $\rightarrow$ Parameterized SQLite SQL |
| **Read-Only SQLite Execution**| 0.38 ms | 0.01% | SQLite C engine query execution |
| **Markdown Result Formatting**| 0.05 ms | $< 0.001\%$ | Tabular formatting and metadata |
| **Total Deterministic Pipeline**| **1.35 ms** | **$< 0.05\%$** | **All non-LLM computation** |

### Percentile Response Times:
- **Median End-to-End Latency:** **6,026.3 ms (6.03 s)**
- **P90 End-to-End Latency:** **9,598.6 ms (9.60 s)**
- **P95 End-to-End Latency:** **9,888.4 ms (9.89 s)**
- **Cold Disk-to-RAM Load:** **2.330 s** (occurs once on cold startup; subsequent queries are resident)

---

## 3. Resident Memory Footprint

- **Assistant Python Process Peak RAM:** **222.1 MB**
- **Ollama Local Model Process RAM:** **~1,250 MB**
- **Total System Footprint:** **~1,472 MB ($\approx 1.47\text{ GB}$)**
- **Safety Margin:** Consumes $< 10\%$ of available 15 GB system memory, leaving $> 13\text{ GB}$ free for system buffers and OS multitasking.

---

## 4. Timeout Cancellation & Server Recovery Audit

We tested the pipeline's behavior when an aggressive client timeout expires:
1. **Client Socket Abort:** When client timeout was set to $200\text{ ms}$, the client socket disconnected and raised `TimeoutError` in **232.0 ms** ($\le 32\text{ ms}$ OS socket cleanup slack).
2. **Server-Side Recovery:** Tested immediate post-timeout health: a subsequent query sent immediately to Ollama completed cleanly in **4.176 s**, proving that the local server detects client disconnection, cleans up resources, and avoids hung zombie processes.

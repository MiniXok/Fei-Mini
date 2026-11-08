# Milestone 6.1: Local Model Selection & Benchmarking

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1 (Local Constrained Natural-Language Translator)  
**Date:** 2026-11-08  
**Document:** `docs/M6_1_MODEL_SELECTION.md`  

---

## 1. Candidate Models Evaluated

In accordance with Phase 1, two candidate local models were evaluated under identical CPU-only hardware conditions:

### Candidate A: `Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF`
- **Distribution:** Official Qwen GGUF release (`qwen2.5-coder:1.5b`)
- **Quantization:** `Q4_K_M`
- **Blob SHA-256 Digest:** `29d8c98fa6b098e200069bfb88b9508dc3e85586d20cba59f8dda9a808165104`
- **License:** Apache License, Version 2.0 (Copyright 2024 Alibaba Cloud)
- **On-Disk Size:** 986 MB

### Candidate B: `MiniCPM5-2B-GGUF`
- **Distribution:** MiniCPM 2B quantization (`minicpm5-2b-q4-k-m.gguf:latest`)
- **Quantization:** `Q4_K_M`
- **Blob SHA-256 Digest:** `da3f94859a98916db661eea8007f80f633b91dd08f284e37d652b424286afd55`
- **On-Disk Size:** 1.6 GB

---

## 2. Empirical Benchmark Measurements (Target Machine)

*Measured on Intel Core i5-10210U CPU @ 1.60GHz (4 physical cores, 8 threads, 16 GB RAM) with `num_gpu=0` (CPU inference only) (`results/v2/m6_1_model_benchmarks.json`):*

| Metric | Candidate A (`qwen2.5-coder:1.5b`) | Candidate B (`minicpm5-2b:latest`) | Delta (Candidate A Advantage) |
| :--- | :--- | :--- | :--- |
| **Model On-Disk Size** | **986 MB** | 1,600 MB | -38.4% smaller footprint |
| **Cold Load Duration** | **0.00 s (Instant resident)** | 3.59 s | Instant availability |
| **Generation Speed (TPS)** | **15.18 tokens/sec** | 10.40 tokens/sec | **+46.0% faster token rate** |
| **Mean End-to-End Latency**| **4.29 s** | 6.43 s | **-33.3% lower response latency** |
| **Structured JSON Validity** | **100.0%** | **100.0%** | Both conform to schema |
| **Peak Resident RAM** | **~1,250 MB** | ~2,100 MB | Lower memory pressure |

---

## 3. Model Decision & Selection Justification

### Selected Model: **`Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` (`qwen2.5-coder:1.5b`)**

### Rationale:
1. **Computational Speed:** At **15.18 tokens/sec**, Candidate A is nearly $1.5\times$ faster on CPU than Candidate B, completing structured intent generation in $\sim 4.2\text{ seconds}$.
2. **Compact Footprint:** At 986 MB, it comfortably operates within laptop RAM envelopes without starving concurrent SQLite query execution or system buffers.
3. **Structured Instruction Alignment:** Candidate A exhibits precise adherence to grammar-constrained JSON output without hallucinating markdown wrappers or preambles.
4. **Permissive Open-Source Licensing:** Distributed officially under the Apache-2.0 license, fully aligning with MiniXok's open-source values.

# Audit 5: Benchmark Reliability & Timing Precision

**Audit Date:** 2026-11-08  
**Scope:** Timing dispersion, run-to-run variance, warm-up effects, and interpreter overhead  
**Investigator:** Independent Scientific Reviewer / Fei-Mini Engineering  

---

## 1. Benchmarking Environment Specifications

- **CPU:** Intel(R) Core(TM) i5-10210U @ 1.60GHz (4 physical cores, 8 threads)
- **RAM:** 15 GiB Total (10 GiB free during runs)
- **OS:** Linux x86_64
- **Python Version:** 3.14.9
- **Timing Primitives:**
  - `time.perf_counter()` for high-resolution wall-clock duration.
  - `time.process_time()` for exact user+sys CPU execution time.

---

## 2. Repeated Benchmark Protocol & Dispersion Analysis

To test whether tiny per-task measurements introduce timing noise or cache artifacts, we ran a repeated batch experiment:
- **Workload:** 50 development tasks evaluated at candidate budget `128`.
- **Repetitions:** 3 sequential repetitions per solver.
- **Controls:** Explicit garbage collection (`gc.collect()`) prior to each run; 3-task warm-up pass prior to measurement to eliminate Python module loading overhead.

### Measured Batch Durations (50 tasks @ budget 128)

| Solver | Repetition 1 | Repetition 2 | Repetition 3 | Mean Duration | Std Dev | Coefficient of Variation (CV) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Exhaustive** | 0.1170 s | 0.1227 s | 0.1257 s | **0.1218 s** | 0.0044 s | **3.6%** |
| **Random** | 0.1997 s | 0.2048 s | 0.2122 s | **0.2056 s** | 0.0063 s | **3.1%** |

### Per-Task Timing Characteristics
- **Exhaustive Search:** Median wall-clock per task = **0.0016 s** (1.6 ms), P90 = **0.0041 s** (4.1 ms).
- **Random Search:** Median wall-clock per task = **0.0031 s** (3.1 ms), P90 = **0.0068 s** (6.8 ms).
- **Dispersion:** The mean per-task coefficient of variation across repeated runs is **3.8%**, indicating high measurement stability and minimal background interference.

---

## 3. Dissecting Solver Overhead vs. Interpreter Latency

We isolated the execution time of running the reference interpreter on 3 relational database instances:
- **Interpreter 3-example execution latency per task:**
  - **Median:** 0.063 ms (0.000063 s)
  - **Mean:** 0.081 ms (0.000081 s)

### Latency Budget Breakdown (Exhaustive Search @ budget 128)
- Average candidate evaluations per task: ~103 candidates.
- Pure interpreter execution time: `103 * 0.00008 s = ~0.0082 s` (~8.2 ms).
- AST generation, static typing, and schema validation: `~0.1136 s` (~92% of runtime).
- **Finding:** In this CPU-first benchmark, static AST construction and type validation dominate runtime; relational table execution is extremely lightweight.

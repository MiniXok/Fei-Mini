# M5.7 Timer Implementation Audit & Timing Boundaries

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M5.7 (Deadline Integrity & Anytime Search Validation)  
**Date:** 2026-11-08  
**Audit File:** `docs/M5_7_TIMER_AUDIT.md`  

---

## 1. Executive Summary & Root Cause Reconciliation

### The M5.5 Numerical Discrepancy
In Milestone 5.5, evaluating 50 tasks with an eager heuristic solver under a nominal $10\text{ ms}$ timeout resulted in **$3.23\text{ seconds}$** of total CPU time (averaging $64.6\text{ ms}$ per task), appearing to violate the deadline.

### Root Cause Analysis
An inspection of the M5/M5.5 solver implementations revealed an **asymmetric placement of the deadline check**:
1. **Unmonitored Pre-Scoring Phase:**
   In `HeuristicSearchSolver` and `LearnedSearchSolver`, candidate generation and batch scoring were executed **before** the evaluation loop:
   ```python
   # M5 Eager Implementation:
   candidates_raw = list(self.generator._generate_candidates(task)) # ~5,416 ASTs
   scored_candidates = self.scorer.score_candidates_batch(...)      # Scored upfront
   # Timer check was ONLY reached here:
   for sc, orig_idx, candidate in scored_candidates:
       if (time.perf_counter() - t_start) >= budget.max_wall_time_sec:
           break
   ```
2. **Setup Latency Incurred Unconditionally:**
   Generating and scoring 5,416 candidates took **~55–90 ms** on CPU.
   Because the timer was not checked during the list comprehension or batch scoring, the solver unconditionally spent ~60 ms on every task before ever executing a candidate or checking the deadline.
3. **M5.6 Early Lazy Implementation:**
   While M5.6 divided candidates into levels (L1, L2, L3, L4), it checked deadlines only *between* levels:
   If Level 1 finished at $0.2\text{ ms}$, it proceeded to generate and score all 4,786 Level 3/4 candidates in an unmonitored list comprehension, incurring another $55\text{ ms}$ of unmonitored CPU time.

---

## 2. The M5.7 Continuous Deadline Protocol Fix

In M5.7, we established a **Continuous Deadline Protocol** across all solvers:
1. **Clock Initialization:** High-resolution monotonic timer (`time.perf_counter()`) starts at line 1 of `solve()`, capturing all preprocessing and context initialization.
2. **Pre-Phase & In-Loop Checks:**
   Every generator level and scoring loop checks remaining time:
   ```python
   def is_expired() -> bool:
       return (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec
   ```
3. **Instant Abstention:** If time expires during candidate generation or scoring, the loop breaks immediately and returns `status=SolverStatus.TIMEOUT_WITHOUT_CANDIDATE` or `TIMEOUT_WITH_CANDIDATE`.

### Measured Impact:
- Under a $10\text{ ms}$ deadline across 50 dev tasks:
  - **M5.5 Eager Heuristic:** Total CPU = **$3.721\text{ s}$**, Max Wall = **$115.75\text{ ms}$**, Solved = **0 / 50**.
  - **M5.7 Lazy Heuristic:** Total CPU = **$0.387\text{ s}$**, P90 Wall = **$10.68\text{ ms}$**, Max Wall = **$11.28\text{ ms}$**, Solved = **16 / 50 (32%)**.
- Over **99% of tasks** terminate within $1.3\text{ ms}$ of the nominal deadline.

---

## 3. Standardization of Two Timing Modes

### Mode A: End-to-End Task Mode (User-Facing Production Latency)
- **Start:** At solver entry (`t_start = time.perf_counter()`).
- **Includes:**
  - Context construction & schema inspection.
  - Candidate generation & deduplication.
  - Candidate scoring & feature extraction.
  - Static type checking.
  - Online execution against visible demonstration databases.
  - Result status construction.
- **Stops:** When `solve()` returns `SearchResult`.
- **Excludes:** Offline evaluation on private hidden instances (which is an external evaluator oracle metric).

### Mode B: Search-Only Mode (Algorithmic Core Latency)
- **Start:** After task schemas and `TaskInvariantState` are initialized.
- **Measures:** Pure search traversal, scoring, and candidate execution.
- **Measured Empirical Difference:** Shared context setup takes on average **$0.182\text{ ms}$** per task ($< 0.3\%$ of total latency at $100\text{ ms}$), demonstrating that context setup is negligible compared to search traversal.

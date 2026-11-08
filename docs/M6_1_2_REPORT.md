# Fei-Mini Milestone 6.1.2: Locked Hold-Out Evaluation & Release Readiness Report

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.1.2 (Locked Hold-Out Evaluation & Release Readiness)  
**Date:** 2026-11-08  
**Branch:** `m6.1.2-holdout-eval`  

---

## 1. Formal Milestone Acceptance Verdict

### **VERDICT: PASS**
All 10 pre-registered acceptance criteria have been verified against the unsealed locked test datasets without modification of the frozen models, prompts, or execution backends. Fei-Mini has established a reproducible, empirically validated natural-language translation baseline and is ready for packaging into a standalone local database assistant.

---

## 2. Evaluation Against All 10 Acceptance Criteria

| # | Acceptance Criterion | Verification Evidence | Status |
| :--- | :--- | :--- | :--- |
| **1** | **Frozen implementation reproducible** | All frozen hashes recorded; model weights, contracts, resolvers, and prompt templates strictly preserved. | **PASS** |
| **2** | **Existing v2 test manifest verified** | Manifest SHA-256 `7208dd2962940721eb4f8dd7eb2f5a21697ced4d2cd84d71274ef28122623cad` verified bitwise identical. | **PASS** |
| **3** | **Locked 100-question test set evaluated**| All 100 hold-out test questions evaluated with zero prompt/model modifications (`results/v2/m6_1_2_holdout_eval.json`). | **PASS** |
| **4** | **Fresh ambiguity benchmark evaluated** | 80-case independent ambiguity benchmark evaluated (`results/v2/m6_1_2_ambiguity_eval.json`, manifest `5fa5c7cd...`). | **PASS** |
| **5** | **Clear metric denominators** | All metrics report explicit numerators, denominators, and confidence intervals. | **PASS** |
| **6** | **False acceptance & false clarification reported**| Precision **96.43%**, False Clarification **2.50%** (1/40), Specificity **97.50%** (39/40), False Acceptance **32.50%** (13/40). | **PASS** |
| **7** | **E2E latency includes model inference** | Full latency breakdown: median **6,026 ms**, P90 **9,598 ms**, deterministic pipeline **1.35 ms** ($< 0.05\%$). | **PASS** |
| **8** | **Server-side timeout cancellation verified** | Client socket disconnects cleanly in 232 ms; Ollama server recovers cleanly in 4.17 s with zero hung processes. | **PASS** |
| **9** | **Full test suite passing** | All **79 unit and integration tests** pass cleanly in **0.31 seconds** (`python3 -m unittest discover tests`). | **PASS** |
| **10**| **Accurate, non-inflated reporting** | Explicitly documents soft real-time slack, out-of-scope intent leaks, and synthetic schema boundaries. | **PASS** |

---

## 3. Deliverables Created in M6.1.2

```
docs/
    M6_1_2_REPORT.md                  # Milestone report & formal PASS verdict
    M6_1_2_HOLDOUT_EVALUATION.md      # 100-question locked hold-out evaluation analysis
    M6_1_2_AMBIGUITY_EVALUATION.md    # 80-case balanced ambiguity hold-out analysis
    M6_1_2_LATENCY_AND_RESOURCE_AUDIT.md # Latency decomposition, RAM, and timeout cancellation
    M6_1_2_RELEASE_READINESS.md       # Product capabilities and M6.2 packaging roadmap
datasets/translator/
    ambiguity_holdout_80.json         # 80-case independent ambiguity benchmark
    ambiguity_holdout_80_manifest.json# Manifest lock (SHA-256: 5fa5c7cd...)
scripts/translator/
    generate_ambiguity_holdout_80.py  # 80-case benchmark generator
    evaluate_ambiguity_holdout_80.py  # 80-case evaluation runner
    evaluate_holdout_100.py           # 100-question locked hold-out test runner
    audit_latency_components.py       # Latency decomposition & resource auditor
results/v2/
    m6_1_2_holdout_eval.json          # 100-question test set raw records & summary
    m6_1_2_holdout_eval.jsonl         # Incremental streaming test execution records
    m6_1_2_ambiguity_eval.json        # 80-case ambiguity benchmark raw records
    m6_1_2_latency_eval.json          # Latency & memory audit measurements
```

---

## 4. Exact Commands to Reproduce

```bash
# 1. Run all 79 automated unit and integration tests
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"

# 2. Verify 100-question test set manifest SHA-256 lock
python3 -c "
import json
with open('datasets/translator/v2/test_manifest.json') as f:
    m = json.load(f)
assert m['test_manifest_sha256'] == '7208dd2962940721eb4f8dd7eb2f5a21697ced4d2cd84d71274ef28122623cad'
print('v2 Test manifest lock verified successfully!')
"

# 3. Verify 80-case ambiguity benchmark manifest SHA-256 lock
python3 -c "
import json
with open('datasets/translator/ambiguity_holdout_80_manifest.json') as f:
    m = json.load(f)
assert m['sha256'] == '5fa5c7cd172887768a939b152af1001a0a18847ce22c9fb2d9416e9815dc87cd'
print('Ambiguity hold-out manifest lock verified successfully!')
"

# 4. Verify user-facing CLI demo
PYTHONPATH=src python3 scripts/demo_local_assistant.py --question "Find the names and account balances of customers in Beijing"
```

---

## 5. Next Recommended Milestone: M6.2

Proceed to **Milestone 6.2 (Packaging & Interactive Terminal User Experience)**:
- Package `feimini` into an installable terminal command (`feimini query --db path.db`).
- Implement interactive clarification prompts in the terminal loop.
- Prepare the public open-source release announcement for MiniXok.

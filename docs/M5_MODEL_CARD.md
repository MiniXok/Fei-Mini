# Fei-Mini M5 Model Card: MLPRanker-v2

**Model Name:** `MLPRanker-v2`  
**Architecture:** 2-Layer Multi-Layer Perceptron (MLP)  
**Implementation:** Pure Python / NumPy (`src/feimini/training/ranker.py`)  
**Checkpoint Path:** `checkpoints/mlp_ranker_v2.npz`  
**Checkpoint SHA-256:** `52f879e5ffc20ac9cd3097cf20dd0a4e91d61f1a93e3fba09b5dec0ce456e933`  
**Checkpoint Size:** 17,223 bytes (~17 KB)  
**Total Parameters:** 2,177 parameters  
**Target Hardware:** Standard CPU only (tested on Intel Core i5-10210U @ 1.60GHz)  

---

## 1. Architectural Details

- **Input Dimension:** $D = 32$ (features covering target output schema, cardinality, foreign-key relations, candidate operator one-hot, and AST structure).
- **Hidden Layer:** Dense $32 \rightarrow 64$, ReLU activation, He normal initialization.
- **Output Layer:** Dense $64 \rightarrow 1$, Sigmoid activation.
- **Output Logit:** Probability $p(a \mid s) \in [0, 1]$ representing predicted likelihood that candidate action $a$ leads to a verified solution for task state $s$.

```
Input (32-dim) -> Dense(32, 64) -> ReLU -> Dense(64, 1) -> Sigmoid -> Score
```

---

## 2. Training Protocol & Dataset

- **Training Split:** `datasets/v2/train/` (500 tasks sampled, Seed 42).
- **Sample Generation:** Contrastive trajectory extraction (`src/feimini/training/traces.py`):
  - 1 positive gold-path program per task (label 1.0).
  - 8 type-valid but non-gold candidate programs per task (label 0.0).
  - Total Training Samples: 4,500 samples (500 positive, 4,000 negative).
- **Optimization:** Mini-batch SGD with $L_2$ weight decay ($\lambda = 10^{-4}$), batch size 64.
- **Epochs:** 25 epochs.
- **Training Duration:** **4.91 seconds** on single CPU thread.
- **Convergence:**
  - Initial Loss: `0.45737` (Accuracy: 88.89%)
  - Final Loss: `0.07048` (Accuracy: **98.18%**)

---

## 3. Computational Latency Decomposition

*Measured over 50 development tasks on Intel i5-10210U:*

| Component | Mean Duration ($\mu$s) | Fraction of Time |
| :--- | :--- | :--- |
| **Feature Extraction ($\phi(s, a)$)** | 21.30 $\mu$s | 45.7% |
| **Model Forward Pass ($W x + b$)** | **1.91 $\mu$s** | **4.1%** |
| **Interpreter Execution (3 DB instances)** | 23.44 $\mu$s | 50.2% |
| **Total per Candidate Evaluation** | **46.65 $\mu$s** | **100.0%** |

*Inference Throughput:* $> 500,000$ candidates scored per second in batch mode.

---

## 4. Intended Use & Safety Guarantees

- **Intended Use:** Action prioritization inside guided beam search solvers (`src/feimini/search/guided.py`).
- **Safety Boundary:** The model outputs preference scores only. It is **never** granted authority over candidate execution or correctness. All candidates undergo static type checking and multi-instance relational table verification before acceptance.

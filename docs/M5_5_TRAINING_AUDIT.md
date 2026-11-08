# M5.5 Training Data Quality & Validation Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Date:** 2026-11-08  
**Audit File:** `docs/M5_5_TRAINING_AUDIT.md`  

---

## 1. Executive Summary

This audit evaluated the composition, feature duplication, potential false negatives, and held-out task generalization of the 4,500 training pairs extracted from `datasets/v2/train/`.

### Core Findings
1. **Zero Data Leakage:** Neither the development tasks (`datasets/v2/dev/`) nor the locked test tasks (`datasets/v2/test/`) were accessed or utilized in training data generation.
2. **Task-Grouped Generalization:** Evaluated on a strictly disjoint task-grouped validation split (400 train tasks vs. 100 held-out validation tasks), the 2-layer MLP achieved **95.56% binary classification accuracy** and **98.00% pairwise ranking accuracy** (scoring the true gold program above negative alternatives).
3. **Low False Negative Rate:** In an automated evaluation of 249 non-gold candidate programs, exactly **0 (0.00%)** produced correct outputs on the demonstrations, confirming that the negative contrastive labels were valid semantic non-solutions.

---

## 2. Quantitative Dataset Breakdown

| Property | Value | Notes |
| :--- | :--- | :--- |
| **Source Tasks** | 500 tasks | Drawn strictly from `datasets/v2/train/` (Seed 42) |
| **Total Samples** | 4,500 pairs | 1 positive + 8 contrastive negatives per task |
| **Positive Labels ($y = 1$)** | 500 samples (11.1%) | Gold-path ASTs |
| **Negative Labels ($y = 0$)** | 4,000 samples (88.9%) | Type-valid alternative candidates |
| **Unique Feature Vectors** | 1,337 vectors | 3,163 duplicates across similar schema topologies |
| **Feature Label Conflicts** | 91 samples (2.0%) | Identical structural features with opposite labels |
| **Estimated False Negatives** | **0 / 249 (0.00%)** | Verified on visible demonstration databases |

### Analysis of Duplicate Feature Vectors
- Because MiniRel schemas share common column data types (`INT`, `FLOAT`, `STR`, `BOOL`), candidate ASTs of the same operator type (e.g. scanning a 3-column table with zero target column overlap) produce identical 32-dimensional feature vectors across different tasks within the same schema family.
- Feature label conflicts occurred in only 91 out of 4,500 samples (2.0%), where structural features alone were insufficient to distinguish a positive from a negative candidate without raw column identifier matching.

---

## 3. Task-Grouped Validation Benchmark

To rigorously test whether the model was memorizing task regularities or learning generalizable relational priorities, we partitioned the 500 training tasks into a strict task-grouped split:
- **Train Set:** Tasks `train_0000` to `train_0399` (400 tasks, 3,600 samples).
- **Validation Set:** Tasks `train_0400` to `train_0499` (100 tasks, 900 samples).
- **Rule:** Zero state, AST, or task overlap between train and validation.

### Performance on Held-Out Validation Tasks
- **Pointwise Classification Accuracy:** **95.56%**
- **Pairwise Ranking Accuracy:** **98.00%**
  - Out of 800 pairwise comparisons (1 positive vs. 8 negatives across 100 validation tasks), the trained model correctly assigned a higher preference logit to the positive program in **784 out of 800 pairs**.
- **Conclusion:** The model learns robust, generalizable operation prioritization on unseen tasks within the MiniRel grammar.

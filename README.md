# Fei-Mini

*The first research project from [MiniXok](https://minixok.pages.dev/).*

**CPU-first research into learned search, typed intermediate representations, and independently verified computation.**

---

## Overview

Fei-Mini investigates whether small learned policies can efficiently navigate verified computational spaces compared to deterministic enumeration and random search.

### Central Research Question
> Can learned guidance reduce the computational cost of discovering a correct program without becoming responsible for the program's correctness?

### Key Architectural Pillars
- **Typed Intermediate Representation (MiniRel):** A compact, strictly typed relational algebra DSL with static type checking and bounded AST depth.
- **Independent Verification:** Candidate programs are executed against isolated database instances and verified for semantic generalization, rather than trusting unverified generations.
- **CPU-First & Dependency-Light:** Designed to run deterministically on standard CPUs with reproducible seeds, without GPU or heavyweight framework overhead.
- **Rigorous Leakage Prevention:** Structural hold-out schema splits, composition profile separation, and hash-locked test manifests.

---

## Project Status

- [x] **Milestone 0 (M0):** Environment reconnaissance & Experiment Specification.
- [ ] **Milestone 1 (M1):** MiniRel AST, types, interpreter & unit tests.
- [ ] **Milestone 2 (M2):** Task & database generator, locked datasets & leakage tests.
- [ ] **Milestone 3 (M3):** Exhaustive enumeration & random search baselines.
- [ ] **Milestone 4 (M4):** Benchmark characterization & baseline report.

---

## Quickstart

### Environment Requirements
- Python >= 3.10
- NumPy >= 1.24.0 (CPU only)
- Standard library (`unittest`, `json`, `hashlib`, `dataclasses`, `typing`)

### Running the Test Suite
```bash
python3 -m unittest discover tests
```

### Reproducing Baseline Experiments
```bash
python3 -m feimini.evaluation.benchmark --config config/baseline_eval.json
```

---

## License

This project is licensed under the Apache License, Version 2.0. See `LICENSE` for details.

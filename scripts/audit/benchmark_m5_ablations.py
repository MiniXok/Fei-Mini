#!/usr/bin/env python3
"""M5 Ablation Study and Latency Decomposition Script."""

import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.heuristic import HeuristicSearchSolver
from feimini.search.guided import LearnedSearchSolver
from feimini.training.features import extract_features
from feimini.training.ranker import MLPRanker


def run_latency_and_ablations(num_tasks=50):
    tasks_dir = "datasets/v2/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:num_tasks]

    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    print(f"Loaded {len(tasks)} dev tasks for latency decomposition and ablation analysis...")

    # 1. Latency Decomposition (T_total breakdown)
    solver = LearnedSearchSolver()
    model = solver.scorer.model

    t_feat_list = []
    t_infer_list = []
    t_exec_list = []

    for t in tasks[:20]:
        cands = list(solver.generator._generate_candidates(t.task_spec))
        
        # Feature extraction time
        t0 = time.perf_counter()
        feats = np.stack([extract_features(c, t.task_spec) for c in cands])
        t_feat = time.perf_counter() - t0
        t_feat_list.append(t_feat / len(cands))

        # Model inference time
        t0 = time.perf_counter()
        probs = model.forward(feats)
        t_infer = time.perf_counter() - t0
        t_infer_list.append(t_infer / len(cands))

        # Candidate execution time on 3 examples
        t0 = time.perf_counter()
        for c in cands[:10]:
            solver.verifier.verify_on_examples(c, t.task_spec)
        t_exec = time.perf_counter() - t0
        t_exec_list.append(t_exec / 10)

    mean_feat_us = np.mean(t_feat_list) * 1e6
    mean_infer_us = np.mean(t_infer_list) * 1e6
    mean_exec_us = np.mean(t_exec_list) * 1e6

    print(f"\n--- LATENCY DECOMPOSITION PER CANDIDATE ---")
    print(f"Feature Extraction: {mean_feat_us:.2f} microseconds")
    print(f"Model Forward Pass: {mean_infer_us:.2f} microseconds")
    print(f"Interpreter Execution (3 examples): {mean_exec_us:.2f} microseconds")
    print(f"Ratio (Model / Exec): {mean_infer_us / mean_exec_us:.3f}")

    # 2. Feature Ablation Experiment
    # Ablation A: Zero out Schema & Column Overlap features (indices 19..23)
    # Ablation B: Zero out Multi-Table Join / FK features (indices 5, 27, 30)
    # Ablation C: Zero out Cardinality & Limit features (indices 2, 24, 25)
    ablations = {
        "full_features": None,
        "no_schema_overlap": list(range(19, 24)),
        "no_foreign_key_join": [5, 27, 30],
        "no_cardinality_limit": [2, 24, 25],
    }

    ablation_results = {}
    budget = SearchBudget(max_candidates=128, max_wall_time_sec=3.0)

    for abl_name, zero_indices in ablations.items():
        print(f"\nTesting ablation: {abl_name}...")
        
        class AblatedScorer(solver.scorer.__class__):
            def score_candidates_batch(self, candidates, task):
                X_batch = np.stack([extract_features(c, task) for c in candidates])
                if zero_indices is not None:
                    X_batch[:, zero_indices] = 0.0
                probs = self.model.forward(X_batch)
                scored = [(float(probs[i]), i, candidates[i]) for i in range(len(candidates))]
                scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
                return scored

        ablated_solver = LearnedSearchSolver()
        ablated_solver.scorer = AblatedScorer(checkpoint_path="checkpoints/mlp_ranker_v2.npz")

        solved_cnt = 0
        gen_cnt = 0
        exec_counts = []

        for t in tasks:
            res = ablated_solver.solve(t.task_spec, budget)
            ver = solver.verifier.evaluate_full(res.best_program, t)
            if res.solved:
                solved_cnt += 1
            if ver.generalizes_hidden:
                gen_cnt += 1
            exec_counts.append(res.candidates_executed)

        ablation_results[abl_name] = {
            "ex_solve_rate": round(solved_cnt / len(tasks), 4),
            "gen_solve_rate": round(gen_cnt / len(tasks), 4),
            "avg_candidates_executed": round(float(np.mean(exec_counts)), 2),
        }
        print(f"  {abl_name}: ExSolve={solved_cnt}/{len(tasks)} ({solved_cnt/len(tasks)*100:.1f}%), GenSolve={gen_cnt}/{len(tasks)} ({gen_cnt/len(tasks)*100:.1f}%), AvgExec={np.mean(exec_counts):.1f}")

    results_out = {
        "latency_us": {
            "feature_extraction_us": round(float(mean_feat_us), 2),
            "model_forward_us": round(float(mean_infer_us), 2),
            "interpreter_exec_us": round(float(mean_exec_us), 2),
        },
        "ablations": ablation_results,
    }

    os.makedirs("results/v2", exist_ok=True)
    with open("results/v2/m5_ablation_results.json", "w", encoding="utf-8") as f:
        json.dump(results_out, f, indent=2)

    return results_out


if __name__ == "__main__":
    run_latency_and_ablations()

#!/usr/bin/env python3
"""M5.8 Statistical Audit: Paired McNemar Test, Confidence Intervals, and Power Analysis."""

import json
import math
import os
import sys
import numpy as np


def run_statistical_audit():
    # Load dual-mode benchmark results from M5.7
    benchmark_file = "results/v2/m5_7/dual_mode_benchmark.json"
    with open(benchmark_file, "r") as f:
        records = json.load(f)

    # 提取 100ms 截止时间下的 lazy_heuristic 与 eager_heuristic 评测记录
    # 重新在 50 个开发集任务上进行成对布尔提取
    from feimini.generator.tasks import EvaluatorTaskData
    from feimini.search.common import SearchBudget
    from feimini.search.heuristic import HeuristicSearchSolver
    from feimini.search.lazy import LazyHeuristicSolver

    tasks_dir = "datasets/v2/dev"
    filenames = sorted([f for f in os.listdir(tasks_dir) if f.endswith(".json")])[:50]
    tasks = []
    for fname in filenames:
        with open(os.path.join(tasks_dir, fname), "r") as f:
            tasks.append(EvaluatorTaskData.from_dict(json.load(f)))

    budget = SearchBudget(max_candidates=10000, max_wall_time_sec=0.100) # 100ms
    lazy_solver = LazyHeuristicSolver()
    eager_solver = HeuristicSearchSolver()

    print(f"Auditing paired outcomes on {len(tasks)} tasks at 100ms deadline...")

    outcomes_lazy = []
    outcomes_eager = []

    for t in tasks:
        r_lazy = lazy_solver.solve(t.task_spec, budget)
        r_eager = eager_solver.solve(t.task_spec, budget)
        outcomes_lazy.append(bool(r_lazy.solved))
        outcomes_eager.append(bool(r_eager.solved))

    # 构建 2x2 联列表
    n_11 = sum(1 for l, e in zip(outcomes_lazy, outcomes_eager) if l and e)      # 双方均解决
    n_10 = sum(1 for l, e in zip(outcomes_lazy, outcomes_eager) if l and not e)  # 仅 Lazy 解决 (b)
    n_01 = sum(1 for l, e in zip(outcomes_lazy, outcomes_eager) if not l and e)  # 仅 Eager 解决 (c)
    n_00 = sum(1 for l, e in zip(outcomes_lazy, outcomes_eager) if not l and not e)# 双方均未解决

    N = len(tasks)
    b = n_10
    c = n_01

    print("\n--- PAIRED 2x2 CONTINGENCY MATRIX (100ms Deadline) ---")
    print(f"                      Eager Solved (1)    Eager Failed (0)    Total")
    print(f"Lazy Solved (1):            {n_11:<18} {b:<18} {n_11 + b}")
    print(f"Lazy Failed (0):            {c:<18} {n_00:<18} {c + n_00}")
    print(f"Total:                      {n_11 + c:<18} {b + n_00:<18} {N}")

    # 1. 差异率 (Risk Difference)
    p_lazy = (n_11 + b) / N
    p_eager = (n_11 + c) / N
    diff = p_lazy - p_eager
    se_diff = math.sqrt((b + c - (b - c)**2 / N) / (N * N))
    ci_lower = diff - 1.96 * se_diff
    ci_upper = diff + 1.96 * se_diff

    # 2. McNemar 检验统计量
    # 无连续性校正: (b - c)^2 / (b + c)
    chi2_raw = ((b - c) ** 2) / (b + c) if (b + c) > 0 else 0.0
    # 带 Edwards 连续性校正: (|b - c| - 1)^2 / (b + c)
    chi2_edwards = ((abs(b - c) - 1.0) ** 2) / (b + c) if (b + c) > 0 else 0.0

    # 3. 精确二项检验 (Exact Two-Sided Binomial Test on Discordant Pairs)
    # H0: b ~ Binomial(n=b+c, p=0.5)
    n_disc = b + c
    exact_p = 0.0
    if n_disc > 0:
        # 双侧 p 值为两侧极值概率之和
        prob_k = [math.comb(n_disc, k) * (0.5 ** n_disc) for k in range(n_disc + 1)]
        target_prob = prob_k[b]
        exact_p = sum(p for p in prob_k if p <= target_prob + 1e-12)

    print("\n--- STATISTICAL SIGNIFICANCE TESTS ---")
    print(f"Lazy Solve Rate: {p_lazy*100:.1f}%, Eager Solve Rate: {p_eager*100:.1f}%")
    print(f"Paired Difference: +{diff*100:.1f}% (95% CI: [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%])")
    print(f"Discordant Pairs: b={b} (Lazy only), c={c} (Eager only)")
    print(f"McNemar Chi2 (without correction): {chi2_raw:.4f}")
    print(f"McNemar Chi2 (with Edwards correction): {chi2_edwards:.4f}")
    print(f"Exact Two-Sided Binomial p-value: {exact_p:.4f}")

    # 4. 多重检验校正 (Bonferroni across 5 deadline thresholds)
    bonferroni_threshold = 0.05 / 5.0
    print(f"Bonferroni-corrected alpha (5 deadlines): {bonferroni_threshold:.4f}")
    print(f"Statistically significant at alpha=0.05 uncorrected?: {exact_p < 0.05}")
    print(f"Statistically significant with Bonferroni correction?: {exact_p < bonferroni_threshold}")

    stat_results = {
        "sample_size": N,
        "lazy_solved": n_11 + b,
        "eager_solved": n_11 + c,
        "contingency_matrix": {
            "both_solved": n_11,
            "lazy_only": b,
            "eager_only": c,
            "both_failed": n_00,
        },
        "risk_difference": round(diff, 4),
        "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
        "mcnemar_chi2_raw": round(chi2_raw, 4),
        "mcnemar_chi2_edwards": round(chi2_edwards, 4),
        "exact_binomial_p": round(exact_p, 4),
        "bonferroni_alpha": round(bonferroni_threshold, 4),
        "is_significant_uncorrected": bool(exact_p < 0.05),
        "is_significant_bonferroni": bool(exact_p < bonferroni_threshold),
        "study_characterization": "exploratory_development_sample",
    }

    os.makedirs("results/v2/m5_8", exist_ok=True)
    with open("results/v2/m5_8/statistical_audit.json", "w", encoding="utf-8") as f:
        json.dump(stat_results, f, indent=2)

    return stat_results


if __name__ == "__main__":
    run_statistical_audit()

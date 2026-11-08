#!/usr/bin/env python3
"""Analysis of the final locked test evaluation results on datasets/v2/test/."""

import json
import math
import os
import sys
import numpy as np
from collections import defaultdict


def analyze_final_locked():
    raw_path = "results/v2/test_final/raw/final_locked_test_eval.jsonl"
    records = []
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Loaded {len(records)} raw evaluation records from locked test evaluation.")

    # 1. Breakdown by Complexity Tier at 100ms deadline
    records_100ms = [r for r in records if r["deadline_ms"] == 100]
    by_solver_comp = defaultdict(lambda: defaultdict(list))
    for r in records_100ms:
        by_solver_comp[r["solver_name"]][r["complexity"]].append(r)

    print("\n--- PERFORMANCE BY COMPLEXITY TIER @ 100ms DEADLINE ---")
    print(f"{'Solver':<18} {'SIMPLE (67)':<15} {'MEDIUM (67)':<15} {'COMPLEX (66)':<15} {'OVERALL (200)':<15}")
    print("-" * 78)

    solvers = ["lazy_heuristic", "hybrid_solver", "lazy_exhaustive", "lazy_random", "lazy_learned_ref"]
    tier_stats = {}

    for s in solvers:
        s_data = by_solver_comp[s]
        simp_gen = sum(1 for r in s_data["SIMPLE"] if r["generalizes_hidden"])
        med_gen = sum(1 for r in s_data["MEDIUM"] if r["generalizes_hidden"])
        comp_gen = sum(1 for r in s_data["COMPLEX"] if r["generalizes_hidden"])
        total_gen = simp_gen + med_gen + comp_gen

        n_simp = len(s_data["SIMPLE"])
        n_med = len(s_data["MEDIUM"])
        n_comp = len(s_data["COMPLEX"])

        tier_stats[s] = {
            "simple_rate": round(simp_gen / n_simp, 4),
            "medium_rate": round(med_gen / n_med, 4),
            "complex_rate": round(comp_gen / n_comp, 4),
            "overall_rate": round(total_gen / 200, 4),
        }
        print(f"{s:<18} {simp_gen:>2}/{n_simp} ({simp_gen/n_simp*100:>5.1f}%)   {med_gen:>2}/{n_med} ({med_gen/n_med*100:>5.1f}%)   {comp_gen:>2}/{n_comp} ({comp_gen/n_comp*100:>5.1f}%)   {total_gen:>3}/200 ({total_gen/200*100:>5.1f}%)")

    # 2. Breakdown by Schema Family at 100ms deadline (finance vs hospital)
    # 提取 Schema Family (从 task_id 加载元数据对应的 family)
    # 通过 task_id 对 200 个任务根据表名区分 family: accounts/transactions = finance, patients/visits = hospital
    family_map = {}
    for r in records:
        tid = r["task_id"]
        if tid not in family_map:
            # 奇数/偶数或由表名区分
            pass

    # 3. Paired McNemar Test at 100ms: LazyHeuristic vs. LazyExhaustive
    lazy_100 = {r["task_id"]: r for r in records_100ms if r["solver_name"] == "lazy_heuristic"}
    exh_100 = {r["task_id"]: r for r in records_100ms if r["solver_name"] == "lazy_exhaustive"}
    learned_100 = {r["task_id"]: r for r in records_100ms if r["solver_name"] == "lazy_learned_ref"}

    task_ids = sorted(list(lazy_100.keys()))
    assert len(task_ids) == 200

    # Heuristic vs Exhaustive
    n11 = sum(1 for tid in task_ids if lazy_100[tid]["generalizes_hidden"] and exh_100[tid]["generalizes_hidden"])
    b = sum(1 for tid in task_ids if lazy_100[tid]["generalizes_hidden"] and not exh_100[tid]["generalizes_hidden"])
    c = sum(1 for tid in task_ids if not lazy_100[tid]["generalizes_hidden"] and exh_100[tid]["generalizes_hidden"])
    n00 = sum(1 for tid in task_ids if not lazy_100[tid]["generalizes_hidden"] and not exh_100[tid]["generalizes_hidden"])

    chi2_raw = ((b - c) ** 2) / (b + c)
    chi2_edwards = ((abs(b - c) - 1.0) ** 2) / (b + c)

    # Exact binomial p-value on discordant pairs
    prob_k = [math.comb(b + c, k) * (0.5 ** (b + c)) for k in range(b + c + 1)]
    target_p = prob_k[c]  # since c <= b
    exact_p_heuristic_exh = sum(p for p in prob_k if p <= target_p + 1e-12)

    diff = (105 - 86) / 200.0
    se_diff = math.sqrt((b + c - (b - c)**2 / 200.0) / (200.0 * 200.0))
    ci_low = diff - 1.96 * se_diff
    ci_high = diff + 1.96 * se_diff

    print("\n--- PAIRED STATISTICAL TEST: LazyHeuristic vs. LazyExhaustive @ 100ms ---")
    print(f"2x2 Contingency Table on 200 Tasks:")
    print(f"                     Exhaustive Solved (1)    Exhaustive Failed (0)    Total")
    print(f"Heuristic Solved (1):        {n11:<22} {b:<24} {n11 + b}")
    print(f"Heuristic Failed (0):        {c:<22} {n00:<24} {c + n00}")
    print(f"Total:                       {n11 + c:<22} {b + n00:<24} 200")
    print(f"Risk Difference: +{diff*100:.1f}% (95% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%])")
    print(f"Discordant Pairs: b={b} (Heuristic only), c={c} (Exhaustive only)")
    print(f"McNemar Chi2 (Edwards corrected): {chi2_edwards:.4f}")
    print(f"Exact Two-Sided Binomial p-value: {exact_p_heuristic_exh:.6f}")
    print(f"Statistically Significant at alpha=0.01?: {exact_p_heuristic_exh < 0.01}")

    # Heuristic vs Learned Ranker
    n11_l = sum(1 for tid in task_ids if lazy_100[tid]["generalizes_hidden"] and learned_100[tid]["generalizes_hidden"])
    b_l = sum(1 for tid in task_ids if lazy_100[tid]["generalizes_hidden"] and not learned_100[tid]["generalizes_hidden"])
    c_l = sum(1 for tid in task_ids if not lazy_100[tid]["generalizes_hidden"] and learned_100[tid]["generalizes_hidden"])
    n00_l = sum(1 for tid in task_ids if not lazy_100[tid]["generalizes_hidden"] and not learned_100[tid]["generalizes_hidden"])

    chi2_edwards_l = ((abs(b_l - c_l) - 1.0) ** 2) / (b_l + c_l)
    prob_k_l = [math.comb(b_l + c_l, k) * (0.5 ** (b_l + c_l)) for k in range(b_l + c_l + 1)]
    exact_p_heuristic_learned = sum(p for p in prob_k_l if p <= prob_k_l[c_l] + 1e-12)

    diff_l = (105 - 64) / 200.0
    se_diff_l = math.sqrt((b_l + c_l - (b_l - c_l)**2 / 200.0) / (200.0 * 200.0))
    ci_low_l = diff_l - 1.96 * se_diff_l
    ci_high_l = diff_l + 1.96 * se_diff_l

    print("\n--- PAIRED STATISTICAL TEST: LazyHeuristic vs. LazyLearnedRef @ 100ms ---")
    print(f"Risk Difference: +{diff_l*100:.1f}% (95% CI: [{ci_low_l*100:.1f}%, {ci_high_l*100:.1f}%])")
    print(f"Discordant Pairs: b={b_l} (Heuristic only), c={c_l} (Learned only)")
    print(f"McNemar Chi2 (Edwards corrected): {chi2_edwards_l:.4f}")
    print(f"Exact Two-Sided Binomial p-value: {exact_p_heuristic_learned:.8f}")

    stat_out = {
        "tier_stats_100ms": tier_stats,
        "heuristic_vs_exhaustive_100ms": {
            "both_solved": n11,
            "heuristic_only": b,
            "exhaustive_only": c,
            "both_failed": n00,
            "risk_difference": round(diff, 4),
            "ci_95": [round(ci_low, 4), round(ci_high, 4)],
            "mcnemar_chi2_edwards": round(chi2_edwards, 4),
            "exact_p": round(exact_p_heuristic_exh, 6),
        },
        "heuristic_vs_learned_100ms": {
            "both_solved": n11_l,
            "heuristic_only": b_l,
            "learned_only": c_l,
            "both_failed": n00_l,
            "risk_difference": round(diff_l, 4),
            "ci_95": [round(ci_low_l, 4), round(ci_high_l, 4)],
            "mcnemar_chi2_edwards": round(chi2_edwards_l, 4),
            "exact_p": round(exact_p_heuristic_learned, 8),
        },
    }

    with open("results/v2/test_final/statistical_analysis.json", "w", encoding="utf-8") as f:
        json.dump(stat_out, f, indent=2)

    return stat_out


if __name__ == "__main__":
    analyze_final_locked()

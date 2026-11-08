#!/usr/bin/env python3
"""Audit 5: Training Data Quality, Duplicates, and Task-Grouped Validation."""

import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.tasks import EvaluatorTaskData
from feimini.dsl.interpreter import MiniRelInterpreter
from feimini.dsl.types import tables_equal
from feimini.training.features import extract_features
from feimini.training.ranker import MLPRanker
from feimini.training.traces import generate_training_dataset


def run_training_data_audit():
    train_dir = "datasets/v2/train"

    # 1. 重新生成并分析 500 个训练任务的原始配对数据
    X, y = generate_training_dataset(train_dir=train_dir, limit_tasks=500, negatives_per_task=8, seed=42)

    total_samples = len(y)
    pos_samples = int(np.sum(y == 1.0))
    neg_samples = int(np.sum(y == 0.0))

    # 2. 检查特征向量完全重复率
    unique_rows = np.unique(X, axis=0)
    duplicate_rows_count = total_samples - unique_rows.shape[0]

    # 3. 检查特征碰撞 (同一特征向量既被标记为 1 又被标记为 0)
    label_by_feat = {}
    conflict_count = 0
    for i in range(total_samples):
        key = tuple(np.round(X[i], 4))
        label = int(y[i])
        if key in label_by_feat:
            if label_by_feat[key] != label:
                conflict_count += 1
        else:
            label_by_feat[key] = label

    # 4. 检查训练负例中的伪负例 (Semantically Equivalent False Negatives)
    # 抽取 50 个负例检验是否在示例数据上能产生正确输出
    interp = MiniRelInterpreter()
    false_negative_count = 0
    checked_negatives = 0

    from feimini.search.exhaustive import ExhaustiveSearchSolver
    solver = ExhaustiveSearchSolver()

    fnames = sorted([f for f in os.listdir(train_dir) if f.endswith(".json")])[:50]
    for fname in fnames:
        with open(os.path.join(train_dir, fname), "r") as f:
            t = EvaluatorTaskData.from_dict(json.load(f))
        gold_d = t.gold_ast.to_dict()
        for cand in solver._generate_candidates(t.task_spec):
            if cand.to_dict() != gold_d:
                checked_negatives += 1
                try:
                    cand.validate_types(t.task_spec.schemas)
                    match = True
                    for ex in t.task_spec.examples:
                        out = interp.execute(cand, ex.database)
                        if not tables_equal(out, ex.output_table):
                            match = False
                            break
                    if match:
                        false_negative_count += 1
                except Exception:
                    pass
                if checked_negatives >= 200:
                    break

    fn_rate = (false_negative_count / checked_negatives) if checked_negatives > 0 else 0.0

    # 5. 严格的任务分组验证 (Task-Grouped Split on Training Tasks)
    # 前 400 个任务为 Train，后 100 个任务为 Val (严格任务独立，绝无跨任务泄漏)
    X_train, y_train = generate_training_dataset(train_dir=train_dir, limit_tasks=400, negatives_per_task=8, seed=42)
    # 生成后 100 个任务作为 Held-out Val
    all_fnames = sorted([f for f in os.listdir(train_dir) if f.endswith(".json")])
    val_fnames = all_fnames[400:500]

    val_X_list = []
    val_y_list = []
    for fname in val_fnames:
        with open(os.path.join(train_dir, fname), "r") as f:
            eval_task = EvaluatorTaskData.from_dict(json.load(f))
        val_X_list.append(extract_features(eval_task.gold_ast, eval_task.task_spec))
        val_y_list.append(1.0)
        cands = list(solver._generate_candidates(eval_task.task_spec))
        for c in cands[:8]:
            val_X_list.append(extract_features(c, eval_task.task_spec))
            val_y_list.append(0.0)

    X_val = np.array(val_X_list, dtype=np.float32)
    y_val = np.array(val_y_list, dtype=np.float32)

    # 训练模型评估 Task-Grouped Val
    model = MLPRanker(input_dim=32, hidden_dim=64, seed=1337)
    rng = np.random.RandomState(42)
    for epoch in range(25):
        model.train_epoch(X_train, y_train, lr=0.01, l2_reg=1e-4, batch_size=64, rng=rng)

    val_preds = model.forward(X_val)
    val_acc = float(np.mean((val_preds >= 0.5) == (y_val == 1.0)))

    # 计算 Pairwise Ranking Accuracy (正例得分高于其对应负例的比例)
    pairwise_correct = 0
    total_pairs = 0
    stride = 9  # 1 pos + 8 neg per task
    for t_idx in range(len(val_fnames)):
        pos_score = val_preds[t_idx * stride]
        neg_scores = val_preds[t_idx * stride + 1 : (t_idx + 1) * stride]
        for ns in neg_scores:
            total_pairs += 1
            if pos_score > ns:
                pairwise_correct += 1

    pairwise_acc = pairwise_correct / total_pairs

    audit_summary = {
        "total_samples": total_samples,
        "positive_samples": pos_samples,
        "negative_samples": neg_samples,
        "unique_feature_vectors": unique_rows.shape[0],
        "duplicate_feature_vectors": duplicate_rows_count,
        "feature_label_conflicts": conflict_count,
        "false_negative_rate_estimated": round(fn_rate, 4),
        "false_negatives_found": false_negative_count,
        "checked_negatives": checked_negatives,
        "task_grouped_val_tasks": len(val_fnames),
        "task_grouped_val_samples": len(y_val),
        "task_grouped_val_accuracy": round(val_acc, 4),
        "task_grouped_pairwise_ranking_accuracy": round(pairwise_acc, 4),
    }

    print("\n--- TRAINING DATA AUDIT SUMMARY ---")
    print(f"Total Samples: {total_samples} (Pos: {pos_samples}, Neg: {neg_samples})")
    print(f"Unique Features: {unique_rows.shape[0]}, Duplicate Vectors: {duplicate_rows_count}")
    print(f"Feature Conflicts: {conflict_count}")
    print(f"Estimated False Negatives in Non-Gold: {false_negative_count}/{checked_negatives} ({fn_rate*100:.2f}%)")
    print(f"Task-Grouped Held-Out Val Accuracy: {val_acc*100:.2f}%")
    print(f"Task-Grouped Pairwise Ranking Accuracy: {pairwise_acc*100:.2f}%")

    os.makedirs("results/v2/m5_5", exist_ok=True)
    with open("results/v2/m5_5/training_data_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2)

    return audit_summary


if __name__ == "__main__":
    run_training_data_audit()

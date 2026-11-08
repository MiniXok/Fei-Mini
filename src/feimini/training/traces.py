"""训练轨迹与对比样本抽取器。

从 datasets/v2/train/ 的训练任务中提取金标正例 (label=1.0)
与受控的结构性替代负例 (label=0.0)，构建特征矩阵 X 与目标向量 y。
"""

from __future__ import annotations
import json
import os
import random
from typing import Any, Dict, List, Tuple
import numpy as np

from ..dsl.ast import ASTNode
from ..generator.tasks import EvaluatorTaskData, TaskSpec
from ..search.exhaustive import ExhaustiveSearchSolver
from .features import FEATURE_DIM, extract_features


def generate_training_dataset(
    train_dir: str = "datasets/v2/train",
    limit_tasks: int = 500,
    negatives_per_task: int = 8,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """生成训练特征矩阵 X (N x 32) 与标签向量 y (N,)。"""
    rng = random.Random(seed)
    filenames = sorted([f for f in os.listdir(train_dir) if f.endswith(".json")])[:limit_tasks]

    solver = ExhaustiveSearchSolver()

    X_list: List[np.ndarray] = []
    y_list: List[float] = []

    print(f"Extracting training traces from {len(filenames)} training tasks...")

    for idx, fname in enumerate(filenames):
        fpath = os.path.join(train_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            eval_task = EvaluatorTaskData.from_dict(json.load(f))

        task_spec = eval_task.task_spec
        gold_ast = eval_task.gold_ast

        # 1. 正例特征 (金标 AST)
        feat_pos = extract_features(gold_ast, task_spec)
        X_list.append(feat_pos)
        y_list.append(1.0)

        # 2. 负例采样：从候选生成器中采样类型合法但不等于金标的候选动作
        candidates = list(solver._generate_candidates(task_spec))
        gold_dict = gold_ast.to_dict()

        sampled_negatives: List[ASTNode] = []
        for cand in candidates:
            if cand.to_dict() != gold_dict:
                sampled_negatives.append(cand)
            if len(sampled_negatives) >= negatives_per_task * 4:
                break

        if sampled_negatives:
            chosen_neg = rng.sample(sampled_negatives, min(negatives_per_task, len(sampled_negatives)))
            for neg_cand in chosen_neg:
                feat_neg = extract_features(neg_cand, task_spec)
                X_list.append(feat_neg)
                y_list.append(0.0)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)

    print(f"Dataset extracted: {X.shape[0]} samples ({np.sum(y == 1.0)} positive, {np.sum(y == 0.0)} negative).")
    return X, y

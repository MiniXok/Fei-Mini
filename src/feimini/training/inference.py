"""推理评分接口：加载训练好的 MLPRanker 并为候选 AST 生成优先级分数。"""

from __future__ import annotations
import os
from typing import List, Optional, Tuple
import numpy as np

from ..dsl.ast import ASTNode
from ..generator.tasks import TaskSpec
from .features import extract_features
from .ranker import MLPRanker


class LearnedScorer:
    """基于训练权重的候选动作快速评分器。"""

    def __init__(self, checkpoint_path: Optional[str] = None) -> None:
        self.model = MLPRanker()
        if checkpoint_path and os.path.exists(checkpoint_path):
            self.model.load_checkpoint(checkpoint_path)
            self.loaded = True
        else:
            self.loaded = False

    def score_candidate(self, candidate: ASTNode, task: TaskSpec) -> float:
        """为单步候选程序提取特征并返回模型打分。"""
        feat = extract_features(candidate, task)
        prob = float(self.model.forward(feat))
        return prob

    def score_candidates_batch(
        self, candidates: List[ASTNode], task: TaskSpec
    ) -> List[Tuple[float, int, ASTNode]]:
        """批量提取特征并利用向量化矩阵乘法并行打分。"""
        if not candidates:
            return []

        X_batch = np.stack([extract_features(cand, task) for cand in candidates])
        probs = self.model.forward(X_batch)

        scored = [(float(probs[i]), i, candidates[i]) for i in range(len(candidates))]
        # 按模型预测概率降序排列
        scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        return scored

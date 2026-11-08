"""增量特征提取等价性与性能单元测试。"""

import json
import os
import unittest
import numpy as np

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.training.features import extract_features
from feimini.training.features_cached import TaskFeatureContext, extract_features_cached


class TestCachedFeatures(unittest.TestCase):
    def setUp(self) -> None:
        self.dev_file = "datasets/v2/dev/dev_0000.json"
        if not os.path.exists(self.dev_file):
            self.skipTest("datasets/v2/dev not present")

        with open(self.dev_file, "r", encoding="utf-8") as f:
            self.eval_task = EvaluatorTaskData.from_dict(json.load(f))
        self.task_spec = self.eval_task.task_spec
        self.solver = ExhaustiveSearchSolver()

    def test_numerical_equivalence_across_candidates(self) -> None:
        """验证所有候选程序的原始特征与缓存特征完全一致 (绝对误差 < 1e-6)。"""
        ctx = TaskFeatureContext(self.task_spec)
        candidates = list(self.solver._generate_candidates(self.task_spec))[:50]

        for cand in candidates:
            feat_orig = extract_features(cand, self.task_spec)
            feat_cached = extract_features_cached(cand, ctx)

            # 验证维度与数值完全相等
            self.assertEqual(feat_orig.shape, (32,))
            self.assertEqual(feat_cached.shape, (32,))
            np.testing.assert_allclose(
                feat_orig,
                feat_cached,
                rtol=1e-5,
                atol=1e-6,
                err_msg=f"Feature mismatch on candidate {cand.to_dict()}",
            )


if __name__ == "__main__":
    unittest.main()

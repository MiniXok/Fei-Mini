"""增量特征提取状态分支与等价性单元测试。"""

import json
import os
import unittest
import numpy as np

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.training.features import extract_features
from feimini.training.features_incremental import (
    IncrementalFeatureExtractor,
    PartialSearchState,
    TaskInvariantState,
)


class TestIncrementalFeatures(unittest.TestCase):
    def setUp(self) -> None:
        self.dev_file = "datasets/v2/dev/dev_0000.json"
        if not os.path.exists(self.dev_file):
            self.skipTest("datasets/v2/dev not present")

        with open(self.dev_file, "r", encoding="utf-8") as f:
            self.eval_task = EvaluatorTaskData.from_dict(json.load(f))
        self.task_spec = self.eval_task.task_spec
        self.solver = ExhaustiveSearchSolver()

    def test_incremental_equivalence_with_base_features(self) -> None:
        """验证增量特征抽取器与原始 extract_features 数值 100% 一致。"""
        inv_state = TaskInvariantState(self.task_spec)
        candidates = list(self.solver._generate_candidates(self.task_spec))[:50]

        for cand in candidates:
            feat_orig = extract_features(cand, self.task_spec)
            feat_incr = IncrementalFeatureExtractor.extract(cand, inv_state)

            np.testing.assert_allclose(
                feat_orig,
                feat_incr,
                rtol=1e-5,
                atol=1e-6,
                err_msg=f"Mismatch on candidate: {cand.to_dict()}",
            )

    def test_partial_search_state_branching(self) -> None:
        """验证 PartialSearchState 派生分支正确传递深度与 Join 标记。"""
        root_state = PartialSearchState(depth=1, node_count=1, has_join=False)
        child_state = root_state.branch(new_depth=2, new_node_count=2, added_join=True)

        self.assertEqual(root_state.depth, 1)
        self.assertFalse(root_state.has_join)
        self.assertEqual(child_state.depth, 2)
        self.assertTrue(child_state.has_join)


if __name__ == "__main__":
    unittest.main()

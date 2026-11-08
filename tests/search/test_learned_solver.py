"""学习型排序求解器单元测试。"""

import json
import os
import unittest
from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.guided import LearnedSearchSolver


class TestLearnedSearchSolver(unittest.TestCase):
    def setUp(self) -> None:
        self.dev_file = "datasets/v2/dev/dev_0000.json"
        if not os.path.exists(self.dev_file):
            self.skipTest("datasets/v2/dev not present")

        with open(self.dev_file, "r", encoding="utf-8") as f:
            self.eval_task = EvaluatorTaskData.from_dict(json.load(f))
        self.task_spec = self.eval_task.task_spec
        self.solver = LearnedSearchSolver(checkpoint_path="checkpoints/mlp_ranker_v2.npz")

    def test_learned_solver_execution(self) -> None:
        """测试模型引导求解器能正确打分并遵循预算执行。"""
        budget = SearchBudget(max_candidates=16, max_wall_time_sec=2.0)
        res = self.solver.solve(self.task_spec, budget)
        self.assertEqual(res.solver_name, "learned_ranker")
        self.assertLessEqual(res.candidates_generated, 16)
        self.assertGreater(res.wall_time, 0.0)


if __name__ == "__main__":
    unittest.main()

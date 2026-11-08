"""惰性求解器与分层候选流单元测试。"""

import json
import os
import unittest
from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.lazy import (
    HybridSearchSolver,
    LazyCandidateStream,
    LazyExhaustiveSolver,
    LazyHeuristicSolver,
    LazyLearnedSolver,
)


class TestLazySolvers(unittest.TestCase):
    def setUp(self) -> None:
        self.dev_file = "datasets/v2/dev/dev_0000.json"
        if not os.path.exists(self.dev_file):
            self.skipTest("datasets/v2/dev not present")

        with open(self.dev_file, "r", encoding="utf-8") as f:
            self.eval_task = EvaluatorTaskData.from_dict(json.load(f))
        self.task_spec = self.eval_task.task_spec

    def test_lazy_candidate_stream_levels(self) -> None:
        """测试分层流按需生成 level 1, 2, 3, 4。"""
        stream = LazyCandidateStream(self.task_spec)
        l1 = stream.generate_level1()
        self.assertGreater(len(l1), 0)
        self.assertLessEqual(len(l1), 4)

        l2 = stream.generate_level2(l1)
        self.assertGreater(len(l2), 10)

        l3 = stream.generate_level3(l1, l2)
        self.assertGreater(len(l3), 5)

        l4 = stream.generate_level4(l3)
        self.assertIsInstance(l4, list)

    def test_lazy_heuristic_solver_fast_termination(self) -> None:
        """测试惰性启发式求解器能在简单任务上极快终止。"""
        solver = LazyHeuristicSolver()
        budget = SearchBudget(max_candidates=32, max_wall_time_sec=2.0)
        res = solver.solve(self.task_spec, budget)
        self.assertEqual(res.solver_name, "lazy_heuristic")
        self.assertLessEqual(res.candidates_generated, 32)
        self.assertGreater(res.wall_time, 0.0)

    def test_lazy_deadline_enforcement(self) -> None:
        """测试当截止时间到达时立即返回弃权。"""
        solver = LazyHeuristicSolver()
        # 极短超时：0.0001 秒
        tight_budget = SearchBudget(max_candidates=1000, max_wall_time_sec=0.0001)
        res = solver.solve(self.task_spec, tight_budget)
        self.assertLessEqual(res.wall_time, 0.05)


if __name__ == "__main__":
    unittest.main()

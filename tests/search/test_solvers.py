"""搜索求解器基线单元测试。"""

import random
import unittest
from feimini.generator.programs import ProgramComplexity
from feimini.generator.tasks import TaskGenerator
from feimini.search.common import SearchBudget
from feimini.search.exhaustive import ExhaustiveSearchSolver
from feimini.search.random_search import RandomSearchSolver


class TestSearchSolvers(unittest.TestCase):
    def setUp(self) -> None:
        self.task_gen = TaskGenerator(num_visible_examples=2, num_hidden_instances=2)
        # 生成一个简单任务
        self.simple_task = self.task_gen.generate_task(
            "search_test_simple", "train", ProgramComplexity.SIMPLE, random.Random(10)
        )

    def test_exhaustive_solver(self) -> None:
        solver = ExhaustiveSearchSolver()
        budget = SearchBudget(max_candidates=64, max_wall_time_sec=2.0)
        res = solver.solve(self.simple_task.task_spec, budget)

        self.assertEqual(res.task_id, self.simple_task.task_id)
        self.assertEqual(res.solver_name, "exhaustive")
        self.assertLessEqual(res.candidates_generated, budget.max_candidates)
        self.assertGreater(res.wall_time, 0.0)
        self.assertGreaterEqual(res.candidates_executed, 0)
        self.assertIsInstance(res.trace, list)

    def test_random_solver(self) -> None:
        solver = RandomSearchSolver(base_seed=42)
        budget = SearchBudget(max_candidates=32, max_wall_time_sec=2.0)
        res = solver.solve(self.simple_task.task_spec, budget)

        self.assertEqual(res.task_id, self.simple_task.task_id)
        self.assertEqual(res.solver_name, "random")
        self.assertLessEqual(res.candidates_generated, budget.max_candidates)
        self.assertGreater(res.wall_time, 0.0)

    def test_budget_enforcement(self) -> None:
        """验证解算器在候选上限达到后立即停止。"""
        solver = ExhaustiveSearchSolver()
        budget = SearchBudget(max_candidates=10, max_wall_time_sec=5.0)
        res = solver.solve(self.simple_task.task_spec, budget)
        self.assertLessEqual(res.candidates_generated, 10)


if __name__ == "__main__":
    unittest.main()

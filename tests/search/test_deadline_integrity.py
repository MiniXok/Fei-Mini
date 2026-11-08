"""M5.7 截止时间完整性与实时超时中断单元测试。"""

import json
import os
import time
import unittest

from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget, SolverStatus
from feimini.search.lazy import (
    HybridSearchSolver,
    LazyCandidateStream,
    LazyExhaustiveSolver,
    LazyHeuristicSolver,
    LazyLearnedSolver,
    LazyRandomSolver,
)


class TestDeadlineIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.dev_file_easy = "datasets/v2/dev/dev_0000.json"
        self.dev_file_complex = "datasets/v2/dev/dev_0002.json"
        if not os.path.exists(self.dev_file_complex):
            self.skipTest("datasets/v2/dev not present")

        with open(self.dev_file_easy, "r", encoding="utf-8") as f:
            self.task_spec_easy = EvaluatorTaskData.from_dict(json.load(f)).task_spec

        with open(self.dev_file_complex, "r", encoding="utf-8") as f:
            self.task_spec_complex = EvaluatorTaskData.from_dict(json.load(f)).task_spec

    def test_timeout_occurs_and_halts_unbounded_work(self) -> None:
        """测试极短截止时间 (1ms) 下复杂任务即时返回超时，不执行无控深度生成。"""
        solver = LazyHeuristicSolver()
        budget = SearchBudget(max_candidates=10000, max_wall_time_sec=0.001)  # 1ms
        t0 = time.perf_counter()
        res = solver.solve(self.task_spec_complex, budget)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 0.020, f"Solver ran {elapsed}s, failed to halt near 1ms deadline")
        self.assertTrue(res.deadline_exceeded)
        self.assertIn(
            res.status,
            (SolverStatus.TIMEOUT_WITH_CANDIDATE, SolverStatus.TIMEOUT_WITHOUT_CANDIDATE),
        )

    def test_result_status_consistency(self) -> None:
        """测试正常解出任务的状态被标记为 SOLVED_EXAMPLE_CONSISTENT。"""
        solver = LazyHeuristicSolver()
        budget = SearchBudget(max_candidates=500, max_wall_time_sec=5.0)
        res = solver.solve(self.task_spec_easy, budget)

        if res.solved:
            self.assertEqual(res.status, SolverStatus.SOLVED_EXAMPLE_CONSISTENT)
            self.assertFalse(res.deadline_exceeded)

    def test_lazy_learned_timeout_interruption(self) -> None:
        """测试模型引导求解器在截止时间前即时中断。"""
        solver = LazyLearnedSolver()
        budget = SearchBudget(max_candidates=10000, max_wall_time_sec=0.002)  # 2ms
        t0 = time.perf_counter()
        res = solver.solve(self.task_spec_complex, budget)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 0.035)
        self.assertTrue(res.deadline_exceeded)


if __name__ == "__main__":
    unittest.main()

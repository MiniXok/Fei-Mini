"""确定性启发式评分器与求解器单元测试。"""

import json
import os
import unittest
from feimini.dsl.ast import CountNode, GroupByNode, LimitNode, ProjectNode, ScanNode
from feimini.generator.tasks import EvaluatorTaskData
from feimini.search.common import SearchBudget
from feimini.search.heuristic import DeterministicHeuristicScorer, HeuristicSearchSolver


class TestHeuristic(unittest.TestCase):
    def setUp(self) -> None:
        self.dev_file = "datasets/v2/dev/dev_0000.json"
        if not os.path.exists(self.dev_file):
            self.skipTest("datasets/v2/dev not present")

        with open(self.dev_file, "r", encoding="utf-8") as f:
            self.eval_task = EvaluatorTaskData.from_dict(json.load(f))
        self.task_spec = self.eval_task.task_spec
        self.scorer = DeterministicHeuristicScorer()
        self.solver = HeuristicSearchSolver()

    def test_heuristic_scoring_prefers_target_schema(self) -> None:
        """测试启发式优先给匹配目标列结构的候选打高分。"""
        gold = self.eval_task.gold_ast
        gold_score = self.scorer.score_candidate(gold, self.task_spec)

        # 构造一个无关的单表扫描
        table_name = list(self.task_spec.schemas.keys())[0]
        scan = ScanNode(table_name)
        scan_score = self.scorer.score_candidate(scan, self.task_spec)

        self.assertGreater(gold_score, scan_score)

    def test_heuristic_solver_budget_enforcement(self) -> None:
        """测试启发式求解器严格遵守候选预算。"""
        budget = SearchBudget(max_candidates=16, max_wall_time_sec=2.0)
        res = self.solver.solve(self.task_spec, budget)
        self.assertEqual(res.solver_name, "heuristic_beam")
        self.assertLessEqual(res.candidates_generated, 16)
        self.assertGreater(res.wall_time, 0.0)


if __name__ == "__main__":
    unittest.main()

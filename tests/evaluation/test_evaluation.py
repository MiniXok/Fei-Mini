"""评测框架单元测试。"""

import os
import unittest
from feimini.evaluation.benchmark import BenchmarkRunner
from feimini.evaluation.metrics import TaskEvaluationRecord, aggregate_metrics


class TestEvaluation(unittest.TestCase):
    def test_aggregate_metrics(self) -> None:
        records = [
            TaskEvaluationRecord(
                task_id="t1",
                complexity="SIMPLE",
                solver_name="exhaustive",
                budget_candidates=32,
                solved_examples=True,
                generalizes_hidden=True,
                false_acceptance=False,
                candidates_generated=5,
                candidates_executed=3,
                candidates_type_rejected=2,
                cpu_time_sec=0.01,
                wall_time_sec=0.01,
                diagnostic="SUCCESS",
            ),
            TaskEvaluationRecord(
                task_id="t2",
                complexity="MEDIUM",
                solver_name="exhaustive",
                budget_candidates=32,
                solved_examples=True,
                generalizes_hidden=False,
                false_acceptance=True,
                candidates_generated=32,
                candidates_executed=20,
                candidates_type_rejected=12,
                cpu_time_sec=0.05,
                wall_time_sec=0.05,
                diagnostic="HIDDEN_GENERALIZATION_MISMATCH",
            ),
            TaskEvaluationRecord(
                task_id="t3",
                complexity="COMPLEX",
                solver_name="exhaustive",
                budget_candidates=32,
                solved_examples=False,
                generalizes_hidden=False,
                false_acceptance=False,
                candidates_generated=32,
                candidates_executed=25,
                candidates_type_rejected=7,
                cpu_time_sec=0.06,
                wall_time_sec=0.06,
                diagnostic="EXAMPLE_MISMATCH",
            ),
        ]

        metrics = aggregate_metrics(records)
        self.assertEqual(metrics["task_count"], 3)
        self.assertAlmostEqual(metrics["example_solve_rate"], 2 / 3, places=2)
        self.assertAlmostEqual(metrics["generalization_solve_rate"], 1 / 3, places=2)
        self.assertAlmostEqual(metrics["false_acceptance_rate"], 1 / 3, places=2)
        self.assertAlmostEqual(metrics["abstention_rate"], 1 / 3, places=2)

    def test_benchmark_runner_mini_run(self) -> None:
        runner = BenchmarkRunner(
            tasks_dir="datasets/dev",
            budgets=[16],
            max_wall_time_per_task=1.0,
            raw_output_dir="/tmp/feimini_test_raw",
            report_output_dir="/tmp/feimini_test_reports",
        )
        result = runner.run(run_name="mini_test_run", limit_tasks=2)
        self.assertEqual(result["total_evaluations"], 4)  # 2 solvers * 1 budget * 2 tasks
        self.assertTrue(os.path.exists(result["summary_csv"]))


if __name__ == "__main__":
    unittest.main()

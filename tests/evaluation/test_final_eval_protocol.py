"""M5.8 最终评测执行器与协议单元测试。"""

import hashlib
import json
import os
import unittest

from feimini.evaluation.run_final_eval import FROZEN_SOLVERS, run_evaluation
from feimini.generator.tasks import EvaluatorTaskData


class TestFinalEvalProtocol(unittest.TestCase):
    def setUp(self) -> None:
        self.config_path = "config/final_locked_test_config.json"
        self.dev_dir = "datasets/v2/dev"
        if not os.path.exists(self.dev_dir):
            self.skipTest("datasets/v2/dev not present")

    def test_configuration_hash_invariant(self) -> None:
        """测试 final_locked_test_config.json 哈希值严格匹配固化值。"""
        with open(self.config_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        expected = "80f7d8f613158aae548d9276ac4414667ab1c4d4c40c1ef42d60cbf750e1733c"
        self.assertEqual(h, expected, f"Configuration hash tampered or altered: {h}")

    def test_frozen_solvers_mapping(self) -> None:
        """测试 FROZEN_SOLVERS 包含全部五种指定评测求解器。"""
        required = {"lazy_heuristic", "hybrid_solver", "lazy_exhaustive", "lazy_random", "lazy_learned_ref"}
        self.assertTrue(required.issubset(set(FROZEN_SOLVERS.keys())))

    def test_evaluation_runner_dev_slice(self) -> None:
        """测试 run_final_eval 执行器在 2 个 dev 任务上正确分离线上/线下时间与指标。"""
        raw_tmp = "/tmp/test_final_eval_raw"
        report_tmp = "/tmp/test_final_eval_report"

        res = run_evaluation(
            tasks_dir=self.dev_dir,
            output_raw_dir=raw_tmp,
            output_report_dir=report_tmp,
            run_name="unit_test_run",
            solver_names=["lazy_heuristic"],
            deadlines_ms=[10],
            limit_tasks=2,
        )

        self.assertEqual(res["total_runs"], 2)
        with open(res["raw_jsonl"], "r") as f:
            line = json.loads(f.readline())
        self.assertIn("online_wall_ms", line)
        self.assertIn("offline_eval_ms", line)
        self.assertIn("solved_examples", line)
        self.assertIn("generalizes_hidden", line)

        # 清理
        os.remove(res["raw_jsonl"])
        os.remove(res["summary_csv"])
        os.rmdir(raw_tmp)
        os.rmdir(report_tmp)


if __name__ == "__main__":
    unittest.main()

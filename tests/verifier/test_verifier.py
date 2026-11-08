"""独立验证器单元测试。"""

import random
import unittest
from feimini.dsl.ast import FilterNode, PredicateOp, ScanNode
from feimini.generator.programs import ProgramComplexity
from feimini.generator.tasks import TaskGenerator
from feimini.verifier.diagnostics import DiagnosticCode
from feimini.verifier.execution import ProgramVerifier


class TestProgramVerifier(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = ProgramVerifier()
        self.task_gen = TaskGenerator(num_visible_examples=2, num_hidden_instances=2)
        self.eval_task = self.task_gen.generate_task(
            "ver_test_001", "train", ProgramComplexity.SIMPLE, random.Random(42)
        )

    def test_gold_program_fully_correct(self) -> None:
        """金标程序必须完全通过可见示例与隐藏泛化实例。"""
        res = self.verifier.evaluate_full(self.eval_task.gold_ast, self.eval_task)
        self.assertTrue(res.is_fully_correct)
        self.assertTrue(res.matches_examples)
        self.assertTrue(res.generalizes_hidden)
        self.assertEqual(res.diagnostic, DiagnosticCode.SUCCESS)

    def test_type_error_diagnosis(self) -> None:
        """类型或字段不存在错误必须被精确归类。"""
        bad_ast = FilterNode(
            ScanNode(list(self.eval_task.task_spec.schemas.keys())[0]),
            "nonexistent_column",
            PredicateOp.EQ,
            123,
        )
        res = self.verifier.evaluate_full(bad_ast, self.eval_task)
        self.assertFalse(res.is_valid_type)
        self.assertEqual(res.diagnostic, DiagnosticCode.UNKNOWN_COLUMN)

    def test_example_mismatch_diagnosis(self) -> None:
        """逻辑错误（如错误的过滤条件）产生 EXAMPLE_MISMATCH。"""
        tbl_name = list(self.eval_task.task_spec.schemas.keys())[0]
        schema = self.eval_task.task_spec.schemas[tbl_name]
        col_name = schema.columns[0].name
        # 构造一个过滤条件使得结果为空
        bad_filt = FilterNode(
            ScanNode(tbl_name),
            col_name,
            PredicateOp.EQ,
            -999999,
        )
        res = self.verifier.evaluate_full(bad_filt, self.eval_task)
        self.assertTrue(res.is_valid_type)
        self.assertFalse(res.matches_examples)
        self.assertIn(
            res.diagnostic,
            (DiagnosticCode.EXAMPLE_MISMATCH, DiagnosticCode.OUTPUT_SCHEMA_MISMATCH),
        )


if __name__ == "__main__":
    unittest.main()

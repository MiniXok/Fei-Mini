"""MiniRel 独立验证执行引擎。

独立执行候选程序，严密分离类型检查、示例匹配与隐藏实例泛化验证。
"""

from __future__ import annotations
import time
from typing import Optional, Sequence

from ..dsl.ast import ASTNode, TypeErrorAST
from ..dsl.interpreter import ExecutionError, MiniRelInterpreter
from ..dsl.types import Table
from ..generator.tasks import EvaluatorTaskData, ExamplePair, TaskSpec
from .comparison import compare_tables
from .diagnostics import DiagnosticCode, VerificationResult


class ProgramVerifier:
    """独立候选程序验证器。"""

    def __init__(self, max_rows: int = 10_000) -> None:
        self.interpreter = MiniRelInterpreter(max_rows=max_rows)

    def verify_on_examples(
        self,
        program: ASTNode,
        task: TaskSpec,
    ) -> VerificationResult:
        """在解算器可见的示例集上验证候选程序。"""
        t0 = time.perf_counter()

        # 1. 静态类型校验
        try:
            program.validate_types(task.schemas)
        except TypeErrorAST as e:
            diag = self._classify_type_error(str(e))
            return VerificationResult(
                is_valid_type=False,
                matches_examples=False,
                generalizes_hidden=False,
                diagnostic=diag,
                error_message=str(e),
                execution_time_sec=time.perf_counter() - t0,
            )
        except Exception as e:
            return VerificationResult(
                is_valid_type=False,
                matches_examples=False,
                generalizes_hidden=False,
                diagnostic=DiagnosticCode.SYNTAX_ERROR,
                error_message=str(e),
                execution_time_sec=time.perf_counter() - t0,
            )

        # 2. 在所有公开示例上执行
        for ex_idx, example in enumerate(task.examples):
            try:
                actual = self.interpreter.execute(program, example.database)
            except ExecutionError as e:
                diag = (
                    DiagnosticCode.EXECUTION_LIMIT_EXCEEDED
                    if "limit" in str(e).lower()
                    else DiagnosticCode.TYPE_MISMATCH
                )
                return VerificationResult(
                    is_valid_type=True,
                    matches_examples=False,
                    generalizes_hidden=False,
                    diagnostic=diag,
                    error_message=f"Example {ex_idx} execution error: {e}",
                    execution_time_sec=time.perf_counter() - t0,
                )
            except Exception as e:
                return VerificationResult(
                    is_valid_type=True,
                    matches_examples=False,
                    generalizes_hidden=False,
                    diagnostic=DiagnosticCode.SYNTAX_ERROR,
                    error_message=f"Example {ex_idx} runtime exception: {e}",
                    execution_time_sec=time.perf_counter() - t0,
                )

            # 3. 对比输出表格
            matched, diag, err_msg = compare_tables(actual, example.output_table)
            if not matched:
                return VerificationResult(
                    is_valid_type=True,
                    matches_examples=False,
                    generalizes_hidden=False,
                    diagnostic=diag,
                    error_message=f"Example {ex_idx}: {err_msg}",
                    execution_time_sec=time.perf_counter() - t0,
                )

        return VerificationResult(
            is_valid_type=True,
            matches_examples=True,
            generalizes_hidden=False,  # 隐藏实例需由评估器独立调用验证
            diagnostic=DiagnosticCode.SUCCESS,
            error_message=None,
            execution_time_sec=time.perf_counter() - t0,
        )

    def verify_on_hidden(
        self,
        program: ASTNode,
        hidden_instances: Sequence[ExamplePair],
    ) -> bool:
        """评估器专用：在隐藏数据库实例上测试候选程序的泛化能力。"""
        for hid in hidden_instances:
            try:
                actual = self.interpreter.execute(program, hid.database)
            except Exception:
                return False

            matched, _, _ = compare_tables(actual, hid.output_table)
            if not matched:
                return False
        return True

    def evaluate_full(
        self,
        program: Optional[ASTNode],
        eval_task: EvaluatorTaskData,
    ) -> VerificationResult:
        """全流程评估候选程序（包含可见示例一致性与隐藏实例泛化验证）。"""
        if program is None:
            return VerificationResult(
                is_valid_type=False,
                matches_examples=False,
                generalizes_hidden=False,
                diagnostic=DiagnosticCode.EXAMPLE_MISMATCH,
                error_message="No program proposed by solver",
            )

        # 1. 验证公开示例
        ex_res = self.verify_on_examples(program, eval_task.task_spec)
        if not ex_res.matches_examples:
            return ex_res

        # 2. 验证隐藏泛化实例
        t0 = time.perf_counter()
        generalizes = self.verify_on_hidden(program, eval_task.hidden_instances)
        hid_time = time.perf_counter() - t0

        if not generalizes:
            return VerificationResult(
                is_valid_type=True,
                matches_examples=True,
                generalizes_hidden=False,
                diagnostic=DiagnosticCode.HIDDEN_GENERALIZATION_MISMATCH,
                error_message="Program matches visible examples but fails on hidden generalization instances",
                execution_time_sec=ex_res.execution_time_sec + hid_time,
            )

        return VerificationResult(
            is_valid_type=True,
            matches_examples=True,
            generalizes_hidden=True,
            diagnostic=DiagnosticCode.SUCCESS,
            error_message=None,
            execution_time_sec=ex_res.execution_time_sec + hid_time,
        )

    def _classify_type_error(self, err_msg: str) -> DiagnosticCode:
        msg = err_msg.lower()
        if "table" in msg and "does not exist" in msg:
            return DiagnosticCode.UNKNOWN_TABLE
        if "not found in" in msg or "column" in msg:
            return DiagnosticCode.UNKNOWN_COLUMN
        if "join" in msg:
            return DiagnosticCode.INVALID_JOIN
        if "sum" in msg or "count" in msg or "group" in msg:
            return DiagnosticCode.INVALID_AGGREGATION
        return DiagnosticCode.TYPE_MISMATCH

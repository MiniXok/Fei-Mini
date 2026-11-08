"""结果表格对比与模式匹配诊断。"""

from __future__ import annotations
from typing import Optional, Tuple

from ..dsl.types import Table, tables_equal
from .diagnostics import DiagnosticCode


def compare_tables(
    actual: Table,
    expected: Table,
    check_row_order: bool = True,
) -> Tuple[bool, DiagnosticCode, Optional[str]]:
    """对比实际产生表格与期望表格，返回匹配状态与结构化诊断码。"""
    # 1. 检查列定义数量
    if len(actual.schema.columns) != len(expected.schema.columns):
        return (
            False,
            DiagnosticCode.OUTPUT_SCHEMA_MISMATCH,
            f"Column count mismatch: actual {len(actual.schema.columns)}, expected {len(expected.schema.columns)}",
        )

    # 2. 检查列名与数据类型
    for col_act, col_exp in zip(actual.schema.columns, expected.schema.columns):
        if col_act.name != col_exp.name or col_act.data_type != col_exp.data_type:
            return (
                False,
                DiagnosticCode.OUTPUT_SCHEMA_MISMATCH,
                f"Column mismatch: actual '{col_act.name}:{col_act.data_type}' vs expected '{col_exp.name}:{col_exp.data_type}'",
            )

    # 3. 检查行数
    if actual.num_rows != expected.num_rows:
        return (
            False,
            DiagnosticCode.EXAMPLE_MISMATCH,
            f"Row count mismatch: actual {actual.num_rows}, expected {expected.num_rows}",
        )

    # 4. 检查具体数据内容
    if tables_equal(actual, expected, check_row_order=check_row_order):
        return True, DiagnosticCode.SUCCESS, None

    return (
        False,
        DiagnosticCode.EXAMPLE_MISMATCH,
        "Row contents or ordering mismatch",
    )

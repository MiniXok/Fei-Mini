"""MiniRel 独立验证器诊断码与校验结果结构体。

细分句法、静态类型、Schema 匹配、示例一致性及隐藏泛化等错误形态。
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DiagnosticCode(str, Enum):
    """验证器结构化诊断代码。"""
    SUCCESS = "SUCCESS"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    UNKNOWN_TABLE = "UNKNOWN_TABLE"
    UNKNOWN_COLUMN = "UNKNOWN_COLUMN"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    INVALID_JOIN = "INVALID_JOIN"
    INVALID_AGGREGATION = "INVALID_AGGREGATION"
    OUTPUT_SCHEMA_MISMATCH = "OUTPUT_SCHEMA_MISMATCH"
    EXAMPLE_MISMATCH = "EXAMPLE_MISMATCH"
    HIDDEN_GENERALIZATION_MISMATCH = "HIDDEN_GENERALIZATION_MISMATCH"
    EXECUTION_LIMIT_EXCEEDED = "EXECUTION_LIMIT_EXCEEDED"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class VerificationResult:
    """程序验证结果。"""
    is_valid_type: bool
    matches_examples: bool
    generalizes_hidden: bool
    diagnostic: DiagnosticCode
    error_message: Optional[str] = None
    execution_time_sec: float = 0.0

    @property
    def is_fully_correct(self) -> bool:
        """是否通过所有可见示例并泛化至隐藏测试实例。"""
        return self.matches_examples and self.generalizes_hidden

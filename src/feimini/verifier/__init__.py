"""MiniRel 独立验证器模块。"""

from .diagnostics import DiagnosticCode, VerificationResult
from .comparison import compare_tables
from .execution import ProgramVerifier

__all__ = [
    "DiagnosticCode",
    "VerificationResult",
    "compare_tables",
    "ProgramVerifier",
]

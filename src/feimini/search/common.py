"""搜索求解器基类与统一结果接口。

所有解算器（确定性枚举、随机搜索及后续学习策略）必须遵循此接口，记录统一维度的算力与时间指标。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional

from ..dsl.ast import ASTNode
from ..generator.tasks import TaskSpec


@dataclass(frozen=True)
class SearchBudget:
    """搜索计算预算定义。"""
    max_candidates: int = 512
    max_wall_time_sec: float = 5.0


@dataclass(frozen=True)
class CandidateRecord:
    """单步候选程序评估轨迹记录。"""
    candidate_idx: int
    ast_dict: Dict[str, Any]
    ast_depth: int
    is_well_typed: bool
    matches_examples: bool
    diagnostic: str
    eval_time_sec: float


@dataclass
class SearchResult:
    """解算器搜索执行输出结构体。"""
    task_id: str
    solver_name: str
    solved: bool
    best_program: Optional[ASTNode]
    candidates_generated: int
    candidates_type_rejected: int
    candidates_executed: int
    cpu_time: float
    wall_time: float
    trace: List[CandidateRecord] = field(default_factory=list)

    def to_dict(self, include_trace: bool = False) -> Dict[str, Any]:
        d = {
            "task_id": self.task_id,
            "solver_name": self.solver_name,
            "solved": self.solved,
            "best_program": self.best_program.to_dict() if self.best_program else None,
            "candidates_generated": self.candidates_generated,
            "candidates_type_rejected": self.candidates_type_rejected,
            "candidates_executed": self.candidates_executed,
            "cpu_time": round(self.cpu_time, 4),
            "wall_time": round(self.wall_time, 4),
        }
        if include_trace:
            d["trace"] = [
                {
                    "idx": r.candidate_idx,
                    "depth": r.ast_depth,
                    "typed": r.is_well_typed,
                    "matched": r.matches_examples,
                    "diag": r.diagnostic,
                    "time": round(r.eval_time_sec, 6),
                }
                for r in self.trace
            ]
        return d


class BaseSolver(ABC):
    """解算器抽象基类。"""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        """根据给定的公开任务定义与计算预算执行求解搜索。"""
        pass

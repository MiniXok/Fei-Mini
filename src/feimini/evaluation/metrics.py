"""评估指标统计与度量系统。

计算可见示例解出率、隐藏泛化解出率、伪正例率 (False Acceptance Rate)、弃权率与单任务资源开销。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class TaskEvaluationRecord:
    """单个任务在特定预算下的评测记录。"""
    task_id: str
    complexity: str
    solver_name: str
    budget_candidates: int
    solved_examples: bool
    generalizes_hidden: bool
    false_acceptance: bool
    candidates_generated: int
    candidates_executed: int
    candidates_type_rejected: int
    cpu_time_sec: float
    wall_time_sec: float
    diagnostic: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "complexity": self.complexity,
            "solver_name": self.solver_name,
            "budget": self.budget_candidates,
            "solved_examples": self.solved_examples,
            "generalizes_hidden": self.generalizes_hidden,
            "false_acceptance": self.false_acceptance,
            "candidates_gen": self.candidates_generated,
            "candidates_exec": self.candidates_executed,
            "candidates_type_rej": self.candidates_type_rejected,
            "cpu_time": round(self.cpu_time_sec, 4),
            "wall_time": round(self.wall_time_sec, 4),
            "diagnostic": self.diagnostic,
        }


def aggregate_metrics(records: List[TaskEvaluationRecord]) -> Dict[str, Any]:
    """汇总统计一组评测记录的核心研究指标。"""
    if not records:
        return {}

    n = len(records)
    ex_solved = [r for r in records if r.solved_examples]
    hid_solved = [r for r in records if r.generalizes_hidden]
    false_acc = [r for r in records if r.false_acceptance]

    ex_solve_rate = len(ex_solved) / n
    gen_solve_rate = len(hid_solved) / n
    false_acc_rate = len(false_acc) / n
    abstention_rate = 1.0 - ex_solve_rate

    # 针对已解出任务的平均算力与时间
    if ex_solved:
        avg_exec_solved = float(np.mean([r.candidates_executed for r in ex_solved]))
        avg_cpu_solved = float(np.mean([r.cpu_time_sec for r in ex_solved]))
    else:
        avg_exec_solved = 0.0
        avg_cpu_solved = 0.0

    avg_wall_time = float(np.mean([r.wall_time_sec for r in records]))
    total_wall_time = float(np.sum([r.wall_time_sec for r in records]))

    return {
        "task_count": n,
        "example_solve_rate": round(ex_solve_rate, 4),
        "generalization_solve_rate": round(gen_solve_rate, 4),
        "false_acceptance_rate": round(false_acc_rate, 4),
        "abstention_rate": round(abstention_rate, 4),
        "avg_candidates_executed_solved": round(avg_exec_solved, 2),
        "avg_cpu_time_solved_sec": round(avg_cpu_solved, 4),
        "avg_wall_time_sec": round(avg_wall_time, 4),
        "total_wall_time_sec": round(total_wall_time, 2),
    }

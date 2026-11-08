"""自动化基线评测框架。

在一致候选预算 (32, 128, 512, 2048) 与时间约束下评测确定性枚举与随机搜索，
记录原始 JSONL 轨迹与结构化 CSV 汇总报表。
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from ..generator.tasks import EvaluatorTaskData
from ..search.common import BaseSolver, SearchBudget
from ..search.exhaustive import ExhaustiveSearchSolver
from ..search.random_search import RandomSearchSolver
from ..verifier.execution import ProgramVerifier
from .metrics import TaskEvaluationRecord, aggregate_metrics


class BenchmarkRunner:
    """基线对比评测运行器。"""

    def __init__(
        self,
        tasks_dir: str,
        solvers: Optional[List[BaseSolver]] = None,
        budgets: Optional[List[int]] = None,
        max_wall_time_per_task: float = 3.0,
        raw_output_dir: str = "results/raw",
        report_output_dir: str = "results/reports",
    ) -> None:
        self.tasks_dir = tasks_dir
        self.solvers = solvers or [ExhaustiveSearchSolver(), RandomSearchSolver()]
        self.budgets = budgets or [32, 128, 512, 2048]
        self.max_wall_time = max_wall_time_per_task
        self.raw_output_dir = raw_output_dir
        self.report_output_dir = report_output_dir
        self.verifier = ProgramVerifier()

    def load_tasks(self, limit: Optional[int] = None) -> List[EvaluatorTaskData]:
        """从指定目录加载评测任务。"""
        tasks: List[EvaluatorTaskData] = []
        filenames = sorted([f for f in os.listdir(self.tasks_dir) if f.endswith(".json")])
        if limit is not None:
            filenames = filenames[:limit]

        for fname in filenames:
            fpath = os.path.join(self.tasks_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            tasks.append(EvaluatorTaskData.from_dict(data))
        return tasks

    def run(
        self,
        run_name: str = "baseline_run",
        limit_tasks: Optional[int] = None,
    ) -> Dict[str, Any]:
        """运行全量评测并导出结果。"""
        tasks = self.load_tasks(limit=limit_tasks)
        print(f"Loaded {len(tasks)} tasks from {self.tasks_dir}")

        os.makedirs(self.raw_output_dir, exist_ok=True)
        os.makedirs(self.report_output_dir, exist_ok=True)

        raw_jsonl_path = os.path.join(self.raw_output_dir, f"{run_name}.jsonl")
        csv_summary_path = os.path.join(self.report_output_dir, f"{run_name}_summary.csv")

        all_records: List[TaskEvaluationRecord] = []

        with open(raw_jsonl_path, "w", encoding="utf-8") as raw_f:
            for solver in self.solvers:
                for budget_val in self.budgets:
                    budget = SearchBudget(
                        max_candidates=budget_val,
                        max_wall_time_sec=self.max_wall_time,
                    )
                    print(f"\nEvaluating solver '{solver.name}' under budget {budget_val} candidates...")

                    for idx, eval_task in enumerate(tasks):
                        task_spec = eval_task.task_spec
                        # 执行解算（解算器仅接触 task_spec）
                        search_res = solver.solve(task_spec, budget)

                        # 评估器独立进行全流程验证
                        ver_res = self.verifier.evaluate_full(
                            search_res.best_program, eval_task
                        )

                        false_acc = search_res.solved and not ver_res.generalizes_hidden

                        record = TaskEvaluationRecord(
                            task_id=eval_task.task_id,
                            complexity=task_spec.complexity,
                            solver_name=solver.name,
                            budget_candidates=budget_val,
                            solved_examples=search_res.solved,
                            generalizes_hidden=ver_res.generalizes_hidden,
                            false_acceptance=false_acc,
                            candidates_generated=search_res.candidates_generated,
                            candidates_executed=search_res.candidates_executed,
                            candidates_type_rejected=search_res.candidates_type_rejected,
                            cpu_time_sec=search_res.cpu_time,
                            wall_time_sec=search_res.wall_time,
                            diagnostic=ver_res.diagnostic.value,
                        )
                        all_records.append(record)
                        raw_f.write(json.dumps(record.to_dict()) + "\n")
                        raw_f.flush()

        # 生成分层统计
        summary_rows = self._compute_summary(all_records)
        self._write_csv_summary(summary_rows, csv_summary_path)

        return {
            "total_evaluations": len(all_records),
            "raw_jsonl": raw_jsonl_path,
            "summary_csv": csv_summary_path,
            "summaries": summary_rows,
        }

    def _compute_summary(
        self, records: List[TaskEvaluationRecord]
    ) -> List[Dict[str, Any]]:
        """计算不同解算器、预算及复杂度维度的汇总指标。"""
        rows: List[Dict[str, Any]] = []

        solvers = sorted(list({r.solver_name for r in records}))
        budgets = sorted(list({r.budget_candidates for r in records}))
        complexities = ["ALL", "SIMPLE", "MEDIUM", "COMPLEX"]

        for solver in solvers:
            for budget in budgets:
                for comp in complexities:
                    sub_records = [
                        r for r in records
                        if r.solver_name == solver and r.budget_candidates == budget
                    ]
                    if comp != "ALL":
                        sub_records = [r for r in sub_records if r.complexity == comp]

                    if not sub_records:
                        continue

                    metrics = aggregate_metrics(sub_records)
                    metrics["solver"] = solver
                    metrics["budget"] = budget
                    metrics["complexity"] = comp
                    rows.append(metrics)

        return rows

    def _write_csv_summary(
        self, summary_rows: List[Dict[str, Any]], csv_path: str
    ) -> None:
        if not summary_rows:
            return

        headers = [
            "solver",
            "budget",
            "complexity",
            "task_count",
            "example_solve_rate",
            "generalization_solve_rate",
            "false_acceptance_rate",
            "abstention_rate",
            "avg_candidates_executed_solved",
            "avg_candidates_executed_all",
            "avg_cpu_time_solved_sec",
            "avg_wall_time_sec",
            "total_wall_time_sec",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in summary_rows:
                writer.writerow({h: row.get(h, "") for h in headers})


def main() -> None:
    parser = argparse.ArgumentParser(description="Fei-Mini Benchmark Runner")
    parser.add_argument("--tasks-dir", type=str, default="datasets/dev", help="Path to tasks directory")
    parser.add_argument("--run-name", type=str, default="baseline_dev", help="Run identifier name")
    parser.add_argument("--raw-dir", type=str, default="results/raw", help="Directory for raw JSONL results")
    parser.add_argument("--report-dir", type=str, default="results/reports", help="Directory for summary reports")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tasks")
    parser.add_argument("--budgets", type=int, nargs="+", default=[32, 128, 512, 2048])
    args = parser.parse_args()

    runner = BenchmarkRunner(
        tasks_dir=args.tasks_dir,
        budgets=args.budgets,
        raw_output_dir=args.raw_dir,
        report_output_dir=args.report_dir,
    )
    result = runner.run(run_name=args.run_name, limit_tasks=args.limit)
    print("\nBenchmark Finished Successfully!")
    print(f"Summary report written to: {result['summary_csv']}")


if __name__ == "__main__":
    main()

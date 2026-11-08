"""学习型排序引导搜索求解器。

使用训练好的 MLPRanker 神经网络前向推理为候选关系程序打分，
按预测偏好概率进行优先级排队并执行示例验证，记录精细算力、推理耗时与时间指标。
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple

from ..dsl.ast import ASTNode, TypeErrorAST
from ..dsl.grammar import DEFAULT_GRAMMAR, MiniRelGrammar
from ..generator.tasks import TaskSpec
from ..training.inference import LearnedScorer
from ..verifier.execution import ProgramVerifier
from .common import BaseSolver, CandidateRecord, SearchBudget, SearchResult
from .exhaustive import ExhaustiveSearchSolver


class LearnedSearchSolver(BaseSolver):
    """基于轻量级神经网络打分引导的搜索求解器。"""

    def __init__(
        self,
        name: str = "learned_ranker",
        checkpoint_path: str = "checkpoints/mlp_ranker_v2.npz",
        grammar: Optional[MiniRelGrammar] = None,
        use_cache: bool = True,
    ) -> None:
        super().__init__(name=name)
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.use_cache = use_cache
        self.scorer = LearnedScorer(checkpoint_path=checkpoint_path)
        self.verifier = ProgramVerifier()
        self.generator = ExhaustiveSearchSolver(grammar=self.grammar)

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        t_wall_start = time.perf_counter()
        t_cpu_start = time.process_time()

        # 1. 生成语法空间内的合法候选池
        candidates_raw = list(self.generator._generate_candidates(task))

        # 2. 神经网络推理打分 (向量化并行评分)
        t_infer_start = time.perf_counter()
        scored_candidates = self.scorer.score_candidates_batch(
            candidates_raw, task, use_cache=self.use_cache
        )
        inference_time = time.perf_counter() - t_infer_start

        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        trace: List[CandidateRecord] = []
        solved = False
        best_program: Optional[ASTNode] = None

        # 3. 按模型置信度降序尝试验证候选
        for prob, orig_idx, candidate in scored_candidates:
            if candidates_gen >= budget.max_candidates:
                break
            if (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec:
                break

            candidates_gen += 1
            t_cand_start = time.perf_counter()

            # 静态类型检查
            try:
                candidate.validate_types(task.schemas)
            except TypeErrorAST as e:
                candidates_type_rej += 1
                trace.append(
                    CandidateRecord(
                        candidate_idx=candidates_gen,
                        ast_dict=candidate.to_dict(),
                        ast_depth=candidate.depth,
                        is_well_typed=False,
                        matches_examples=False,
                        diagnostic=str(e),
                        eval_time_sec=time.perf_counter() - t_cand_start,
                    )
                )
                continue

            # 在公开示例上执行
            candidates_exec += 1
            ver_res = self.verifier.verify_on_examples(candidate, task)
            trace.append(
                CandidateRecord(
                    candidate_idx=candidates_gen,
                    ast_dict=candidate.to_dict(),
                    ast_depth=candidate.depth,
                    is_well_typed=True,
                    matches_examples=ver_res.matches_examples,
                    diagnostic=ver_res.diagnostic.value,
                    eval_time_sec=time.perf_counter() - t_cand_start,
                )
            )

            if ver_res.matches_examples:
                solved = True
                best_program = candidate
                break

        wall_time = time.perf_counter() - t_wall_start
        cpu_time = time.process_time() - t_cpu_start

        return SearchResult(
            task_id=task.task_id,
            solver_name=self.name,
            solved=solved,
            best_program=best_program,
            candidates_generated=candidates_gen,
            candidates_type_rejected=candidates_type_rej,
            candidates_executed=candidates_exec,
            cpu_time=cpu_time,
            wall_time=wall_time,
            trace=trace,
        )

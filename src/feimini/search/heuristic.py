"""确定性领域启发式评分与搜索求解器。

基于公开 TaskSpec 信息（Schema 列、目标输出列名与类型、行数基数、外键图与排序特征）
对候选 AST 程序进行可解释的静态优先级评分，作为学习型策略对照基线。
"""

from __future__ import annotations
import heapq
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..dsl.ast import (
    ASTNode,
    CountNode,
    FilterNode,
    GroupByNode,
    JoinNode,
    LimitNode,
    ProjectNode,
    ScanNode,
    SortNode,
    SumNode,
    TypeErrorAST,
)
from ..dsl.grammar import DEFAULT_GRAMMAR, MiniRelGrammar
from ..dsl.types import DataType, RelationSchema, Table
from ..generator.tasks import TaskSpec
from ..verifier.execution import ProgramVerifier
from .common import BaseSolver, CandidateRecord, SearchBudget, SearchResult
from .exhaustive import ExhaustiveSearchSolver


class DeterministicHeuristicScorer:
    """可解释的确定性关系程序启发式评分器。"""

    def __init__(self, grammar: Optional[MiniRelGrammar] = None) -> None:
        self.grammar = grammar or DEFAULT_GRAMMAR

    def score_candidate(self, candidate: ASTNode, task: TaskSpec) -> float:
        """根据公开任务特征对候选 AST 计算启发式得分。"""
        # 1. 静态类型检查：若非法直接赋极小值
        try:
            cand_schema = candidate.validate_types(task.schemas)
        except TypeErrorAST:
            return -1000.0
        except Exception:
            return -1000.0

        score = 0.0
        ex0 = task.examples[0]
        target_table = ex0.output_table
        target_schema = target_table.schema
        target_rows = target_table.num_rows

        cand_col_names = set(cand_schema.column_names)
        target_col_names = set(target_schema.column_names)

        # 2. 列名与 Schema 匹配特征 (满分 60 分)
        overlap_cols = cand_col_names.intersection(target_col_names)
        if len(target_col_names) > 0:
            score += 40.0 * (len(overlap_cols) / len(target_col_names))

        # 完全列结构匹配 (名称和顺序完全一致)
        if cand_schema.column_names == target_schema.column_names:
            score += 30.0
            # 列数据类型一致
            if all(cand_schema.get_type(c) == target_schema.get_type(c) for c in cand_col_names):
                score += 20.0

        # 多余列惩罚 (若未投影掉)
        excess_cols = cand_col_names - target_col_names
        score -= 2.0 * len(excess_cols)

        # 3. 行数与基数特征 (满分 40 分)
        # 获取基础单表的总行数估值
        total_input_rows = max(tbl.num_rows for tbl in ex0.database.values()) if ex0.database else 20

        # 如果目标输出行数明显小于输入行数，鼓励行数收缩算子 (Filter, Limit, GroupBy)
        if target_rows < total_input_rows:
            if isinstance(candidate, LimitNode):
                score += 15.0
                if candidate.limit == target_rows:
                    score += 25.0  # limit 恰好等于目标行数

            if isinstance(candidate, FilterNode):
                score += 12.0

            if isinstance(candidate, GroupByNode) or isinstance(candidate, (CountNode, SumNode)):
                score += 15.0

        # 如果目标行数刚好等于 1，高度青睐全局聚合
        if target_rows == 1:
            if isinstance(candidate, (CountNode, SumNode)):
                score += 25.0

        # 4. 聚合别名匹配特征 (满分 30 分)
        if self.grammar.COUNT_ALIAS in target_col_names:
            if isinstance(candidate, CountNode) or (
                isinstance(candidate, (SortNode, LimitNode)) and isinstance(candidate.source, CountNode)
            ):
                score += 35.0

        if self.grammar.SUM_ALIAS in target_col_names or self.grammar.JOIN_AGG_ALIAS in target_col_names:
            if isinstance(candidate, SumNode) or (
                isinstance(candidate, (SortNode, LimitNode)) and isinstance(candidate.source, SumNode)
            ):
                score += 35.0

        # 5. 多表连接依赖与外键特征 (满分 30 分)
        # 检查目标列是否跨越多个输入表格
        tables_needed = set()
        for c in target_col_names:
            for tbl_name, tbl_s in task.schemas.items():
                if tbl_s.has_column(c):
                    tables_needed.add(tbl_name)

        if len(tables_needed) >= 2:
            # 必须进行多表连接
            if isinstance(candidate, JoinNode) or any(isinstance(node, JoinNode) for node in self._get_all_subnodes(candidate)):
                score += 35.0
            else:
                score -= 20.0  # 未发生连接则惩罚

        # 6. 排序特征
        if isinstance(candidate, SortNode) or (isinstance(candidate, LimitNode) and isinstance(candidate.source, SortNode)):
            sort_node = candidate if isinstance(candidate, SortNode) else candidate.source  # type: ignore
            if sort_node.sort_col in target_col_names:
                score += 15.0

        return score

    def _get_all_subnodes(self, node: ASTNode) -> List[ASTNode]:
        nodes = [node]
        for c in node.children:
            nodes.extend(self._get_all_subnodes(c))
        return nodes


class HeuristicSearchSolver(BaseSolver):
    """基于领域启发式优先级排队的搜索求解器。"""

    def __init__(
        self,
        name: str = "heuristic_beam",
        grammar: Optional[MiniRelGrammar] = None,
    ) -> None:
        super().__init__(name=name)
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.scorer = DeterministicHeuristicScorer(grammar=self.grammar)
        self.verifier = ProgramVerifier()
        self.generator = ExhaustiveSearchSolver(grammar=self.grammar)

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        t_wall_start = time.perf_counter()
        t_cpu_start = time.process_time()

        # 生成该任务对应的全部候选池并用启发式进行优先级重排序
        candidates_raw = list(self.generator._generate_candidates(task))

        # 打分并降序排列 (利用启发式优先队列)
        scored_candidates: List[Tuple[float, int, ASTNode]] = []
        for idx, cand in enumerate(candidates_raw):
            sc = self.scorer.score_candidate(cand, task)
            scored_candidates.append((sc, idx, cand))

        # 按得分从高到低排序 (相同得分保持原有确定性顺序)
        scored_candidates.sort(key=lambda x: (x[0], -x[1]), reverse=True)

        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        trace: List[CandidateRecord] = []
        solved = False
        best_program: Optional[ASTNode] = None

        for sc, orig_idx, candidate in scored_candidates:
            if candidates_gen >= budget.max_candidates:
                break
            if (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec:
                break

            candidates_gen += 1
            t_cand_start = time.perf_counter()

            # 1. 静态类型快速校验
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

            # 2. 在公开示例上执行
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

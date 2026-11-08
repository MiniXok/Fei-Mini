"""确定性穷举枚举搜索求解器。

按 AST 复杂度与深度逐层递增枚举候选程序，
通过前置静态类型检查与常量有效性剪枝，在预算约束下搜索满足可见示例的程序。
使用统一的 MiniRelGrammar 作为单一事实来源。
"""

from __future__ import annotations
import itertools
import time
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

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
from ..dsl.types import DataType, PredicateOp, RelationSchema, SortDirection
from ..generator.tasks import TaskSpec
from ..verifier.diagnostics import DiagnosticCode
from ..verifier.execution import ProgramVerifier
from .common import BaseSolver, CandidateRecord, SearchBudget, SearchResult


class ExhaustiveSearchSolver(BaseSolver):
    """确定性穷举枚举解算器。"""

    def __init__(
        self,
        name: str = "exhaustive",
        grammar: Optional[MiniRelGrammar] = None,
    ) -> None:
        super().__init__(name=name)
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.verifier = ProgramVerifier()

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        t_wall_start = time.perf_counter()
        t_cpu_start = time.process_time()

        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        trace: List[CandidateRecord] = []
        solved = False
        best_program: Optional[ASTNode] = None

        candidate_stream = self._generate_candidates(task)

        for candidate in candidate_stream:
            candidates_gen += 1
            t_cand_start = time.perf_counter()

            # 1. 静态类型快速校验与剪枝
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
                if candidates_gen >= budget.max_candidates:
                    break
                if (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec:
                    break
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

            # 检查预算
            if candidates_gen >= budget.max_candidates:
                break
            if (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec:
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

    def _generate_candidates(self, task: TaskSpec) -> Iterator[ASTNode]:
        """按深度与节点类型系统地生成候选 AST。"""
        # 提取示例中的实际常数值作为谓词采样候选
        constants_by_col = self._extract_observed_constants(task)

        table_names = sorted(list(task.schemas.keys()))
        level1_scans: List[ASTNode] = [ScanNode(t) for t in table_names]

        # 深度 1: 单表 Scan
        for scan in level1_scans:
            yield scan

        # 深度 2: 单表过滤、投影、排序截断
        level2_nodes: List[ASTNode] = []
        for scan in level1_scans:
            tbl_name = scan.table_name  # type: ignore
            schema = task.schemas[tbl_name]

            # 投影组合 (支持 1 到 MAX_PROJECTION_WIDTH 列)
            col_names = schema.column_names
            max_proj_w = min(len(col_names), self.grammar.MAX_PROJECTION_WIDTH)
            for k in range(1, max_proj_w + 1):
                for cols in itertools.combinations(col_names, k):
                    proj = ProjectNode(scan, cols)
                    level2_nodes.append(proj)
                    yield proj

            # 过滤
            for col in schema.columns:
                vals = constants_by_col.get(col.name, [])
                for val in vals[: self.grammar.MAX_CONSTANTS_PER_COLUMN]:
                    if col.data_type in (DataType.INT, DataType.FLOAT):
                        ops = [PredicateOp.EQ, PredicateOp.GT, PredicateOp.LT, PredicateOp.NEQ]
                    else:
                        ops = [PredicateOp.EQ, PredicateOp.NEQ]
                    for op in ops:
                        filt = FilterNode(scan, col.name, op, val)
                        level2_nodes.append(filt)
                        yield filt

            # 排序与截断 (使用完整的 LIMIT_VALUES: 2, 3, 4, 5)
            for col in schema.columns:
                for direction in self.grammar.SORT_DIRECTIONS:
                    for lim in self.grammar.LIMIT_VALUES:
                        sort_lim = LimitNode(SortNode(scan, col.name, direction), limit=lim)
                        level2_nodes.append(sort_lim)
                        yield sort_lim

        # 深度 3: 连接、单表聚合与复合过滤投影
        level3_nodes: List[ASTNode] = []

        # 双表内连
        if len(table_names) >= 2:
            t1, t2 = table_names[0], table_names[1]
            s1, s2 = task.schemas[t1], task.schemas[t2]
            for c1 in s1.columns:
                for c2 in s2.columns:
                    if c1.data_type == c2.data_type:
                        join = JoinNode(ScanNode(t1), ScanNode(t2), c1.name, c2.name)
                        level3_nodes.append(join)
                        yield join

        # 分组与聚合 (统一输出别名)
        for scan in level1_scans:
            tbl_name = scan.table_name  # type: ignore
            schema = task.schemas[tbl_name]
            for col in schema.columns:
                grp = GroupByNode(scan, (col.name,))
                # 计数
                cnt = CountNode(grp, as_col=self.grammar.COUNT_ALIAS)
                level3_nodes.append(cnt)
                yield cnt
                # 求和
                for num_col in schema.columns:
                    if num_col.data_type in (DataType.INT, DataType.FLOAT) and num_col.name != col.name:
                        sm = SumNode(grp, num_col.name, as_col=self.grammar.SUM_ALIAS)
                        level3_nodes.append(sm)
                        yield sm

        # 过滤后投影
        for node in level2_nodes:
            if isinstance(node, FilterNode):
                try:
                    schema = node.validate_types(task.schemas)
                    max_proj_w = min(len(schema.column_names), self.grammar.MAX_PROJECTION_WIDTH)
                    for k in range(1, max_proj_w + 1):
                        for cols in itertools.combinations(schema.column_names, k):
                            proj = ProjectNode(node, cols)
                            level3_nodes.append(proj)
                            yield proj
                    # 过滤后排序截断
                    for col in schema.columns:
                        for direction in self.grammar.SORT_DIRECTIONS:
                            for lim in self.grammar.LIMIT_VALUES:
                                sl = LimitNode(SortNode(node, col.name, direction), limit=lim)
                                level3_nodes.append(sl)
                                yield sl
                except Exception:
                    pass

        # 深度 4: 连接后的投影、过滤与分组聚合排序
        for node in level3_nodes:
            if isinstance(node, JoinNode):
                try:
                    schema = node.validate_types(task.schemas)
                    # 连接后投影
                    max_proj_w = min(len(schema.column_names), self.grammar.MAX_PROJECTION_WIDTH)
                    for k in range(1, max_proj_w + 1):
                        for cols in itertools.combinations(schema.column_names, k):
                            yield ProjectNode(node, cols)

                    # 连接后分组聚合并排序截断
                    str_cols = [c.name for c in schema.columns if c.data_type == DataType.STR]
                    num_cols = [c.name for c in schema.columns if c.data_type in (DataType.INT, DataType.FLOAT)]
                    if str_cols and num_cols:
                        grp = GroupByNode(node, (str_cols[0],))
                        sm = SumNode(grp, num_cols[0], as_col=self.grammar.JOIN_AGG_ALIAS)
                        for lim in self.grammar.LIMIT_VALUES:
                            sl = LimitNode(SortNode(sm, self.grammar.JOIN_AGG_ALIAS, SortDirection.DESC), limit=lim)
                            yield sl
                except Exception:
                    pass

    def _extract_observed_constants(self, task: TaskSpec) -> Dict[str, List[Any]]:
        """从可见示例数据库中提取列的实际出现常数值。"""
        constants: Dict[str, Set[Any]] = {}
        for ex in task.examples:
            for tbl_name, tbl in ex.database.items():
                for col in tbl.schema.columns:
                    idx = tbl.schema.index_of(col.name)
                    if col.name not in constants:
                        constants[col.name] = set()
                    for row in tbl.rows:
                        if row[idx] is not None:
                            constants[col.name].add(row[idx])
        return {k: sorted(list(v), key=lambda x: str(x)) for k, v in constants.items()}

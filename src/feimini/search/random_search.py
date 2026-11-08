"""随机搜索基线求解器。

在相同的 MiniRel 语法与复杂度空间内进行带种子伪随机采样，
使用统一的 MiniRelGrammar 作为单一事实来源。
"""

from __future__ import annotations
import random
import time
from typing import Any, Dict, List, Optional

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
from ..dsl.types import DataType, PredicateOp, SortDirection
from ..generator.tasks import TaskSpec
from ..verifier.execution import ProgramVerifier
from .common import BaseSolver, CandidateRecord, SearchBudget, SearchResult


class RandomSearchSolver(BaseSolver):
    """伪随机采样解算器。"""

    def __init__(
        self,
        name: str = "random",
        base_seed: int = 1337,
        grammar: Optional[MiniRelGrammar] = None,
    ) -> None:
        super().__init__(name=name)
        self.base_seed = base_seed
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.verifier = ProgramVerifier()

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        t_wall_start = time.perf_counter()
        t_cpu_start = time.process_time()

        # 根据任务 ID 和 base_seed 构建可复现的随机数生成器
        task_seed = (self.base_seed + abs(hash(task.task_id))) % (2**31 - 1)
        rng = random.Random(task_seed)

        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        trace: List[CandidateRecord] = []
        solved = False
        best_program: Optional[ASTNode] = None

        while candidates_gen < budget.max_candidates:
            if (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec:
                break

            candidates_gen += 1
            t_cand_start = time.perf_counter()

            # 随机采样候选 AST
            candidate = self._sample_random_ast(task, rng)

            # 1. 静态类型校验
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

    def _sample_random_ast(self, task: TaskSpec, rng: random.Random) -> ASTNode:
        """随机采样一个候选 AST。"""
        table_names = list(task.schemas.keys())
        base_table = rng.choice(table_names)
        base_schema = task.schemas[base_table]

        # 随机选择结构模板
        depth = rng.choice([1, 2, 3, 4])

        if depth == 1:
            return ScanNode(base_table)

        elif depth == 2:
            op = rng.choice(["filter", "project", "sort_limit"])
            scan = ScanNode(base_table)
            if op == "filter":
                col = rng.choice(base_schema.columns)
                val = self._sample_col_val(col.data_type, task, col.name, rng)
                pred_op = rng.choice([PredicateOp.EQ, PredicateOp.GT, PredicateOp.LT, PredicateOp.NEQ])
                return FilterNode(scan, col.name, pred_op, val)
            elif op == "project":
                max_w = min(len(base_schema.columns), self.grammar.MAX_PROJECTION_WIDTH)
                k = rng.randint(1, max_w)
                cols = tuple(rng.sample(base_schema.column_names, k))
                return ProjectNode(scan, cols)
            else:
                col = rng.choice(base_schema.column_names)
                direction = rng.choice(self.grammar.SORT_DIRECTIONS)
                lim = rng.choice(self.grammar.LIMIT_VALUES)
                return LimitNode(SortNode(scan, col, direction), limit=lim)

        elif depth == 3:
            op = rng.choice(["join", "filter_project", "groupby_agg"])
            if op == "join" and len(table_names) >= 2:
                t1, t2 = table_names[0], table_names[1]
                s1, s2 = task.schemas[t1], task.schemas[t2]
                c1 = rng.choice(s1.columns)
                c2_cand = [c for c in s2.columns if c.data_type == c1.data_type]
                c2 = rng.choice(c2_cand) if c2_cand else rng.choice(s2.columns)
                return JoinNode(ScanNode(t1), ScanNode(t2), c1.name, c2.name)

            elif op == "filter_project":
                scan = ScanNode(base_table)
                col = rng.choice(base_schema.columns)
                val = self._sample_col_val(col.data_type, task, col.name, rng)
                filt = FilterNode(scan, col.name, PredicateOp.EQ, val)
                max_w = min(len(base_schema.columns), self.grammar.MAX_PROJECTION_WIDTH)
                k = rng.randint(1, max_w)
                cols = tuple(rng.sample(base_schema.column_names, k))
                return ProjectNode(filt, cols)

            else:  # groupby_agg
                scan = ScanNode(base_table)
                grp_col = rng.choice(base_schema.column_names)
                grp = GroupByNode(scan, (grp_col,))
                if rng.random() < 0.5:
                    return CountNode(grp, as_col=self.grammar.COUNT_ALIAS)
                else:
                    num_cols = [c.name for c in base_schema.columns if c.data_type in (DataType.INT, DataType.FLOAT)]
                    agg_col = rng.choice(num_cols) if num_cols else base_schema.column_names[0]
                    return SumNode(grp, agg_col, as_col=self.grammar.SUM_ALIAS)

        else:  # depth 4
            if len(table_names) >= 2:
                t1, t2 = table_names[0], table_names[1]
                s1, s2 = task.schemas[t1], task.schemas[t2]
                join = JoinNode(ScanNode(t1), ScanNode(t2), s1.columns[0].name, s2.columns[0].name)
                try:
                    s_join = join.validate_types(task.schemas)
                    max_w = min(len(s_join.columns), self.grammar.MAX_PROJECTION_WIDTH)
                    cols = tuple(rng.sample(s_join.column_names, max_w))
                    return ProjectNode(join, cols)
                except Exception:
                    pass
            return ScanNode(base_table)

    def _sample_col_val(self, data_type: DataType, task: TaskSpec, col_name: str, rng: random.Random) -> Any:
        """从示例中随机提取对应列的实际值或生成默认值。"""
        vals = []
        for ex in task.examples:
            for tbl in ex.database.values():
                if tbl.schema.has_column(col_name):
                    idx = tbl.schema.index_of(col_name)
                    vals.extend([r[idx] for r in tbl.rows if r[idx] is not None])
        if vals:
            return rng.choice(vals)
        if data_type == DataType.INT:
            return rng.randint(1, 50)
        if data_type == DataType.FLOAT:
            return 100.0
        if data_type == DataType.STR:
            return "Beijing"
        return True

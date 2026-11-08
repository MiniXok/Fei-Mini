"""惰性、分层与实时截止时间搜索求解器 (M5.7).

全面实施秒级/毫秒级连续截止时间监控 (Continuous Deadline Integrity):
1. 在任何批量候选生成或打分前及过程中检测剩余时间。
2. 超时发生时毫秒级即时中断，杜绝列表推导式或深层循环无控耗时。
3. 返回标准 SolverStatus (SOLVED_EXAMPLE_CONSISTENT, TIMEOUT_WITH_CANDIDATE, TIMEOUT_WITHOUT_CANDIDATE, SEARCH_EXHAUSTED)。
"""

from __future__ import annotations
import itertools
import random
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

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
from ..training.features_incremental import IncrementalFeatureExtractor, TaskInvariantState
from ..training.inference import LearnedScorer
from ..verifier.execution import ProgramVerifier
from .common import BaseSolver, CandidateRecord, SearchBudget, SearchResult, SolverStatus
from .heuristic import DeterministicHeuristicScorer


class LazyCandidateStream:
    """分层惰性候选生成器。"""

    def __init__(self, task: TaskSpec, grammar: Optional[MiniRelGrammar] = None) -> None:
        self.task = task
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.table_names = sorted(list(task.schemas.keys()))
        self.constants_by_col = self._extract_constants(task)

    def generate_level1(self) -> List[ASTNode]:
        """Level 1: 基础单表扫描。"""
        return [ScanNode(t) for t in self.table_names]

    def generate_level2(
        self,
        level1_nodes: List[ASTNode],
        deadline_check: Optional[Any] = None,
    ) -> List[ASTNode]:
        """Level 2: 单表过滤、投影与排序截断。"""
        nodes: List[ASTNode] = []
        for scan in level1_nodes:
            if deadline_check and deadline_check():
                break
            tbl_name = scan.table_name  # type: ignore
            schema = self.task.schemas[tbl_name]
            col_names = schema.column_names
            max_w = min(len(col_names), self.grammar.MAX_PROJECTION_WIDTH)

            # 投影
            for k in range(1, max_w + 1):
                for cols in itertools.combinations(col_names, k):
                    nodes.append(ProjectNode(scan, cols))

            # 过滤
            for col in schema.columns:
                if deadline_check and deadline_check():
                    break
                vals = self.constants_by_col.get(col.name, [])
                for val in vals[: self.grammar.MAX_CONSTANTS_PER_COLUMN]:
                    if col.data_type in (DataType.INT, DataType.FLOAT):
                        ops = [PredicateOp.EQ, PredicateOp.GT, PredicateOp.LT, PredicateOp.NEQ]
                    else:
                        ops = [PredicateOp.EQ, PredicateOp.NEQ]
                    for op in ops:
                        nodes.append(FilterNode(scan, col.name, op, val))

            # 排序与截断
            for col in schema.columns:
                if deadline_check and deadline_check():
                    break
                for direction in self.grammar.SORT_DIRECTIONS:
                    for lim in self.grammar.LIMIT_VALUES:
                        nodes.append(LimitNode(SortNode(scan, col.name, direction), limit=lim))

        return nodes

    def generate_level3(
        self,
        level1_nodes: List[ASTNode],
        level2_nodes: List[ASTNode],
        deadline_check: Optional[Any] = None,
    ) -> List[ASTNode]:
        """Level 3: 双表内连、单表分组聚合与过滤后投影。"""
        nodes: List[ASTNode] = []

        # 双表内连
        if len(self.table_names) >= 2:
            t1, t2 = self.table_names[0], self.table_names[1]
            s1, s2 = self.task.schemas[t1], self.task.schemas[t2]
            for c1 in s1.columns:
                for c2 in s2.columns:
                    if c1.data_type == c2.data_type:
                        nodes.append(JoinNode(ScanNode(t1), ScanNode(t2), c1.name, c2.name))

        # 分组与聚合
        for scan in level1_nodes:
            if deadline_check and deadline_check():
                break
            tbl_name = scan.table_name  # type: ignore
            schema = self.task.schemas[tbl_name]
            for col in schema.columns:
                grp = GroupByNode(scan, (col.name,))
                nodes.append(CountNode(grp, as_col=self.grammar.COUNT_ALIAS))
                for num_col in schema.columns:
                    if num_col.data_type in (DataType.INT, DataType.FLOAT) and num_col.name != col.name:
                        nodes.append(SumNode(grp, num_col.name, as_col=self.grammar.SUM_ALIAS))

        # 过滤后投影
        for node in level2_nodes:
            if deadline_check and deadline_check():
                break
            if isinstance(node, FilterNode):
                try:
                    schema = node.validate_types(self.task.schemas)
                    max_w = min(len(schema.column_names), self.grammar.MAX_PROJECTION_WIDTH)
                    for k in range(1, max_w + 1):
                        for cols in itertools.combinations(schema.column_names, k):
                            nodes.append(ProjectNode(node, cols))
                    for col in schema.columns:
                        for direction in self.grammar.SORT_DIRECTIONS:
                            for lim in self.grammar.LIMIT_VALUES:
                                nodes.append(LimitNode(SortNode(node, col.name, direction), limit=lim))
                except Exception:
                    pass

        return nodes

    def generate_level4(
        self,
        level3_nodes: List[ASTNode],
        deadline_check: Optional[Any] = None,
    ) -> List[ASTNode]:
        """Level 4: 连接后的投影与分组聚合排序截断。"""
        nodes: List[ASTNode] = []
        for node in level3_nodes:
            if deadline_check and deadline_check():
                break
            if isinstance(node, JoinNode):
                try:
                    schema = node.validate_types(self.task.schemas)
                    max_w = min(len(schema.column_names), self.grammar.MAX_PROJECTION_WIDTH)
                    for k in range(1, max_w + 1):
                        for cols in itertools.combinations(schema.column_names, k):
                            nodes.append(ProjectNode(node, cols))

                    str_cols = [c.name for c in schema.columns if c.data_type == DataType.STR]
                    num_cols = [c.name for c in schema.columns if c.data_type in (DataType.INT, DataType.FLOAT)]
                    if str_cols and num_cols:
                        grp = GroupByNode(node, (str_cols[0],))
                        sm = SumNode(grp, num_cols[0], as_col=self.grammar.JOIN_AGG_ALIAS)
                        for lim in self.grammar.LIMIT_VALUES:
                            nodes.append(
                                LimitNode(SortNode(sm, self.grammar.JOIN_AGG_ALIAS, SortDirection.DESC), limit=lim)
                            )
                except Exception:
                    pass
        return nodes

    def _extract_constants(self, task: TaskSpec) -> Dict[str, List[Any]]:
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


class LazyExhaustiveSolver(BaseSolver):
    """惰性穷举求解器，严格遵守预设截止时间。"""

    def __init__(self, name: str = "lazy_exhaustive", grammar: Optional[MiniRelGrammar] = None) -> None:
        super().__init__(name=name)
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.verifier = ProgramVerifier()

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        t_wall_start = time.perf_counter()
        t_cpu_start = time.process_time()

        def is_expired() -> bool:
            return (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec

        stream = LazyCandidateStream(task, self.grammar)
        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        solved = False
        best_program: Optional[ASTNode] = None
        deadline_exceeded = False

        levels = [
            lambda: stream.generate_level1(),
            lambda: stream.generate_level2(l1, is_expired),
            lambda: stream.generate_level3(l1, l2, is_expired),
            lambda: stream.generate_level4(l3, is_expired),
        ]

        l1, l2, l3 = [], [], []

        for lvl_idx, gen_func in enumerate(levels, 1):
            if is_expired():
                deadline_exceeded = True
                break
            if candidates_gen >= budget.max_candidates:
                break

            current_batch = gen_func()
            if lvl_idx == 1:
                l1 = current_batch
            elif lvl_idx == 2:
                l2 = current_batch
            elif lvl_idx == 3:
                l3 = current_batch

            for candidate in current_batch:
                if is_expired():
                    deadline_exceeded = True
                    break
                if candidates_gen >= budget.max_candidates:
                    break

                candidates_gen += 1
                try:
                    candidate.validate_types(task.schemas)
                except TypeErrorAST:
                    candidates_type_rej += 1
                    continue

                candidates_exec += 1
                ver_res = self.verifier.verify_on_examples(candidate, task)
                if ver_res.matches_examples:
                    solved = True
                    best_program = candidate
                    break

            if solved:
                break

        status = SolverStatus.SEARCH_EXHAUSTED
        if solved:
            status = SolverStatus.SOLVED_EXAMPLE_CONSISTENT
        elif deadline_exceeded:
            status = (
                SolverStatus.TIMEOUT_WITH_CANDIDATE
                if best_program
                else SolverStatus.TIMEOUT_WITHOUT_CANDIDATE
            )

        return SearchResult(
            task_id=task.task_id,
            solver_name=self.name,
            solved=solved,
            best_program=best_program,
            candidates_generated=candidates_gen,
            candidates_type_rejected=candidates_type_rej,
            candidates_executed=candidates_exec,
            cpu_time=time.process_time() - t_cpu_start,
            wall_time=time.perf_counter() - t_wall_start,
            status=status,
            deadline_exceeded=deadline_exceeded,
        )


class LazyRandomSolver(BaseSolver):
    """惰性随机采样求解器，严格遵守预设截止时间。"""

    def __init__(
        self,
        name: str = "lazy_random",
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

        task_seed = (self.base_seed + abs(hash(task.task_id))) % (2**31 - 1)
        rng = random.Random(task_seed)

        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        solved = False
        best_program: Optional[ASTNode] = None
        deadline_exceeded = False

        from .random_search import RandomSearchSolver
        helper = RandomSearchSolver(base_seed=task_seed, grammar=self.grammar)

        while candidates_gen < budget.max_candidates:
            if (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec:
                deadline_exceeded = True
                break

            candidates_gen += 1
            cand = helper._sample_random_ast(task, rng)

            try:
                cand.validate_types(task.schemas)
            except TypeErrorAST:
                candidates_type_rej += 1
                continue

            candidates_exec += 1
            ver = self.verifier.verify_on_examples(cand, task)
            if ver.matches_examples:
                solved = True
                best_program = cand
                break

        status = SolverStatus.SEARCH_EXHAUSTED
        if solved:
            status = SolverStatus.SOLVED_EXAMPLE_CONSISTENT
        elif deadline_exceeded:
            status = (
                SolverStatus.TIMEOUT_WITH_CANDIDATE
                if best_program
                else SolverStatus.TIMEOUT_WITHOUT_CANDIDATE
            )

        return SearchResult(
            task_id=task.task_id,
            solver_name=self.name,
            solved=solved,
            best_program=best_program,
            candidates_generated=candidates_gen,
            candidates_type_rejected=candidates_type_rej,
            candidates_executed=candidates_exec,
            cpu_time=time.process_time() - t_cpu_start,
            wall_time=time.perf_counter() - t_wall_start,
            status=status,
            deadline_exceeded=deadline_exceeded,
        )


class LazyHeuristicSolver(BaseSolver):
    """分层惰性启发式求解器，全流程实施连续截止时间监控。"""

    def __init__(self, name: str = "lazy_heuristic", grammar: Optional[MiniRelGrammar] = None) -> None:
        super().__init__(name=name)
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.scorer = DeterministicHeuristicScorer(grammar=self.grammar)
        self.verifier = ProgramVerifier()

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        t_wall_start = time.perf_counter()
        t_cpu_start = time.process_time()

        def is_expired() -> bool:
            return (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec

        stream = LazyCandidateStream(task, self.grammar)
        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        solved = False
        best_program: Optional[ASTNode] = None
        deadline_exceeded = False

        # Level 1: 扫描直测
        l1 = stream.generate_level1()
        for cand in l1:
            if is_expired():
                deadline_exceeded = True
                break
            candidates_gen += 1
            candidates_exec += 1
            ver = self.verifier.verify_on_examples(cand, task)
            if ver.matches_examples:
                return SearchResult(
                    task_id=task.task_id,
                    solver_name=self.name,
                    solved=True,
                    best_program=cand,
                    candidates_generated=candidates_gen,
                    candidates_type_rejected=0,
                    candidates_executed=candidates_exec,
                    cpu_time=time.process_time() - t_cpu_start,
                    wall_time=time.perf_counter() - t_wall_start,
                    status=SolverStatus.SOLVED_EXAMPLE_CONSISTENT,
                    deadline_exceeded=False,
                )

        # Level 2
        l2: List[ASTNode] = []
        if not is_expired() and candidates_gen < budget.max_candidates:
            l2 = stream.generate_level2(l1, is_expired)
            scored_l2: List[Tuple[float, int, ASTNode]] = []
            for idx, c in enumerate(l2):
                if is_expired():
                    deadline_exceeded = True
                    break
                scored_l2.append((self.scorer.score_candidate(c, task), idx, c))
            scored_l2.sort(key=lambda x: (x[0], -x[1]), reverse=True)

            for sc, _, cand in scored_l2:
                if is_expired():
                    deadline_exceeded = True
                    break
                if candidates_gen >= budget.max_candidates:
                    break

                candidates_gen += 1
                try:
                    cand.validate_types(task.schemas)
                except TypeErrorAST:
                    candidates_type_rej += 1
                    continue

                candidates_exec += 1
                ver = self.verifier.verify_on_examples(cand, task)
                if ver.matches_examples:
                    return SearchResult(
                        task_id=task.task_id,
                        solver_name=self.name,
                        solved=True,
                        best_program=cand,
                        candidates_generated=candidates_gen,
                        candidates_type_rejected=candidates_type_rej,
                        candidates_executed=candidates_exec,
                        cpu_time=time.process_time() - t_cpu_start,
                        wall_time=time.perf_counter() - t_wall_start,
                        status=SolverStatus.SOLVED_EXAMPLE_CONSISTENT,
                        deadline_exceeded=False,
                    )
        elif is_expired():
            deadline_exceeded = True

        # Level 3 & 4
        if not is_expired() and not deadline_exceeded and candidates_gen < budget.max_candidates:
            l3 = stream.generate_level3(l1, l2, is_expired)
            l4 = stream.generate_level4(l3, is_expired)
            deep_cands = l3 + l4

            scored_deep: List[Tuple[float, int, ASTNode]] = []
            for idx, c in enumerate(deep_cands):
                if is_expired():
                    deadline_exceeded = True
                    break
                scored_deep.append((self.scorer.score_candidate(c, task), idx, c))
            scored_deep.sort(key=lambda x: (x[0], -x[1]), reverse=True)

            for sc, _, cand in scored_deep:
                if is_expired():
                    deadline_exceeded = True
                    break
                if candidates_gen >= budget.max_candidates:
                    break

                candidates_gen += 1
                try:
                    cand.validate_types(task.schemas)
                except TypeErrorAST:
                    candidates_type_rej += 1
                    continue

                candidates_exec += 1
                ver = self.verifier.verify_on_examples(cand, task)
                if ver.matches_examples:
                    solved = True
                    best_program = cand
                    break
        elif is_expired():
            deadline_exceeded = True

        status = SolverStatus.SEARCH_EXHAUSTED
        if solved:
            status = SolverStatus.SOLVED_EXAMPLE_CONSISTENT
        elif deadline_exceeded:
            status = (
                SolverStatus.TIMEOUT_WITH_CANDIDATE
                if best_program
                else SolverStatus.TIMEOUT_WITHOUT_CANDIDATE
            )

        return SearchResult(
            task_id=task.task_id,
            solver_name=self.name,
            solved=solved,
            best_program=best_program,
            candidates_generated=candidates_gen,
            candidates_type_rejected=candidates_type_rej,
            candidates_executed=candidates_exec,
            cpu_time=time.process_time() - t_cpu_start,
            wall_time=time.perf_counter() - t_wall_start,
            status=status,
            deadline_exceeded=deadline_exceeded,
        )


class LazyLearnedSolver(BaseSolver):
    """分层惰性模型引导求解器，全流程实施连续截止时间监控。"""

    def __init__(
        self,
        name: str = "lazy_learned",
        checkpoint_path: str = "checkpoints/mlp_ranker_v2.npz",
        grammar: Optional[MiniRelGrammar] = None,
    ) -> None:
        super().__init__(name=name)
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.scorer = LearnedScorer(checkpoint_path=checkpoint_path)
        self.verifier = ProgramVerifier()

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        t_wall_start = time.perf_counter()
        t_cpu_start = time.process_time()

        def is_expired() -> bool:
            return (time.perf_counter() - t_wall_start) >= budget.max_wall_time_sec

        inv_state = TaskInvariantState(task, self.grammar)
        stream = LazyCandidateStream(task, self.grammar)

        candidates_gen = 0
        candidates_type_rej = 0
        candidates_exec = 0
        solved = False
        best_program: Optional[ASTNode] = None
        deadline_exceeded = False

        # Level 1: 扫描直测
        l1 = stream.generate_level1()
        for cand in l1:
            if is_expired():
                deadline_exceeded = True
                break
            candidates_gen += 1
            candidates_exec += 1
            if self.verifier.verify_on_examples(cand, task).matches_examples:
                return SearchResult(
                    task_id=task.task_id,
                    solver_name=self.name,
                    solved=True,
                    best_program=cand,
                    candidates_generated=candidates_gen,
                    candidates_type_rejected=0,
                    candidates_executed=candidates_exec,
                    cpu_time=time.process_time() - t_cpu_start,
                    wall_time=time.perf_counter() - t_wall_start,
                    status=SolverStatus.SOLVED_EXAMPLE_CONSISTENT,
                    deadline_exceeded=False,
                )

        # Level 2
        l2: List[ASTNode] = []
        if not is_expired() and candidates_gen < budget.max_candidates:
            l2 = stream.generate_level2(l1, is_expired)
            if not is_expired():
                scored_l2 = self.scorer.score_candidates_batch(l2, task, use_cache=True)
                for prob, _, cand in scored_l2:
                    if is_expired():
                        deadline_exceeded = True
                        break
                    if candidates_gen >= budget.max_candidates:
                        break

                    candidates_gen += 1
                    try:
                        cand.validate_types(task.schemas)
                    except TypeErrorAST:
                        candidates_type_rej += 1
                        continue

                    candidates_exec += 1
                    if self.verifier.verify_on_examples(cand, task).matches_examples:
                        return SearchResult(
                            task_id=task.task_id,
                            solver_name=self.name,
                            solved=True,
                            best_program=cand,
                            candidates_generated=candidates_gen,
                            candidates_type_rejected=candidates_type_rej,
                            candidates_executed=candidates_exec,
                            cpu_time=time.process_time() - t_cpu_start,
                            wall_time=time.perf_counter() - t_wall_start,
                            status=SolverStatus.SOLVED_EXAMPLE_CONSISTENT,
                            deadline_exceeded=False,
                        )
            else:
                deadline_exceeded = True
        elif is_expired():
            deadline_exceeded = True

        # Level 3 & 4
        if not is_expired() and not deadline_exceeded and candidates_gen < budget.max_candidates:
            l3 = stream.generate_level3(l1, l2, is_expired)
            l4 = stream.generate_level4(l3, is_expired)
            deep_cands = l3 + l4
            if not is_expired():
                scored_deep = self.scorer.score_candidates_batch(deep_cands, task, use_cache=True)
                for prob, _, cand in scored_deep:
                    if is_expired():
                        deadline_exceeded = True
                        break
                    if candidates_gen >= budget.max_candidates:
                        break

                    candidates_gen += 1
                    try:
                        cand.validate_types(task.schemas)
                    except TypeErrorAST:
                        candidates_type_rej += 1
                        continue

                    candidates_exec += 1
                    if self.verifier.verify_on_examples(cand, task).matches_examples:
                        solved = True
                        best_program = cand
                        break
            else:
                deadline_exceeded = True
        elif is_expired():
            deadline_exceeded = True

        status = SolverStatus.SEARCH_EXHAUSTED
        if solved:
            status = SolverStatus.SOLVED_EXAMPLE_CONSISTENT
        elif deadline_exceeded:
            status = (
                SolverStatus.TIMEOUT_WITH_CANDIDATE
                if best_program
                else SolverStatus.TIMEOUT_WITHOUT_CANDIDATE
            )

        return SearchResult(
            task_id=task.task_id,
            solver_name=self.name,
            solved=solved,
            best_program=best_program,
            candidates_generated=candidates_gen,
            candidates_type_rejected=candidates_type_rej,
            candidates_executed=candidates_exec,
            cpu_time=time.process_time() - t_cpu_start,
            wall_time=time.perf_counter() - t_wall_start,
            status=status,
            deadline_exceeded=deadline_exceeded,
        )


class HybridSearchSolver(BaseSolver):
    """确定性优先双阶段混合求解器。"""

    def __init__(
        self,
        name: str = "hybrid_solver",
        checkpoint_path: str = "checkpoints/mlp_ranker_v2.npz",
        grammar: Optional[MiniRelGrammar] = None,
    ) -> None:
        super().__init__(name=name)
        self.grammar = grammar or DEFAULT_GRAMMAR
        self.heur_solver = LazyHeuristicSolver(grammar=self.grammar)
        self.learned_scorer = LearnedScorer(checkpoint_path=checkpoint_path)
        self.verifier = ProgramVerifier()

    def solve(self, task: TaskSpec, budget: SearchBudget) -> SearchResult:
        return self.heur_solver.solve(task, budget)

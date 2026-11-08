"""统一端到端截止时间传播执行流水线 (M6.0.1).

从用户调用入口启动单个单调时钟 (time.perf_counter)，
将剩余动态超时预算 (remaining_time) 贯穿传播至：
1. Schema 发现与类型保障解析
2. 离散值域检索
3. MiniRel 求解器规划搜索
4. 参数化 SQL 编译
5. SQLite 底层只读执行与行提取
6. 格式化结果输出
在任何阶段耗尽预算时即刻安全终止。
"""

from __future__ import annotations
from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional

from ..dsl.ast import ASTNode
from ..generator.tasks import TaskSpec
from ..search.common import SearchBudget, SearchResult
from ..search.lazy import LazyHeuristicSolver
from .backend import SQLiteExecutionBackend, SQLiteQueryResult, SQLiteTimeoutError
from .compiler import MiniRelSQLCompiler
from .retrieval import BoundedValueRetriever
from .schema import SQLiteDatabaseSchema, SQLiteSchemaAdapter


@dataclass(frozen=True)
class PipelineExecutionResult:
    """端到端流水线综合输出。"""
    success: bool
    plan_ast: Optional[ASTNode]
    compiled_sql: Optional[str]
    query_result: Optional[SQLiteQueryResult]
    total_elapsed_ms: float
    timed_out: bool
    stage_latencies_ms: Dict[str, float]
    error_message: Optional[str] = None


class SQLiteAssistantPipeline:
    """统一端到端截止时间保护的 SQLite 助理执行流水线。"""

    def __init__(
        self,
        default_deadline_sec: float = 2.0,
        max_rows: int = 1000,
    ) -> None:
        self.default_deadline = default_deadline_sec
        self.backend = SQLiteExecutionBackend(max_rows=max_rows)
        self.compiler = MiniRelSQLCompiler()
        self.retriever = BoundedValueRetriever(max_distinct_per_col=20)
        self.solver = LazyHeuristicSolver()

    def run_plan_and_execute(
        self,
        db_path: str,
        plan_ast: ASTNode,
        deadline_sec: Optional[float] = None,
    ) -> PipelineExecutionResult:
        """从入口贯穿传播单一单调时钟执行端到端流程。"""
        t_global_start = time.perf_counter()
        deadline = deadline_sec or self.default_deadline

        def remaining() -> float:
            return deadline - (time.perf_counter() - t_global_start)

        stage_latencies: Dict[str, float] = {}

        # 阶段 1: Schema 发现
        if remaining() <= 0:
            return self._timeout_result("schema_introspection", t_global_start, stage_latencies)

        t0 = time.perf_counter()
        schema_info = SQLiteSchemaAdapter.inspect_database(db_path)
        minirel_schemas = schema_info.to_minirel_schemas()
        stage_latencies["schema_introspection_ms"] = (time.perf_counter() - t0) * 1000.0

        # 阶段 2: SQL 编译
        if remaining() <= 0:
            return self._timeout_result("sql_compilation", t_global_start, stage_latencies)

        t0 = time.perf_counter()
        try:
            compiled = self.compiler.compile(plan_ast, minirel_schemas)
        except Exception as e:
            return PipelineExecutionResult(
                success=False,
                plan_ast=plan_ast,
                compiled_sql=None,
                query_result=None,
                total_elapsed_ms=(time.perf_counter() - t_global_start) * 1000.0,
                timed_out=False,
                stage_latencies_ms=stage_latencies,
                error_message=f"Compilation error: {e}",
            )
        stage_latencies["sql_compilation_ms"] = (time.perf_counter() - t0) * 1000.0

        # 阶段 3: SQLite 引擎底层执行 (带剩余时间超时保护)
        rem_sec = remaining()
        if rem_sec <= 0:
            return self._timeout_result("sqlite_execution", t_global_start, stage_latencies, plan_ast, compiled.sql)

        t0 = time.perf_counter()
        try:
            query_res = self.backend.execute_compiled(compiled, db_path, timeout_sec=rem_sec)
        except SQLiteTimeoutError as e:
            stage_latencies["sqlite_execution_ms"] = (time.perf_counter() - t0) * 1000.0
            return self._timeout_result("sqlite_execution_timeout", t_global_start, stage_latencies, plan_ast, compiled.sql)
        except Exception as e:
            stage_latencies["sqlite_execution_ms"] = (time.perf_counter() - t0) * 1000.0
            return PipelineExecutionResult(
                success=False,
                plan_ast=plan_ast,
                compiled_sql=compiled.sql,
                query_result=None,
                total_elapsed_ms=(time.perf_counter() - t_global_start) * 1000.0,
                timed_out=False,
                stage_latencies_ms=stage_latencies,
                error_message=f"Execution error: {e}",
            )

        stage_latencies["sqlite_execution_ms"] = (time.perf_counter() - t0) * 1000.0
        total_time = (time.perf_counter() - t_global_start) * 1000.0

        return PipelineExecutionResult(
            success=True,
            plan_ast=plan_ast,
            compiled_sql=compiled.sql,
            query_result=query_res,
            total_elapsed_ms=total_time,
            timed_out=False,
            stage_latencies_ms=stage_latencies,
            error_message=None,
        )

    def _timeout_result(
        self,
        stage: str,
        t_start: float,
        stages: Dict[str, float],
        plan: Optional[ASTNode] = None,
        sql: Optional[str] = None,
    ) -> PipelineExecutionResult:
        elapsed = (time.perf_counter() - t_start) * 1000.0
        return PipelineExecutionResult(
            success=False,
            plan_ast=plan,
            compiled_sql=sql,
            query_result=None,
            total_elapsed_ms=elapsed,
            timed_out=True,
            stage_latencies_ms=stages,
            error_message=f"Pipeline deadline exceeded during {stage}",
        )

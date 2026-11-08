"""端到端自然语言 SQLite 助理全流程流水线 (M6.1).

工作流：
自然语言输入
-> Schema 上下文装配
-> 本地约束模型翻译 (LocalTranslatorClient)
-> 结构化 IntentSpec 校验 (validate_intent_against_schema)
-> 确定性 MiniRel AST 规划 (IntentResolver)
-> 参数化 SQL 编译 (MiniRelSQLCompiler)
-> 只读 SQLite 后端执行 (SQLiteExecutionBackend)
-> 结果校验与 Markdown 友好表格渲染。

全程贯穿单一单调时钟 (Single Monotonic Deadline)，支持优雅澄清与安全弃权。
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple

from ..dsl.ast import ASTNode
from ..sqlite.backend import SQLiteExecutionBackend, SQLiteQueryResult, SQLiteTimeoutError
from ..sqlite.compiler import MiniRelSQLCompiler
from ..sqlite.schema import SQLiteDatabaseSchema, SQLiteSchemaAdapter
from .client import LocalTranslatorClient, TranslatorClientError, TranslatorTimeoutError
from .contract import IntentSpec, validate_intent_against_schema
from .resolver import IntentResolutionError, IntentResolver


@dataclass(frozen=True)
class NaturalLanguageQueryResult:
    """自然语言查询最终输出结果。"""
    question: str
    success: bool
    intent: Optional[IntentSpec]
    compiled_sql: Optional[str]
    table_result: Optional[SQLiteQueryResult]
    formatted_output: str
    needs_clarification: bool
    clarification_prompt: Optional[str]
    is_unsupported: bool
    unsupported_reason: Optional[str]
    timed_out: bool
    total_latency_ms: float
    stage_durations_ms: Dict[str, float]
    error_message: Optional[str] = None


class NaturalLanguageSQLiteAssistant:
    """端到端本地自然语言 SQLite 助理。"""

    def __init__(
        self,
        model_name: str = "qwen2.5-coder:1.5b",
        default_deadline_sec: float = 15.0,
        max_rows: int = 1000,
    ) -> None:
        self.default_deadline = default_deadline_sec
        self.translator = LocalTranslatorClient(model_name=model_name)
        self.compiler = MiniRelSQLCompiler()
        self.backend = SQLiteExecutionBackend(max_rows=max_rows)

    def query(
        self,
        question: str,
        db_path: str,
        deadline_sec: Optional[float] = None,
    ) -> NaturalLanguageQueryResult:
        """从自然语言提问到验证结果的完整单调截止时间执行。"""
        t_global_start = time.perf_counter()
        deadline = deadline_sec or self.default_deadline

        def remaining() -> float:
            return deadline - (time.perf_counter() - t_global_start)

        stages: Dict[str, float] = {}

        # 防御性安全前置检查：显式拦截删除、修改与 DDL 意图
        q_lower = question.lower().strip()
        destructive_verbs = ("drop table", "delete from", "delete all", "update ", "insert into", "truncate ", "alter table")
        if any(v in q_lower for v in destructive_verbs):
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=None,
                compiled_sql=None,
                table_result=None,
                formatted_output="Operation Prohibited: Write, mutation, and schema alteration queries are strictly prohibited on read-only databases.",
                needs_clarification=False,
                clarification_prompt=None,
                is_unsupported=True,
                unsupported_reason="Database write and schema mutation operations are strictly prohibited.",
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
                error_message="Prohibited database write operation",
            )

        # 阶段 1: Schema 元数据发现
        if remaining() <= 0:
            return self._timeout_exit(question, "schema_introspection", t_global_start, stages)

        t0 = time.perf_counter()
        schema = SQLiteSchemaAdapter.inspect_database(db_path)
        stages["schema_introspection_ms"] = (time.perf_counter() - t0) * 1000.0

        # 阶段 2: 本地模型约束意图翻译
        rem_sec = remaining()
        if rem_sec <= 0:
            return self._timeout_exit(question, "translator_inference", t_global_start, stages)

        t0 = time.perf_counter()
        try:
            intent, infer_time = self.translator.translate_question(question, schema, timeout_sec=rem_sec)
        except TranslatorTimeoutError:
            stages["translator_inference_ms"] = (time.perf_counter() - t0) * 1000.0
            return self._timeout_exit(question, "translator_inference_timeout", t_global_start, stages)
        except Exception as e:
            stages["translator_inference_ms"] = (time.perf_counter() - t0) * 1000.0
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=None,
                compiled_sql=None,
                table_result=None,
                formatted_output=f"Translator Error: {e}",
                needs_clarification=False,
                clarification_prompt=None,
                is_unsupported=False,
                unsupported_reason=None,
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
                error_message=str(e),
            )

        stages["translator_inference_ms"] = (time.perf_counter() - t0) * 1000.0

        # 阶段 3: 澄清或不支持意图处理
        if intent.clarification_needed:
            prompt = intent.clarification_prompt or "Your request is ambiguous. Please specify more details."
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=intent,
                compiled_sql=None,
                table_result=None,
                formatted_output=f"Clarification Needed: {prompt}",
                needs_clarification=True,
                clarification_prompt=prompt,
                is_unsupported=False,
                unsupported_reason=None,
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
            )

        if intent.unsupported:
            reason = intent.unsupported_reason or "This operation is not supported by the current database schema."
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=intent,
                compiled_sql=None,
                table_result=None,
                formatted_output=f"Unsupported Request: {reason}",
                needs_clarification=False,
                clarification_prompt=None,
                is_unsupported=True,
                unsupported_reason=reason,
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
            )

        # 阶段 4: 静态 Schema 合法性校验
        is_valid_schema, schema_err = validate_intent_against_schema(intent, schema)
        if not is_valid_schema:
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=intent,
                compiled_sql=None,
                table_result=None,
                formatted_output=f"Schema Validation Error: {schema_err}",
                needs_clarification=False,
                clarification_prompt=None,
                is_unsupported=True,
                unsupported_reason=schema_err,
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
                error_message=schema_err,
            )

        # 阶段 5: 确定性 MiniRel AST 规划
        t0 = time.perf_counter()
        try:
            plan_ast = IntentResolver.resolve_to_ast(intent, schema)
        except IntentResolutionError as e:
            stages["intent_resolution_ms"] = (time.perf_counter() - t0) * 1000.0
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=intent,
                compiled_sql=None,
                table_result=None,
                formatted_output=f"Planning Error: {e}",
                needs_clarification=False,
                clarification_prompt=None,
                is_unsupported=True,
                unsupported_reason=str(e),
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
                error_message=str(e),
            )
        stages["intent_resolution_ms"] = (time.perf_counter() - t0) * 1000.0

        # 阶段 6: 参数化 SQL 编译
        if remaining() <= 0:
            return self._timeout_exit(question, "sql_compilation", t_global_start, stages, intent)

        t0 = time.perf_counter()
        minirel_schemas = schema.to_minirel_schemas()
        try:
            compiled = self.compiler.compile(plan_ast, minirel_schemas)
        except Exception as e:
            stages["sql_compilation_ms"] = (time.perf_counter() - t0) * 1000.0
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=intent,
                compiled_sql=None,
                table_result=None,
                formatted_output=f"SQL Compilation Error: {e}",
                needs_clarification=False,
                clarification_prompt=None,
                is_unsupported=True,
                unsupported_reason=str(e),
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
                error_message=str(e),
            )
        stages["sql_compilation_ms"] = (time.perf_counter() - t0) * 1000.0

        # 阶段 7: 只读 SQLite 引擎底层执行
        rem_sec = remaining()
        if rem_sec <= 0:
            return self._timeout_exit(question, "sqlite_execution", t_global_start, stages, intent, compiled.sql)

        t0 = time.perf_counter()
        try:
            query_res = self.backend.execute_compiled(compiled, db_path, timeout_sec=rem_sec)
        except SQLiteTimeoutError:
            stages["sqlite_execution_ms"] = (time.perf_counter() - t0) * 1000.0
            return self._timeout_exit(question, "sqlite_execution_timeout", t_global_start, stages, intent, compiled.sql)
        except Exception as e:
            stages["sqlite_execution_ms"] = (time.perf_counter() - t0) * 1000.0
            return NaturalLanguageQueryResult(
                question=question,
                success=False,
                intent=intent,
                compiled_sql=compiled.sql,
                table_result=None,
                formatted_output=f"Database Execution Error: {e}",
                needs_clarification=False,
                clarification_prompt=None,
                is_unsupported=False,
                unsupported_reason=None,
                timed_out=False,
                total_latency_ms=(time.perf_counter() - t_global_start) * 1000.0,
                stage_durations_ms=stages,
                error_message=str(e),
            )
        stages["sqlite_execution_ms"] = (time.perf_counter() - t0) * 1000.0

        # 阶段 8: Markdown 格式化呈现
        rendered_markdown = self._render_markdown_table(query_res)
        total_time_ms = (time.perf_counter() - t_global_start) * 1000.0

        return NaturalLanguageQueryResult(
            question=question,
            success=True,
            intent=intent,
            compiled_sql=compiled.sql,
            table_result=query_res,
            formatted_output=rendered_markdown,
            needs_clarification=False,
            clarification_prompt=None,
            is_unsupported=False,
            unsupported_reason=None,
            timed_out=False,
            total_latency_ms=total_time_ms,
            stage_durations_ms=stages,
            error_message=None,
        )

    def _render_markdown_table(self, res: SQLiteQueryResult) -> str:
        """渲染结果表格为干净的 Markdown 格式。"""
        if res.row_count == 0:
            return "No matching records found."

        cols = list(res.schema.column_names)
        header_line = "| " + " | ".join(cols) + " |"
        sep_line = "| " + " | ".join(["---" for _ in cols]) + " |"
        row_lines = []
        for r in res.rows:
            row_lines.append("| " + " | ".join(str(val) if val is not None else "NULL" for val in r) + " |")

        lines = [header_line, sep_line] + row_lines
        if res.is_truncated:
            lines.append(f"\n*(Output truncated at {res.row_count} rows)*")
        return "\n".join(lines)

    def _timeout_exit(
        self,
        question: str,
        stage: str,
        t_start: float,
        stages: Dict[str, float],
        intent: Optional[IntentSpec] = None,
        sql: Optional[str] = None,
    ) -> NaturalLanguageQueryResult:
        elapsed = (time.perf_counter() - t_start) * 1000.0
        return NaturalLanguageQueryResult(
            question=question,
            success=False,
            intent=intent,
            compiled_sql=sql,
            table_result=None,
            formatted_output=f"Request timed out during {stage} after {elapsed:.1f}ms.",
            needs_clarification=False,
            clarification_prompt=None,
            is_unsupported=False,
            unsupported_reason=None,
            timed_out=True,
            total_latency_ms=elapsed,
            stage_durations_ms=stages,
            error_message=f"Timeout during {stage}",
        )

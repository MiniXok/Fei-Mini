"""安全只读 SQLite 执行引擎与结果模型。

实施纵深防御 (Defense in Depth) 策略：
1. 只读 URI 连接参数 (mode=ro)。
2. 系统级 PRAGMA query_only = ON 强制锁定。
3. 底层 SQLite Authorizer 回调函数：白名单放行 SELECT/READ，绝对阻断 INSERT/UPDATE/DELETE/DROP/ALTER/ATTACH/PRAGMA。
4. SQLite Progress Handler 毫秒级虚拟指令级中断保护。
5. 结果行数与字节数上限截断。
"""

from __future__ import annotations
from dataclasses import dataclass
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..dsl.ast import ASTNode
from ..dsl.types import Column, DataType, RelationSchema, Table
from .compiler import CompiledSQLQuery, MiniRelSQLCompiler
from .schema import SQLiteDatabaseSchema, SQLiteSchemaAdapter


class SQLiteSecurityError(Exception):
    """SQLite 安全越权拦截异常。"""
    pass


class SQLiteExecutionError(Exception):
    """SQLite 查询执行期错误。"""
    pass


class SQLiteTimeoutError(SQLiteExecutionError):
    """SQLite 查询执行超时中断。"""
    pass


@dataclass(frozen=True)
class SQLiteQueryResult:
    """SQLite 查询执行标准输出结果模型。"""
    schema: RelationSchema
    rows: Tuple[Tuple[Any, ...], ...]
    row_count: int
    is_truncated: bool
    execution_time_sec: float
    compiled_sql: str
    params: Tuple[Any, ...]
    error: Optional[str] = None

    def to_table(self) -> Table:
        """转换为 MiniRel 内存表格结构以供比较。"""
        return Table(self.schema, self.rows)


# SQLite Authorizer 动作码定义 (由 C 源码扩展常量保证)
_SQLITE_OK = 0
_SQLITE_DENY = 1
_SQLITE_IGNORE = 2

# 允许的安全只读操作码集合
_SAFE_AUTHORIZER_ACTIONS = {
    sqlite3.SQLITE_SELECT if hasattr(sqlite3, "SQLITE_SELECT") else 21,
    sqlite3.SQLITE_READ if hasattr(sqlite3, "SQLITE_READ") else 20,
    sqlite3.SQLITE_FUNCTION if hasattr(sqlite3, "SQLITE_FUNCTION") else 19,
    sqlite3.SQLITE_RECURSIVE if hasattr(sqlite3, "SQLITE_RECURSIVE") else 33,
}


def _strict_readonly_authorizer(action_code: int, p1: Any, p2: Any, p3: Any, p4: Any) -> int:
    """SQLite 底层安全拦截器回调函数。"""
    if action_code in _SAFE_AUTHORIZER_ACTIONS:
        return _SQLITE_OK
    # 任何写操作、模式修改、ATTACH/PRAGMA 均一票否决
    return _SQLITE_DENY


class SQLiteExecutionBackend:
    """只读安全 SQLite 统一执行后端。"""

    def __init__(
        self,
        max_rows: int = 10_000,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        default_timeout_sec: float = 2.0,
    ) -> None:
        self.max_rows = max_rows
        self.max_bytes = max_bytes
        self.default_timeout = default_timeout_sec
        self.compiler = MiniRelSQLCompiler()

    def execute_ast(
        self,
        node: ASTNode,
        db_path: str,
        env_schemas: Dict[str, RelationSchema],
        timeout_sec: Optional[float] = None,
    ) -> SQLiteQueryResult:
        """将 MiniRel AST 编译并在只读 SQLite 数据库中安全执行。"""
        compiled = self.compiler.compile(node, env_schemas)
        return self.execute_compiled(compiled, db_path, timeout_sec)

    def execute_compiled(
        self,
        compiled: CompiledSQLQuery,
        db_path: str,
        timeout_sec: Optional[float] = None,
    ) -> SQLiteQueryResult:
        """执行编译好的参数化 SQL 查询。"""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")

        timeout = timeout_sec or self.default_timeout
        abs_path = os.path.abspath(db_path)
        uri = f"file:{abs_path}?mode=ro"

        t_wall_start = time.perf_counter()

        # 进度处理中断检查
        class TimeoutTracker:
            def __init__(self, limit: float) -> None:
                self.t0 = time.perf_counter()
                self.limit = limit
                self.timed_out = False

            def check_progress(self) -> int:
                if (time.perf_counter() - self.t0) > self.limit:
                    self.timed_out = True
                    return 1  # 非零返回值将中断 SQLite 查询
                return 0

        tracker = TimeoutTracker(timeout)

        conn = sqlite3.connect(uri, uri=True, timeout=timeout)
        try:
            # 1. 强制启用 query_only
            conn.execute("PRAGMA query_only = ON;")

            # 2. 挂载严苛底层 authorizer 回调
            conn.set_authorizer(_strict_readonly_authorizer)

            # 3. 挂载指令进度中断处理器 (每 1000 条虚拟指令检查一次时钟)
            conn.set_progress_handler(tracker.check_progress, 1000)

            cursor = conn.cursor()

            try:
                cursor.execute(compiled.sql, compiled.params)
            except sqlite3.DatabaseError as e:
                err_msg = str(e)
                if tracker.timed_out or "interrupted" in err_msg.lower():
                    raise SQLiteTimeoutError(f"Query exceeded execution timeout ({timeout}s)")
                if "not authorized" in err_msg.lower():
                    raise SQLiteSecurityError(f"Unauthorized operation denied by security policy: {e}")
                raise SQLiteExecutionError(f"SQLite execution failed: {e}")

            # 4. 获取列信息
            desc = cursor.description or ()
            # 优先采用编译期推导出的精确 Schema
            col_names = [d[0] for d in desc]

            out_cols: List[Column] = []
            for idx, c_name in enumerate(col_names):
                col_type = compiled.output_schema.get_type(c_name) or DataType.STR
                out_cols.append(Column(c_name, col_type))
            result_schema = RelationSchema(tuple(out_cols))

            # 5. 遍历读取行并严格进行行数与内存大小截断保护
            rows: List[Tuple[Any, ...]] = []
            is_truncated = False
            total_bytes = 0

            try:
                while True:
                    fetch_batch = cursor.fetchmany(100)
                    if not fetch_batch:
                        break

                    for row in fetch_batch:
                        rows.append(tuple(row))
                        total_bytes += sum(len(str(v)) for v in row)

                        if len(rows) >= self.max_rows or total_bytes >= self.max_bytes:
                            is_truncated = True
                            break

                    if is_truncated:
                        break
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                err_msg = str(e)
                if tracker.timed_out or "interrupted" in err_msg.lower():
                    raise SQLiteTimeoutError(f"Query exceeded execution timeout ({timeout}s)")
                raise SQLiteExecutionError(f"Fetch failed: {e}")

            execution_time = time.perf_counter() - t_wall_start

            return SQLiteQueryResult(
                schema=result_schema,
                rows=tuple(rows),
                row_count=len(rows),
                is_truncated=is_truncated,
                execution_time_sec=execution_time,
                compiled_sql=compiled.sql,
                params=compiled.params,
                error=None,
            )

        finally:
            conn.close()

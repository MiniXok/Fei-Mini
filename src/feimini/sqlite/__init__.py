"""SQLite 适配器、编译器与只读执行后端模块。"""

from .schema import (
    SQLiteColumnInfo,
    SQLiteForeignKeyInfo,
    SQLiteTableInfo,
    SQLiteDatabaseSchema,
    SQLiteSchemaAdapter,
    map_sqlite_type_to_minirel,
)
from .retrieval import BoundedValueRetriever
from .compiler import (
    CompilationError,
    CompiledSQLQuery,
    MiniRelSQLCompiler,
)
from .backend import (
    SQLiteSecurityError,
    SQLiteExecutionError,
    SQLiteTimeoutError,
    SQLiteQueryResult,
    SQLiteExecutionBackend,
)

__all__ = [
    "SQLiteColumnInfo",
    "SQLiteForeignKeyInfo",
    "SQLiteTableInfo",
    "SQLiteDatabaseSchema",
    "SQLiteSchemaAdapter",
    "map_sqlite_type_to_minirel",
    "BoundedValueRetriever",
    "CompilationError",
    "CompiledSQLQuery",
    "MiniRelSQLCompiler",
    "SQLiteSecurityError",
    "SQLiteExecutionError",
    "SQLiteTimeoutError",
    "SQLiteQueryResult",
    "SQLiteExecutionBackend",
]

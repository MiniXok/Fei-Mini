"""SQLite 数据库 Schema 检查适配器与显式类型安全模型。

显式区分：
1. 声明的 SQLite 类型亲和 (Declared Affinity).
2. 是否使用 STRICT 类型表模式 (SQLite 3.37.0+ STRICT tables).
3. 保证类型 (TypeGuarantee) vs 推断类型 (Inferred Type).
4. 运行期存储类 (Storage Class: INTEGER, REAL, TEXT, BLOB, NULL).
5. 列的可空性 (Nullability) 与观测存储特征 (Bounded profiling).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from ..dsl.types import Column, DataType, RelationSchema
from ..generator.schema import TableSpec


class TypeGuarantee(str, Enum):
    """类型确定性保障级别。"""
    GUARANTEED_STRICT = "GUARANTEED_STRICT"   # STRICT 模式表中的显式类型定义（SQLite 引擎强制保证无异类）
    GUARANTEED_PK = "GUARANTEED_PK"           # 传统 ROWID 表的 INTEGER PRIMARY KEY (保证 64 位有符号整型)
    INFERRED_AFFINITY = "INFERRED_AFFINITY"   # 传统非 STRICT 表中的声明亲和（仅为偏好，可能包含异类值）
    DYNAMIC_UNKNOWN = "DYNAMIC_UNKNOWN"       # 未声明类型、ANY 或通用动态列


@dataclass(frozen=True)
class SQLiteColumnInfo:
    """SQLite 单列详细元数据结构体。"""
    cid: int
    name: str
    declared_type: str
    data_type: DataType
    type_guarantee: TypeGuarantee
    not_null: bool
    is_pk: bool
    default_value: Optional[str] = None
    observed_storage_classes: Tuple[str, ...] = ()
    has_nulls_observed: Optional[bool] = None


@dataclass(frozen=True)
class SQLiteForeignKeyInfo:
    """SQLite 外键约束元数据。"""
    from_column: str
    target_table: str
    to_column: str


@dataclass(frozen=True)
class SQLiteTableInfo:
    """SQLite 数据表元数据结构体。"""
    name: str
    columns: Tuple[SQLiteColumnInfo, ...]
    primary_key: Optional[str]
    foreign_keys: Tuple[SQLiteForeignKeyInfo, ...]
    indexes: Tuple[str, ...] = ()
    is_view: bool = False
    is_strict: bool = False
    without_rowid: bool = False
    sql: Optional[str] = None

    @property
    def column_names(self) -> Tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    def to_minirel_schema(self) -> RelationSchema:
        """转换为 MiniRel 的强类型 RelationSchema。"""
        cols = tuple(Column(c.name, c.data_type) for c in self.columns)
        return RelationSchema(cols)

    def to_table_spec(self, value_domains: Optional[Dict[str, List[Any]]] = None) -> TableSpec:
        """转换为任务生成器与求解器兼容的 TableSpec。"""
        fk_ref = None
        if self.foreign_keys:
            fk = self.foreign_keys[0]
            fk_ref = (fk.from_column, fk.target_table)

        pk_col = self.primary_key or (self.columns[0].name if self.columns else "id")
        return TableSpec(
            name=self.name,
            schema=self.to_minirel_schema(),
            pk_col=pk_col,
            fk_ref=fk_ref,
            value_domains=value_domains,
        )


@dataclass
class SQLiteDatabaseSchema:
    """完整 SQLite 数据库结构体。"""
    db_path: str
    tables: Dict[str, SQLiteTableInfo] = field(default_factory=dict)

    def get_table(self, name: str) -> Optional[SQLiteTableInfo]:
        return self.tables.get(name)

    def to_minirel_schemas(self) -> Dict[str, RelationSchema]:
        return {name: t.to_minirel_schema() for name, t in self.tables.items()}


def map_sqlite_type_to_minirel(declared_type: str) -> DataType:
    """根据 SQLite 类型亲和规则与显式声明保守映射至 MiniRel 标量类型。"""
    t = declared_type.strip().upper()
    if not t or t == "ANY":
        return DataType.STR

    if t in ("BOOL", "BOOLEAN"):
        return DataType.BOOL

    int_keywords = ("INT", "INTEGER", "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT", "UNSIGNED BIG INT", "INT2", "INT8")
    if any(k in t for k in int_keywords):
        return DataType.INT

    real_keywords = ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL")
    if any(k in t for k in real_keywords):
        return DataType.FLOAT

    text_keywords = ("TEXT", "CHAR", "CLOB", "VARCHAR", "NVARCHAR")
    if any(k in t for k in text_keywords):
        return DataType.STR

    return DataType.STR


def _is_table_strict(sql: Optional[str]) -> bool:
    """根据建表 SQL 解析是否启用了 STRICT 模式。"""
    if not sql:
        return False
    # STRICT 必须位于括号闭合后: ) STRICT; 或 ) WITHOUT ROWID, STRICT;
    clean_sql = sql.strip()
    return bool(re.search(r'\)\s*(?:WITHOUT\s+ROWID\s*,\s*)?STRICT\b', clean_sql, re.IGNORECASE))


def _is_table_without_rowid(sql: Optional[str]) -> bool:
    """解析是否启用了 WITHOUT ROWID。"""
    if not sql:
        return False
    clean_sql = sql.strip()
    return bool(re.search(r'\)\s*(?:STRICT\s*,\s*)?WITHOUT\s+ROWID\b', clean_sql, re.IGNORECASE))


class SQLiteSchemaAdapter:
    """SQLite 数据库安全元数据适配器。"""

    @staticmethod
    def inspect_database(db_path: str, profile_sample_rows: int = 20) -> SQLiteDatabaseSchema:
        """以严格只读模式检查指定 SQLite 数据库，构建显式类型保障模型。"""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")

        abs_path = os.path.abspath(db_path)
        uri = f"file:{abs_path}?mode=ro"

        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA query_only = ON;")

            # 1. 查询所有用户数据表与视图及其 DDL 定义
            cursor.execute(
                "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            table_entries = cursor.fetchall()

            schema = SQLiteDatabaseSchema(db_path=abs_path)

            for tbl_name, tbl_type, tbl_sql in table_entries:
                is_view = (tbl_type == "view")
                is_strict = _is_table_strict(tbl_sql) if not is_view else False
                without_rowid = _is_table_without_rowid(tbl_sql) if not is_view else False

                clean_name = tbl_name.replace('"', '""')
                cursor.execute(f'PRAGMA table_info("{clean_name}");')
                col_rows = cursor.fetchall()

                columns: List[SQLiteColumnInfo] = []
                pk_col: Optional[str] = None

                for cid, c_name, c_type, notnull, dflt, is_pk in col_rows:
                    dt = map_sqlite_type_to_minirel(c_type)
                    clean_c_type = c_type.strip().upper()

                    # 判定类型保障级别
                    if is_strict and clean_c_type in ("INT", "INTEGER", "REAL", "TEXT", "BLOB"):
                        guarantee = TypeGuarantee.GUARANTEED_STRICT
                    elif bool(is_pk) and clean_c_type == "INTEGER" and not without_rowid:
                        guarantee = TypeGuarantee.GUARANTEED_PK
                    elif clean_c_type:
                        guarantee = TypeGuarantee.INFERRED_AFFINITY
                    else:
                        guarantee = TypeGuarantee.DYNAMIC_UNKNOWN

                    if is_pk == 1 and pk_col is None:
                        pk_col = c_name

                    # 轻量级有界存储类采样（上限 20 行，杜绝全表扫描）
                    observed_classes: Set[str] = set()
                    has_nulls: Optional[bool] = None

                    if profile_sample_rows > 0 and not is_view:
                        try:
                            clean_col = c_name.replace('"', '""')
                            prof_sql = f'SELECT typeof("{clean_col}"), "{clean_col}" IS NULL FROM "{clean_name}" LIMIT {int(profile_sample_rows)};'
                            cursor.execute(prof_sql)
                            for s_type, s_null in cursor.fetchall():
                                if s_type:
                                    observed_classes.add(s_type.upper())
                                if s_null == 1:
                                    has_nulls = True
                            if has_nulls is None and len(observed_classes) > 0:
                                has_nulls = False
                        except Exception:
                            pass

                    columns.append(
                        SQLiteColumnInfo(
                            cid=cid,
                            name=c_name,
                            declared_type=c_type,
                            data_type=dt,
                            type_guarantee=guarantee,
                            not_null=bool(notnull),
                            is_pk=bool(is_pk),
                            default_value=str(dflt) if dflt is not None else None,
                            observed_storage_classes=tuple(sorted(list(observed_classes))),
                            has_nulls_observed=has_nulls,
                        )
                    )

                # 外键参照关系
                fks: List[SQLiteForeignKeyInfo] = []
                if not is_view:
                    cursor.execute(f'PRAGMA foreign_key_list("{clean_name}");')
                    for _, _, target_tbl, from_c, to_c, _, _, _ in cursor.fetchall():
                        fks.append(
                            SQLiteForeignKeyInfo(
                                from_column=from_c,
                                target_table=target_tbl,
                                to_column=to_c,
                            )
                        )

                # 索引列表
                indexes: List[str] = []
                if not is_view:
                    cursor.execute(f'PRAGMA index_list("{clean_name}");')
                    for idx_row in cursor.fetchall():
                        indexes.append(idx_row[1])

                table_info = SQLiteTableInfo(
                    name=tbl_name,
                    columns=tuple(columns),
                    primary_key=pk_col,
                    foreign_keys=tuple(fks),
                    indexes=tuple(indexes),
                    is_view=is_view,
                    is_strict=is_strict,
                    without_rowid=without_rowid,
                    sql=tbl_sql,
                )
                schema.tables[tbl_name] = table_info

            return schema
        finally:
            conn.close()

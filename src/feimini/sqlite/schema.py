"""SQLite 数据库 Schema 检查适配器。

通过查询 sqlite_master 与系统 PRAGMA 获取表格、列属性、主外键参照关系及索引，
将 SQLite 动态类型保守映射为 MiniRel 的静态类型系统，杜绝扫描大表发现元数据。
"""

from __future__ import annotations
from dataclasses import dataclass, field
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from ..dsl.types import Column, DataType, RelationSchema
from ..generator.schema import TableSpec


@dataclass(frozen=True)
class SQLiteColumnInfo:
    """SQLite 单列元数据。"""
    cid: int
    name: str
    declared_type: str
    data_type: DataType
    not_null: bool
    is_pk: bool
    default_value: Optional[str] = None


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
    if not t:
        return DataType.STR

    # 布尔类型优先匹配
    if t in ("BOOL", "BOOLEAN"):
        return DataType.BOOL

    # 整数亲和
    int_keywords = ("INT", "INTEGER", "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT", "UNSIGNED BIG INT", "INT2", "INT8")
    if any(k in t for k in int_keywords):
        return DataType.INT

    # 浮点/数值亲和
    real_keywords = ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL")
    if any(k in t for k in real_keywords):
        return DataType.FLOAT

    # 文本与字符串亲和
    text_keywords = ("TEXT", "CHAR", "CLOB", "VARCHAR", "NVARCHAR")
    if any(k in t for k in text_keywords):
        return DataType.STR

    return DataType.STR


class SQLiteSchemaAdapter:
    """SQLite 数据库安全元数据适配器。"""

    @staticmethod
    def inspect_database(db_path: str) -> SQLiteDatabaseSchema:
        """以严格只读模式检查指定 SQLite 数据库并构建元数据，不扫描数据行。"""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")

        # 使用只读 URI 连接
        abs_path = os.path.abspath(db_path)
        uri = f"file:{abs_path}?mode=ro"

        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA query_only = ON;")

            # 1. 查询所有用户数据表与视图
            cursor.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            table_entries = cursor.fetchall()

            schema = SQLiteDatabaseSchema(db_path=abs_path)

            for tbl_name, tbl_type in table_entries:
                is_view = (tbl_type == "view")

                # 2. 查询列信息 (PRAGMA table_info)
                # 使用参数化验证表名防止注入
                clean_name = tbl_name.replace('"', '""')
                cursor.execute(f'PRAGMA table_info("{clean_name}");')
                col_rows = cursor.fetchall()

                columns: List[SQLiteColumnInfo] = []
                pk_col: Optional[str] = None

                for cid, c_name, c_type, notnull, dflt, is_pk in col_rows:
                    dt = map_sqlite_type_to_minirel(c_type)
                    if is_pk == 1 and pk_col is None:
                        pk_col = c_name
                    columns.append(
                        SQLiteColumnInfo(
                            cid=cid,
                            name=c_name,
                            declared_type=c_type,
                            data_type=dt,
                            not_null=bool(notnull),
                            is_pk=bool(is_pk),
                            default_value=str(dflt) if dflt is not None else None,
                        )
                    )

                # 3. 查询外键参照关系 (PRAGMA foreign_key_list)
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

                # 4. 查询索引列表 (PRAGMA index_list)
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
                )
                schema.tables[tbl_name] = table_info

            return schema
        finally:
            conn.close()

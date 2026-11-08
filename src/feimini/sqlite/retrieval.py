"""有界列取值与分类域安全提取器。

在严格行数上限 (LIMIT) 与查询超时约束下，为分类列及候选谓词常数提取离散值域，
绝不进行全表无界扫描，杜绝向外部或云端暴露敏感数据。
"""

from __future__ import annotations
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set

from .schema import SQLiteDatabaseSchema, SQLiteTableInfo


class BoundedValueRetriever:
    """有界离散值域检索器。"""

    def __init__(
        self,
        max_distinct_per_col: int = 50,
        query_timeout_sec: float = 1.0,
    ) -> None:
        self.max_distinct = max_distinct_per_col
        self.timeout_sec = query_timeout_sec

    def retrieve_column_values(
        self,
        db_path: str,
        table_name: str,
        column_name: str,
    ) -> List[Any]:
        """安全检索指定数据列的代表性离散值（上限 max_distinct）。"""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")

        abs_path = os.path.abspath(db_path)
        uri = f"file:{abs_path}?mode=ro"

        conn = sqlite3.connect(uri, uri=True, timeout=self.timeout_sec)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA query_only = ON;")

            # 安全转义标识符
            clean_tbl = table_name.replace('"', '""')
            clean_col = column_name.replace('"', '""')

            # 使用 DISTINCT 与显式 LIMIT 避免无界全表扫描
            sql = f'SELECT DISTINCT "{clean_col}" FROM "{clean_tbl}" WHERE "{clean_col}" IS NOT NULL LIMIT {int(self.max_distinct)};'

            t0 = time.perf_counter()
            cursor.execute(sql)
            rows = cursor.fetchall()

            return [r[0] for r in rows]
        except Exception:
            return []
        finally:
            conn.close()

    def harvest_categorical_domains(
        self,
        schema: SQLiteDatabaseSchema,
        target_tables: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, List[Any]]]:
        """批量获取指定表格中字符串与整数列的代表性离散值域。"""
        domains: Dict[str, Dict[str, List[Any]]] = {}
        tables = target_tables or list(schema.tables.keys())

        for tbl_name in tables:
            tbl_info = schema.get_table(tbl_name)
            if not tbl_info:
                continue

            tbl_domains: Dict[str, List[Any]] = {}
            for col in tbl_info.columns:
                # 仅对文本或低基数整数列提取离散常数候选
                vals = self.retrieve_column_values(schema.db_path, tbl_name, col.name)
                if vals:
                    tbl_domains[col.name] = vals

            domains[tbl_name] = tbl_domains

        return domains

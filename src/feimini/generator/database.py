"""确定性内存数据库实例生成器。

基于给定的 Schema 族与随机数种子生成具有主外键参照完整性的关系表格实例。
"""

from __future__ import annotations
import random
from typing import Any, Dict, List, Optional, Tuple

from ..dsl.types import DataType, Table
from .schema import SchemaFamily, TableSpec


class DatabaseGenerator:
    """根据 Schema 族生成真实且具备参照完整性的数据库实例。"""

    def __init__(self, min_rows: int = 10, max_rows: int = 30) -> None:
        self.min_rows = min_rows
        self.max_rows = max_rows

    def generate(self, family: SchemaFamily, rng: random.Random) -> Dict[str, Table]:
        """确定性生成一个数据库实例（包含族内所有表格）。"""
        database: Dict[str, Table] = {}
        # 存储主表生成的 PK 集合，供从表外键引用
        pk_store: Dict[str, List[int]] = {}

        # 区分主表与从表（无外键的先生成，有外键的后生成）
        parent_tables = [t for t in family.tables if t.fk_ref is None]
        child_tables = [t for t in family.tables if t.fk_ref is not None]

        # 1. 生成主表
        for spec in parent_tables:
            n_rows = rng.randint(self.min_rows, self.max_rows)
            rows: List[Tuple[Any, ...]] = []
            pks = list(range(1, n_rows + 1))
            rng.shuffle(pks)
            pk_store[spec.name] = pks

            for i in range(n_rows):
                row_vals: List[Any] = []
                for col in spec.schema.columns:
                    if col.name == spec.pk_col:
                        row_vals.append(pks[i])
                    elif spec.value_domains and col.name in spec.value_domains:
                        row_vals.append(rng.choice(spec.value_domains[col.name]))
                    elif col.data_type == DataType.INT:
                        row_vals.append(rng.randint(1, 100))
                    elif col.data_type == DataType.FLOAT:
                        row_vals.append(round(rng.uniform(10.0, 500.0), 2))
                    elif col.data_type == DataType.STR:
                        row_vals.append(f"item_{rng.randint(1, 20)}")
                    elif col.data_type == DataType.BOOL:
                        row_vals.append(rng.choice([True, False]))
                rows.append(tuple(row_vals))

            database[spec.name] = Table(spec.schema, tuple(rows))

        # 2. 生成从表（保证外键引用有效）
        for spec in child_tables:
            n_rows = rng.randint(self.min_rows, self.max_rows)
            rows = []
            pks = list(range(1001, 1001 + n_rows))
            rng.shuffle(pks)

            fk_col, ref_table_name = spec.fk_ref  # type: ignore
            available_fks = pk_store.get(ref_table_name, [1])

            for i in range(n_rows):
                row_vals = []
                for col in spec.schema.columns:
                    if col.name == spec.pk_col:
                        row_vals.append(pks[i])
                    elif col.name == fk_col:
                        # 从主表主键集合中随机采样外键
                        row_vals.append(rng.choice(available_fks))
                    elif spec.value_domains and col.name in spec.value_domains:
                        row_vals.append(rng.choice(spec.value_domains[col.name]))
                    elif col.data_type == DataType.INT:
                        row_vals.append(rng.randint(1, 100))
                    elif col.data_type == DataType.FLOAT:
                        row_vals.append(round(rng.uniform(5.0, 300.0), 2))
                    elif col.data_type == DataType.STR:
                        row_vals.append(f"val_{rng.randint(1, 15)}")
                    elif col.data_type == DataType.BOOL:
                        row_vals.append(rng.choice([True, False]))
                rows.append(tuple(row_vals))

            database[spec.name] = Table(spec.schema, tuple(rows))

        return database

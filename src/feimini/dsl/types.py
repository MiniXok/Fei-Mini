"""MiniRel 关系类型系统与内存表格模型。

包含基础标量类型、列定义、关系 Schema、表格模型以及谓词操作符与排序方向枚举。
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


class DataType(str, Enum):
    """支持的标量数据类型。"""
    INT = "INT"
    FLOAT = "FLOAT"
    STR = "STR"
    BOOL = "BOOL"

    def coerce(self, val: Any) -> Any:
        """安全类型转换。"""
        if val is None:
            return None
        if self == DataType.INT:
            return int(val)
        if self == DataType.FLOAT:
            return float(val)
        if self == DataType.STR:
            return str(val)
        if self == DataType.BOOL:
            return bool(val)
        raise ValueError(f"Unknown data type: {self}")


class PredicateOp(str, Enum):
    """谓词比较操作符。"""
    EQ = "EQ"
    NEQ = "NEQ"
    LT = "LT"
    GT = "GT"
    LTE = "LTE"
    GTE = "GTE"

    def evaluate(self, left: Any, right: Any) -> bool:
        """评估左右两个标量值的比较结果。"""
        if left is None or right is None:
            return False
        if self == PredicateOp.EQ:
            return left == right
        if self == PredicateOp.NEQ:
            return left != right
        if self == PredicateOp.LT:
            return left < right
        if self == PredicateOp.GT:
            return left > right
        if self == PredicateOp.LTE:
            return left <= right
        if self == PredicateOp.GTE:
            return left >= right
        raise ValueError(f"Unknown predicate operator: {self}")


class SortDirection(str, Enum):
    """排序方向枚举。"""
    ASC = "ASC"
    DESC = "DESC"


@dataclass(frozen=True)
class Column:
    """关系的列定义。"""
    name: str
    data_type: DataType

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "type": self.data_type.value}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> Column:
        return cls(name=data["name"], data_type=DataType(data["type"]))


@dataclass(frozen=True)
class RelationSchema:
    """关系的 Schema，包含有序列集合。"""
    columns: Tuple[Column, ...]

    def __post_init__(self) -> None:
        names = [col.name for col in self.columns]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate column names in schema: {names}")

    @property
    def column_names(self) -> Tuple[str, ...]:
        return tuple(col.name for col in self.columns)

    def get_column(self, name: str) -> Optional[Column]:
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_type(self, name: str) -> Optional[DataType]:
        col = self.get_column(name)
        return col.data_type if col else None

    def has_column(self, name: str) -> bool:
        return self.get_column(name) is not None

    def index_of(self, name: str) -> int:
        for idx, col in enumerate(self.columns):
            if col.name == name:
                return idx
        raise KeyError(f"Column '{name}' not found in schema {self.column_names}")

    def with_prefix(self, prefix: str) -> RelationSchema:
        """返回为所有列名添加前缀的新 Schema。"""
        return RelationSchema(
            tuple(Column(f"{prefix}.{c.name}", c.data_type) for c in self.columns)
        )

    def to_dict(self) -> List[Dict[str, str]]:
        return [c.to_dict() for c in self.columns]

    @classmethod
    def from_dict(cls, data: Sequence[Dict[str, str]]) -> RelationSchema:
        return cls(tuple(Column.from_dict(d) for d in data))


@dataclass(frozen=True)
class Table:
    """不可变的内存关系表。"""
    schema: RelationSchema
    rows: Tuple[Tuple[Any, ...], ...]

    def __post_init__(self) -> None:
        col_count = len(self.schema.columns)
        for r_idx, row in enumerate(self.rows):
            if len(row) != col_count:
                raise ValueError(
                    f"Row {r_idx} length {len(row)} does not match schema column count {col_count}"
                )

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        return len(self.schema.columns)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema.to_dict(),
            "rows": [list(r) for r in self.rows],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Table:
        schema = RelationSchema.from_dict(data["schema"])
        rows = tuple(tuple(r) for r in data["rows"])
        return cls(schema=schema, rows=rows)


def tables_equal(t1: Table, t2: Table, check_row_order: bool = True) -> bool:
    """判断两张表格是否在结构与数据上完全等价。"""
    # 检查列名与类型
    if len(t1.schema.columns) != len(t2.schema.columns):
        return False
    for c1, c2 in zip(t1.schema.columns, t2.schema.columns):
        if c1.name != c2.name or c1.data_type != c2.data_type:
            return False

    if t1.num_rows != t2.num_rows:
        return False

    if check_row_order:
        return t1.rows == t2.rows
    else:
        # 无序比较：按 multiset 比较
        from collections import Counter
        return Counter(t1.rows) == Counter(t2.rows)

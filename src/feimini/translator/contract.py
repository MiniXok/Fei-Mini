"""结构化意图契约 (IntentSpec) 与 Schema 静态校验模块。

定义自然语言翻译器输出的中间表示，将自然语言意图结构化为受控的意图数据结构，
提供严格的静态 Schema 绑定校验，防止模型幻觉列名进入求解器。
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..dsl.ast import (
    ASTNode,
    CountNode,
    FilterNode,
    GroupByNode,
    JoinNode,
    LimitNode,
    PredicateOp,
    ProjectNode,
    ScanNode,
    SortDirection,
    SortNode,
    SumNode,
)
from ..dsl.grammar import DEFAULT_GRAMMAR
from ..dsl.types import Column, DataType, RelationSchema
from ..sqlite.schema import SQLiteDatabaseSchema, SQLiteTableInfo


@dataclass(frozen=True)
class AggregationIntent:
    """聚合意图。"""
    op: str  # "SUM" | "COUNT"
    column: str
    as_col: str


@dataclass(frozen=True)
class FilterIntent:
    """过滤条件意图。"""
    column: str
    op: PredicateOp
    value: Any


@dataclass(frozen=True)
class SortIntent:
    """排序意图。"""
    column: str
    direction: SortDirection


@dataclass(frozen=True)
class IntentSpec:
    """结构化用户意图契约。"""
    target_table: str
    target_columns: Tuple[str, ...]
    aggregations: Tuple[AggregationIntent, ...] = ()
    filters: Tuple[FilterIntent, ...] = ()
    sort: Optional[SortIntent] = None
    limit: Optional[int] = None
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None
    unsupported: bool = False
    unsupported_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_table": self.target_table,
            "target_columns": list(self.target_columns),
            "aggregations": [
                {"op": a.op, "column": a.column, "as_col": a.as_col} for a in self.aggregations
            ],
            "filters": [
                {"column": f.column, "op": f.op.value, "value": f.value} for f in self.filters
            ],
            "sort": {
                "column": self.sort.column,
                "direction": self.sort.direction.value,
            } if self.sort else None,
            "limit": self.limit,
            "clarification_needed": self.clarification_needed,
            "clarification_prompt": self.clarification_prompt,
            "unsupported": self.unsupported,
            "unsupported_reason": self.unsupported_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IntentSpec:
        aggs = tuple(
            AggregationIntent(
                op=a["op"],
                column=a["column"],
                as_col=a.get("as_col", DEFAULT_GRAMMAR.SUM_ALIAS if a["op"] == "SUM" else DEFAULT_GRAMMAR.COUNT_ALIAS),
            )
            for a in data.get("aggregations", ())
        )

        filts = []
        for f in data.get("filters", ()):
            op_str = f.get("op", "EQ")
            try:
                p_op = PredicateOp(op_str)
            except ValueError:
                p_op = PredicateOp.EQ
            filts.append(FilterIntent(column=f["column"], op=p_op, value=f["value"]))

        sort_obj = None
        if data.get("sort"):
            s_dict = data["sort"]
            dir_str = s_dict.get("direction", "ASC").upper()
            dir_enum = SortDirection.DESC if dir_str == "DESC" else SortDirection.ASC
            sort_obj = SortIntent(column=s_dict["column"], direction=dir_enum)

        return cls(
            target_table=data.get("target_table", ""),
            target_columns=tuple(data.get("target_columns", ())),
            aggregations=aggs,
            filters=tuple(filts),
            sort=sort_obj,
            limit=data.get("limit"),
            clarification_needed=bool(data.get("clarification_needed", False)),
            clarification_prompt=data.get("clarification_prompt"),
            unsupported=bool(data.get("unsupported", False)),
            unsupported_reason=data.get("unsupported_reason"),
        )


def validate_intent_against_schema(
    intent: IntentSpec,
    schema: SQLiteDatabaseSchema,
) -> Tuple[bool, Optional[str]]:
    """严格校验意图中的数据表与列名是否存在于真实的 SQLite 数据库中（支持多表）。"""
    if intent.clarification_needed or intent.unsupported:
        return True, None

    base_tbl = schema.get_table(intent.target_table)
    if not base_tbl:
        return False, f"Target table '{intent.target_table}' not found in database schema"

    # 提取数据库中所有合法表名与列名集合
    all_table_cols: Dict[str, Set[str]] = {
        tbl_name: set(tbl_info.column_names) for tbl_name, tbl_info in schema.tables.items()
    }
    all_known_cols = set.union(*all_table_cols.values()) if all_table_cols else set()

    # 1. 校验目标列
    for c in intent.target_columns:
        if any(c == a.as_col for a in intent.aggregations):
            continue  # 聚合别名合法
        if "." in c:
            t_name, col_name = c.split(".", 1)
            if t_name not in all_table_cols or col_name not in all_table_cols[t_name]:
                return False, f"Target column '{c}' not found in database schema"
        else:
            if c not in all_known_cols:
                return False, f"Target column '{c}' not found in database schema"

    # 2. 校验过滤字段
    for f in intent.filters:
        if "." in f.column:
            t_name, col_name = f.column.split(".", 1)
            if t_name not in all_table_cols or col_name not in all_table_cols[t_name]:
                return False, f"Filter column '{f.column}' not found in database schema"
        else:
            if f.column not in all_known_cols:
                return False, f"Filter column '{f.column}' not found in database schema"

    # 3. 校验聚合字段
    for a in intent.aggregations:
        if a.op == "SUM":
            if "." in a.column:
                t_name, col_name = a.column.split(".", 1)
                if t_name not in all_table_cols or col_name not in all_table_cols[t_name]:
                    return False, f"Aggregation column '{a.column}' not found in schema"
            else:
                if a.column not in all_known_cols:
                    return False, f"Aggregation column '{a.column}' not found in schema"

    return True, None

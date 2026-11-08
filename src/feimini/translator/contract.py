"""结构化意图契约 (IntentSpec) 与三态决策模型 (M6.1.3).

显式区分三类决策结果：
1. EXECUTE: 语义清晰且受支持，进入求解与执行流水线。
2. CLARIFY: 存在多重解释或缺少必要准则，向用户请求澄清。
3. ABSTAIN: 包含写操作、越权攻击或超出系统职责范围，安全拒答。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
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


class IntentDecision(str, Enum):
    """翻译决策三大状态。"""
    EXECUTE = "EXECUTE"
    CLARIFY = "CLARIFY"
    ABSTAIN = "ABSTAIN"


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
    decision: IntentDecision = IntentDecision.EXECUTE
    target_table: Optional[str] = None
    target_columns: Tuple[str, ...] = ()
    aggregations: Tuple[AggregationIntent, ...] = ()
    filters: Tuple[FilterIntent, ...] = ()
    sort: Optional[SortIntent] = None
    limit: Optional[int] = None
    clarification_prompt: Optional[str] = None
    abstain_reason: Optional[str] = None

    def __init__(
        self,
        decision: IntentDecision = IntentDecision.EXECUTE,
        target_table: Optional[str] = None,
        target_columns: Tuple[str, ...] = (),
        aggregations: Tuple[AggregationIntent, ...] = (),
        filters: Tuple[FilterIntent, ...] = (),
        sort: Optional[SortIntent] = None,
        limit: Optional[int] = None,
        clarification_prompt: Optional[str] = None,
        abstain_reason: Optional[str] = None,
        clarification_needed: Optional[bool] = None,
        unsupported: Optional[bool] = None,
        unsupported_reason: Optional[str] = None,
    ) -> None:
        if clarification_needed is True:
            decision = IntentDecision.CLARIFY
        elif unsupported is True:
            decision = IntentDecision.ABSTAIN

        object.__setattr__(self, "decision", decision)
        object.__setattr__(self, "target_table", target_table)
        object.__setattr__(self, "target_columns", target_columns)
        object.__setattr__(self, "aggregations", aggregations)
        object.__setattr__(self, "filters", filters)
        object.__setattr__(self, "sort", sort)
        object.__setattr__(self, "limit", limit)
        object.__setattr__(self, "clarification_prompt", clarification_prompt)
        object.__setattr__(self, "abstain_reason", abstain_reason or unsupported_reason)

    # 向后兼容属性
    @property
    def clarification_needed(self) -> bool:
        return self.decision == IntentDecision.CLARIFY

    @property
    def unsupported(self) -> bool:
        return self.decision == IntentDecision.ABSTAIN

    @property
    def unsupported_reason(self) -> Optional[str]:
        return self.abstain_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
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
            "unsupported_reason": self.abstain_reason,
            "abstain_reason": self.abstain_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IntentSpec:
        # 解析 decision 决策
        dec_str = data.get("decision", "").upper()
        if dec_str in ("EXECUTE", "CLARIFY", "ABSTAIN"):
            decision = IntentDecision(dec_str)
        elif data.get("clarification_needed"):
            decision = IntentDecision.CLARIFY
        elif data.get("unsupported"):
            decision = IntentDecision.ABSTAIN
        else:
            decision = IntentDecision.EXECUTE

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
            decision=decision,
            target_table=data.get("target_table"),
            target_columns=tuple(data.get("target_columns", ())),
            aggregations=aggs,
            filters=tuple(filts),
            sort=sort_obj,
            limit=data.get("limit"),
            clarification_prompt=data.get("clarification_prompt"),
            abstain_reason=data.get("abstain_reason") or data.get("unsupported_reason"),
        )


def validate_intent_against_schema(
    intent: IntentSpec,
    schema: SQLiteDatabaseSchema,
) -> Tuple[bool, Optional[str]]:
    """严格校验意图中的数据表与列名是否存在于真实的 SQLite 数据库中。"""
    if intent.decision != IntentDecision.EXECUTE:
        return True, None

    if not intent.target_table:
        return False, "Target table is missing for executable query"

    base_tbl = schema.get_table(intent.target_table)
    if not base_tbl:
        return False, f"Target table '{intent.target_table}' not found in database schema"

    all_table_cols: Dict[str, Set[str]] = {
        tbl_name: set(tbl_info.column_names) for tbl_name, tbl_info in schema.tables.items()
    }
    all_known_cols = set.union(*all_table_cols.values()) if all_table_cols else set()

    for c in intent.target_columns:
        if any(c == a.as_col for a in intent.aggregations):
            continue
        if "." in c:
            t_name, col_name = c.split(".", 1)
            if t_name not in all_table_cols or col_name not in all_table_cols[t_name]:
                return False, f"Target column '{c}' not found in database schema"
        else:
            if c not in all_known_cols:
                return False, f"Target column '{c}' not found in database schema"

    for f in intent.filters:
        if "." in f.column:
            t_name, col_name = f.column.split(".", 1)
            if t_name not in all_table_cols or col_name not in all_table_cols[t_name]:
                return False, f"Filter column '{f.column}' not found in database schema"
        else:
            if f.column not in all_known_cols:
                return False, f"Filter column '{f.column}' not found in database schema"

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

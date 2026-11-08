"""MiniRel 单一事实来源 (Single Source of Truth) 语法定义与配置。

定义所有算子规范、合法操作符、标准别名、有效参数取值范围与投影宽度上限。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from .types import PredicateOp, SortDirection


@dataclass(frozen=True)
class MiniRelGrammar:
    """MiniRel 关系算子语法规范。"""

    # 合法算子名称集合
    OPERATORS: Tuple[str, ...] = (
        "SCAN",
        "FILTER",
        "PROJECT",
        "JOIN",
        "GROUP_BY",
        "SUM",
        "COUNT",
        "SORT",
        "LIMIT",
    )

    # 合法谓词比较符集合
    PREDICATE_OPS_CATEGORICAL: Tuple[PredicateOp, ...] = (
        PredicateOp.EQ,
        PredicateOp.NEQ,
    )
    PREDICATE_OPS_ORDERED: Tuple[PredicateOp, ...] = (
        PredicateOp.EQ,
        PredicateOp.NEQ,
        PredicateOp.GT,
        PredicateOp.LT,
        PredicateOp.GTE,
        PredicateOp.LTE,
    )

    # 排序方向
    SORT_DIRECTIONS: Tuple[SortDirection, ...] = (
        SortDirection.ASC,
        SortDirection.DESC,
    )

    # 合法 LIMIT 取值集
    LIMIT_VALUES: Tuple[int, ...] = (2, 3, 4, 5)

    # 投影列数上限
    MAX_PROJECTION_WIDTH: int = 3

    # 聚合算子统一标准输出别名
    COUNT_ALIAS: str = "total_cnt"
    SUM_ALIAS: str = "sum_metric"
    JOIN_AGG_ALIAS: str = "agg_metric"

    # 最大候选常量采样数（从每个列的观察值中提取）
    MAX_CONSTANTS_PER_COLUMN: int = 5


# 全局默认语法实例
DEFAULT_GRAMMAR = MiniRelGrammar()

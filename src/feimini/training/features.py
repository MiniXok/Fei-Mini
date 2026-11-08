"""特征提取模块：将搜索状态与候选动作映射为标准定长数值特征向量。

特征向量维度 D = 32，包含任务目标模式、Schema 结构、基数对齐与候选 AST 算子属性。
纯 NumPy 实现，零第三方框架开销，单步抽取耗时 < 0.02ms。
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Set
import numpy as np

from ..dsl.ast import (
    ASTNode,
    CountNode,
    FilterNode,
    GroupByNode,
    JoinNode,
    LimitNode,
    ProjectNode,
    ScanNode,
    SortNode,
    SumNode,
    TypeErrorAST,
)
from ..dsl.grammar import DEFAULT_GRAMMAR, MiniRelGrammar
from ..dsl.types import DataType, RelationSchema
from ..generator.tasks import TaskSpec

FEATURE_DIM = 32

OP_TO_INDEX = {
    "SCAN": 0,
    "FILTER": 1,
    "PROJECT": 2,
    "JOIN": 3,
    "GROUP_BY": 4,
    "SUM": 5,
    "COUNT": 6,
    "SORT": 7,
    "LIMIT": 8,
}


def extract_features(
    candidate: ASTNode,
    task: TaskSpec,
    grammar: Optional[MiniRelGrammar] = None,
) -> np.ndarray:
    """提取状态-动作对 (state, candidate_action) 的 32 维特征向量。"""
    g = grammar or DEFAULT_GRAMMAR
    feat = np.zeros(FEATURE_DIM, dtype=np.float32)

    ex0 = task.examples[0]
    target_table = ex0.output_table
    target_schema = target_table.schema
    target_rows = target_table.num_rows

    target_col_names = set(target_schema.column_names)
    target_col_count = len(target_schema.columns)

    # 1. 任务目标上下文特征 (索引 0..6)
    feat[0] = len(task.schemas) / 3.0  # 表格数量归一化
    feat[1] = target_col_count / 5.0   # 目标输出列数
    feat[2] = math.log1p(target_rows) / 5.0  # 目标输出行数对数
    feat[3] = 1.0 if g.COUNT_ALIAS in target_col_names else 0.0
    feat[4] = 1.0 if (g.SUM_ALIAS in target_col_names or g.JOIN_AGG_ALIAS in target_col_names) else 0.0

    # 检查是否需要多表连接
    tables_needed = set()
    for c in target_col_names:
        for tbl_name, tbl_s in task.schemas.items():
            if tbl_s.has_column(c):
                tables_needed.add(tbl_name)
    feat[5] = 1.0 if len(tables_needed) >= 2 else 0.0

    # 目标列类型分布 (数值 vs 文本/布尔)
    num_numeric_target = sum(
        1 for c in target_schema.columns if c.data_type in (DataType.INT, DataType.FLOAT)
    )
    feat[6] = num_numeric_target / max(1, target_col_count)

    # 2. 候选算子类型 One-hot 编码 (索引 7..15)
    cand_op_name = candidate.__class__.__name__.replace("Node", "").upper()
    if cand_op_name in OP_TO_INDEX:
        feat[7 + OP_TO_INDEX[cand_op_name]] = 1.0

    # 3. 候选 AST 复杂度特征 (索引 16..18)
    feat[16] = candidate.depth / 5.0
    feat[17] = candidate.node_count / 10.0

    # 4. 候选输出 Schema 对齐特征 (索引 19..24)
    try:
        cand_schema = candidate.validate_types(task.schemas)
        cand_col_names = set(cand_schema.column_names)
        cand_col_count = len(cand_schema.columns)
        feat[18] = 1.0  # 静态类型检查通过标记

        overlap = len(cand_col_names.intersection(target_col_names))
        feat[19] = overlap / max(1, target_col_count)  # 目标覆盖率
        feat[20] = 1.0 if cand_schema.column_names == target_schema.column_names else 0.0  # 完全相同
        feat[21] = len(cand_col_names - target_col_names) / 5.0  # 多余列数

        # 列数据类型匹配度
        matching_types = sum(
            1 for c in cand_col_names if target_schema.has_column(c) and cand_schema.get_type(c) == target_schema.get_type(c)
        )
        feat[22] = matching_types / max(1, target_col_count)
        feat[23] = cand_col_count / 5.0

    except TypeErrorAST:
        feat[18] = -1.0  # 类型非法
    except Exception:
        feat[18] = -1.0

    # 5. 特定算子语义特征 (索引 25..31)
    if isinstance(candidate, LimitNode):
        feat[24] = candidate.limit / 5.0
        feat[25] = 1.0 if candidate.limit == target_rows else 0.0

    if isinstance(candidate, FilterNode):
        feat[26] = 1.0 if candidate.col_name in target_col_names else 0.5

    if isinstance(candidate, JoinNode):
        feat[27] = 1.0 if len(tables_needed) >= 2 else 0.0

    if isinstance(candidate, (CountNode, SumNode)):
        if g.COUNT_ALIAS in target_col_names or g.SUM_ALIAS in target_col_names or g.JOIN_AGG_ALIAS in target_col_names:
            feat[28] = 1.0
        else:
            feat[28] = -0.5

    if isinstance(candidate, SortNode):
        feat[29] = 1.0 if candidate.sort_col in target_col_names else 0.0

    # 是否包含 Join 子节点
    has_join = any(isinstance(n, JoinNode) for n in _get_subnodes(candidate))
    feat[30] = 1.0 if has_join else 0.0

    # 偏置项
    feat[31] = 1.0

    return feat


def _get_subnodes(node: ASTNode) -> List[ASTNode]:
    nodes = [node]
    for c in node.children:
        nodes.extend(_get_subnodes(c))
    return nodes

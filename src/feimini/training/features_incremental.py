"""增量与三级状态特征提取模块 (M5.6).

将特征细分为三级架构：
A. 任务不变量 (TaskInvariantState): 静态 Schema、外键依赖与目标表元数据，预计算一次。
B. 搜索状态 (PartialSearchState): 记录当前局部 AST 的前缀深度、节点数、算子历史与 Join 拓扑。
C. 动作增量 (CandidateActionFeatures): 仅针对最新动作计算增量，极大降低单步提取开销。

保证输出特征向量与原始 features.py 输出 100% 数值与语义等价。
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Set, Tuple
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
from .features import FEATURE_DIM, OP_TO_INDEX


class TaskInvariantState:
    """A 级特征：任务级不可变上下文（每个任务初始化一次）。"""

    def __init__(self, task: TaskSpec, grammar: Optional[MiniRelGrammar] = None) -> None:
        self.task = task
        self.grammar = grammar or DEFAULT_GRAMMAR

        ex0 = task.examples[0]
        self.target_table = ex0.output_table
        self.target_schema = self.target_table.schema
        self.target_rows = self.target_table.num_rows

        self.target_col_names: Set[str] = set(self.target_schema.column_names)
        self.target_col_count: int = len(self.target_schema.columns)

        # 快速类型映射
        self.target_type_map: Dict[str, DataType] = {
            c.name: c.data_type for c in self.target_schema.columns
        }

        # 依赖表格集合
        self.tables_needed: Set[str] = set()
        for c in self.target_col_names:
            for tbl_name, tbl_s in task.schemas.items():
                if tbl_s.has_column(c):
                    self.tables_needed.add(tbl_name)
        self.has_multiple_tables_needed: float = 1.0 if len(self.tables_needed) >= 2 else 0.0

        # 预计算 A 级静态向量切片
        self.static_features = np.zeros(FEATURE_DIM, dtype=np.float32)
        self.static_features[0] = len(task.schemas) / 3.0
        self.static_features[1] = self.target_col_count / 5.0
        self.static_features[2] = math.log1p(self.target_rows) / 5.0
        self.static_features[3] = 1.0 if self.grammar.COUNT_ALIAS in self.target_col_names else 0.0
        self.static_features[4] = 1.0 if (
            self.grammar.SUM_ALIAS in self.target_col_names or self.grammar.JOIN_AGG_ALIAS in self.target_col_names
        ) else 0.0
        self.static_features[5] = self.has_multiple_tables_needed

        num_numeric = sum(
            1 for c in self.target_schema.columns if c.data_type in (DataType.INT, DataType.FLOAT)
        )
        self.static_features[6] = num_numeric / max(1, self.target_col_count)
        self.static_features[31] = 1.0  # 偏置项


class PartialSearchState:
    """B 级特征：搜索中间节点前缀状态。在树搜索扩展中继承与维护。"""

    __slots__ = ("depth", "node_count", "has_join", "output_schema", "column_names_set")

    def __init__(
        self,
        depth: int = 1,
        node_count: int = 1,
        has_join: bool = False,
        output_schema: Optional[RelationSchema] = None,
    ) -> None:
        self.depth = depth
        self.node_count = node_count
        self.has_join = has_join
        self.output_schema = output_schema
        self.column_names_set: Optional[Set[str]] = (
            set(output_schema.column_names) if output_schema else None
        )

    def branch(
        self,
        new_depth: int,
        new_node_count: int,
        added_join: bool = False,
        new_schema: Optional[RelationSchema] = None,
    ) -> PartialSearchState:
        """从父状态派生新搜索状态。"""
        return PartialSearchState(
            depth=new_depth,
            node_count=new_node_count,
            has_join=self.has_join or added_join,
            output_schema=new_schema,
        )


class IncrementalFeatureExtractor:
    """增量特征提取执行器。"""

    @staticmethod
    def extract(
        candidate: ASTNode,
        inv_state: TaskInvariantState,
        partial_state: Optional[PartialSearchState] = None,
    ) -> np.ndarray:
        """计算候选 AST 的完整 32 维特征向量。"""
        feat = inv_state.static_features.copy()

        # 算子 One-hot (7..15)
        cand_op_name = candidate.__class__.__name__.replace("Node", "").upper()
        if cand_op_name in OP_TO_INDEX:
            feat[7 + OP_TO_INDEX[cand_op_name]] = 1.0

        # 深度与节点复杂度 (16..17)
        if partial_state:
            feat[16] = partial_state.depth / 5.0
            feat[17] = partial_state.node_count / 10.0
            has_join = partial_state.has_join or isinstance(candidate, JoinNode)
        else:
            feat[16] = candidate.depth / 5.0
            feat[17] = candidate.node_count / 10.0
            has_join = _check_join_recursive(candidate)

        # 候选输出 Schema 对齐 (18..23)
        try:
            cand_schema = candidate.validate_types(inv_state.task.schemas)
            cand_col_names = set(cand_schema.column_names)
            cand_col_count = len(cand_schema.columns)
            feat[18] = 1.0

            overlap = len(cand_col_names.intersection(inv_state.target_col_names))
            feat[19] = overlap / max(1, inv_state.target_col_count)
            feat[20] = 1.0 if cand_schema.column_names == inv_state.target_schema.column_names else 0.0
            feat[21] = len(cand_col_names - inv_state.target_col_names) / 5.0

            matching_types = 0
            for col in cand_schema.columns:
                if col.name in inv_state.target_type_map and inv_state.target_type_map[col.name] == col.data_type:
                    matching_types += 1
            feat[22] = matching_types / max(1, inv_state.target_col_count)
            feat[23] = cand_col_count / 5.0

        except TypeErrorAST:
            feat[18] = -1.0
        except Exception:
            feat[18] = -1.0

        # 特定算子语义特征 (24..30)
        if isinstance(candidate, LimitNode):
            feat[24] = candidate.limit / 5.0
            feat[25] = 1.0 if candidate.limit == inv_state.target_rows else 0.0

        if isinstance(candidate, FilterNode):
            feat[26] = 1.0 if candidate.col_name in inv_state.target_col_names else 0.5

        if isinstance(candidate, JoinNode):
            feat[27] = inv_state.has_multiple_tables_needed

        if isinstance(candidate, (CountNode, SumNode)):
            if (
                inv_state.grammar.COUNT_ALIAS in inv_state.target_col_names
                or inv_state.grammar.SUM_ALIAS in inv_state.target_col_names
                or inv_state.grammar.JOIN_AGG_ALIAS in inv_state.target_col_names
            ):
                feat[28] = 1.0
            else:
                feat[28] = -0.5

        if isinstance(candidate, SortNode):
            feat[29] = 1.0 if candidate.sort_col in inv_state.target_col_names else 0.0

        feat[30] = 1.0 if has_join else 0.0

        return feat


def _check_join_recursive(node: ASTNode) -> bool:
    if isinstance(node, JoinNode):
        return True
    for c in node.children:
        if _check_join_recursive(c):
            return True
    return False

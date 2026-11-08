"""MiniRel 语法树 (AST) 节点定义与静态类型校验。

支持的 9 种核心算子：
SCAN, FILTER, PROJECT, JOIN, GROUP_BY, SUM, COUNT, SORT, LIMIT。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .types import Column, DataType, PredicateOp, RelationSchema, SortDirection


class TypeErrorAST(Exception):
    """AST 静态类型检查异常。"""
    pass


class ASTNode(ABC):
    """AST 节点抽象基类。"""

    @abstractmethod
    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        """递归静态检查节点类型并返回推断出的输出 RelationSchema。"""
        pass

    @property
    @abstractmethod
    def children(self) -> Tuple[ASTNode, ...]:
        """子节点元组。"""
        pass

    @property
    def depth(self) -> int:
        """树的最大深度。"""
        if not self.children:
            return 1
        return 1 + max(c.depth for c in self.children)

    @property
    def node_count(self) -> int:
        """树中所有节点总数。"""
        return 1 + sum(c.node_count for c in self.children)

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """将 AST 序列化为结构化字典。"""
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ASTNode:
        """从字典反序列化生成 AST 节点。"""
        op = data.get("op")
        if op == "SCAN":
            return ScanNode(table_name=data["table_name"])
        elif op == "FILTER":
            return FilterNode(
                source=ASTNode.from_dict(data["source"]),
                col_name=data["col_name"],
                predicate_op=PredicateOp(data["predicate_op"]),
                value=data["value"],
            )
        elif op == "PROJECT":
            return ProjectNode(
                source=ASTNode.from_dict(data["source"]),
                columns=tuple(data["columns"]),
            )
        elif op == "JOIN":
            return JoinNode(
                left=ASTNode.from_dict(data["left"]),
                right=ASTNode.from_dict(data["right"]),
                left_col=data["left_col"],
                right_col=data["right_col"],
            )
        elif op == "GROUP_BY":
            return GroupByNode(
                source=ASTNode.from_dict(data["source"]),
                group_cols=tuple(data["group_cols"]),
            )
        elif op == "SUM":
            return SumNode(
                source=ASTNode.from_dict(data["source"]),
                agg_col=data["agg_col"],
                as_col=data.get("as_col", "sum_val"),
            )
        elif op == "COUNT":
            return CountNode(
                source=ASTNode.from_dict(data["source"]),
                as_col=data.get("as_col", "count_val"),
            )
        elif op == "SORT":
            return SortNode(
                source=ASTNode.from_dict(data["source"]),
                sort_col=data["sort_col"],
                direction=SortDirection(data.get("direction", "ASC")),
            )
        elif op == "LIMIT":
            return LimitNode(
                source=ASTNode.from_dict(data["source"]),
                limit=int(data["limit"]),
            )
        else:
            raise ValueError(f"Unknown AST operation: {op}")


@dataclass(frozen=True)
class ScanNode(ASTNode):
    """扫描指定表格。"""
    table_name: str

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return ()

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        if self.table_name not in env_schemas:
            raise TypeErrorAST(f"Table '{self.table_name}' does not exist in environment")
        return env_schemas[self.table_name]

    def to_dict(self) -> Dict[str, Any]:
        return {"op": "SCAN", "table_name": self.table_name}


@dataclass(frozen=True)
class FilterNode(ASTNode):
    """按谓词条件过滤行。"""
    source: ASTNode
    col_name: str
    predicate_op: PredicateOp
    value: Any

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.source,)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        schema = self.source.validate_types(env_schemas)
        col = schema.get_column(self.col_name)
        if col is None:
            raise TypeErrorAST(
                f"Filter column '{self.col_name}' not found in schema {schema.column_names}"
            )
        # 标量值类型校验
        try:
            col.data_type.coerce(self.value)
        except Exception as e:
            raise TypeErrorAST(
                f"Filter value '{self.value}' incompatible with column type {col.data_type}: {e}"
            )
        return schema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "FILTER",
            "source": self.source.to_dict(),
            "col_name": self.col_name,
            "predicate_op": self.predicate_op.value,
            "value": self.value,
        }


@dataclass(frozen=True)
class ProjectNode(ASTNode):
    """选择投影指定子集的列。"""
    source: ASTNode
    columns: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("ProjectNode must specify at least one column")

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.source,)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        schema = self.source.validate_types(env_schemas)
        out_cols: List[Column] = []
        for col_name in self.columns:
            col = schema.get_column(col_name)
            if col is None:
                raise TypeErrorAST(
                    f"Projected column '{col_name}' not found in schema {schema.column_names}"
                )
            out_cols.append(col)
        return RelationSchema(tuple(out_cols))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "PROJECT",
            "source": self.source.to_dict(),
            "columns": list(self.columns),
        }


@dataclass(frozen=True)
class JoinNode(ASTNode):
    """两张表格的等值内连接。"""
    left: ASTNode
    right: ASTNode
    left_col: str
    right_col: str

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.left, self.right)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        left_schema = self.left.validate_types(env_schemas)
        right_schema = self.right.validate_types(env_schemas)

        col_l = left_schema.get_column(self.left_col)
        if col_l is None:
            raise TypeErrorAST(
                f"Join left column '{self.left_col}' not found in left schema {left_schema.column_names}"
            )

        col_r = right_schema.get_column(self.right_col)
        if col_r is None:
            raise TypeErrorAST(
                f"Join right column '{self.right_col}' not found in right schema {right_schema.column_names}"
            )

        if col_l.data_type != col_r.data_type:
            raise TypeErrorAST(
                f"Join type mismatch: {col_l.data_type} vs {col_r.data_type}"
            )

        # 构建连接后的列名：如果有重复列名，则进行前缀区分
        out_cols: List[Column] = list(left_schema.columns)
        left_names = set(left_schema.column_names)
        for col in right_schema.columns:
            if col.name in left_names:
                # 产生重名时使用 right. 规范命名
                out_cols.append(Column(f"right.{col.name}", col.data_type))
            else:
                out_cols.append(col)
        return RelationSchema(tuple(out_cols))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "JOIN",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "left_col": self.left_col,
            "right_col": self.right_col,
        }


@dataclass(frozen=True)
class GroupByNode(ASTNode):
    """分组节点，为后续聚合算子标记分组键。"""
    source: ASTNode
    group_cols: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.group_cols:
            raise ValueError("GroupByNode must specify at least one grouping column")

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.source,)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        schema = self.source.validate_types(env_schemas)
        for g_col in self.group_cols:
            if not schema.has_column(g_col):
                raise TypeErrorAST(
                    f"GroupBy column '{g_col}' not found in schema {schema.column_names}"
                )
        return schema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "GROUP_BY",
            "source": self.source.to_dict(),
            "group_cols": list(self.group_cols),
        }


@dataclass(frozen=True)
class SumNode(ASTNode):
    """求和聚合算子。若上游是 GroupByNode，则按分组求和，否则计算全表总和。"""
    source: ASTNode
    agg_col: str
    as_col: str = "sum_val"

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.source,)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        schema = self.source.validate_types(env_schemas)
        col = schema.get_column(self.agg_col)
        if col is None:
            raise TypeErrorAST(
                f"Sum column '{self.agg_col}' not found in schema {schema.column_names}"
            )
        if col.data_type not in (DataType.INT, DataType.FLOAT):
            raise TypeErrorAST(
                f"Sum column '{self.agg_col}' must be numeric (INT/FLOAT), got {col.data_type}"
            )

        out_cols: List[Column] = []
        if isinstance(self.source, GroupByNode):
            for g_col in self.source.group_cols:
                out_cols.append(schema.get_column(g_col))  # type: ignore
        out_cols.append(Column(self.as_col, col.data_type))
        return RelationSchema(tuple(out_cols))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "SUM",
            "source": self.source.to_dict(),
            "agg_col": self.agg_col,
            "as_col": self.as_col,
        }


@dataclass(frozen=True)
class CountNode(ASTNode):
    """计数聚合算子。若上游是 GroupByNode，则按分组计数，否则计算全表行数。"""
    source: ASTNode
    as_col: str = "count_val"

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.source,)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        schema = self.source.validate_types(env_schemas)
        out_cols: List[Column] = []
        if isinstance(self.source, GroupByNode):
            for g_col in self.source.group_cols:
                out_cols.append(schema.get_column(g_col))  # type: ignore
        out_cols.append(Column(self.as_col, DataType.INT))
        return RelationSchema(tuple(out_cols))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "COUNT",
            "source": self.source.to_dict(),
            "as_col": self.as_col,
        }


@dataclass(frozen=True)
class SortNode(ASTNode):
    """排序算子。"""
    source: ASTNode
    sort_col: str
    direction: SortDirection = SortDirection.ASC

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.source,)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        schema = self.source.validate_types(env_schemas)
        if not schema.has_column(self.sort_col):
            raise TypeErrorAST(
                f"Sort column '{self.sort_col}' not found in schema {schema.column_names}"
            )
        return schema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "SORT",
            "source": self.source.to_dict(),
            "sort_col": self.sort_col,
            "direction": self.direction.value,
        }


@dataclass(frozen=True)
class LimitNode(ASTNode):
    """截取前 N 行算子。"""
    source: ASTNode
    limit: int

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError(f"Limit must be > 0, got {self.limit}")

    @property
    def children(self) -> Tuple[ASTNode, ...]:
        return (self.source,)

    def validate_types(self, env_schemas: Dict[str, RelationSchema]) -> RelationSchema:
        return self.source.validate_types(env_schemas)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": "LIMIT",
            "source": self.source.to_dict(),
            "limit": self.limit,
        }

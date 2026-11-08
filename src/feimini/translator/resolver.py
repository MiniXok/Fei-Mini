"""确定性意图到 MiniRel AST 计划解析器。

将结构化 IntentSpec 结合 SQLiteDatabaseSchema 的外键依赖关系，
解析并构建精确的、强类型的 MiniRel 关系语法树，支持自动外键连接拓扑发现。
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple

from ..dsl.ast import (
    ASTNode,
    CountNode,
    FilterNode,
    GroupByNode,
    JoinNode,
    LimitNode,
    ProjectNode,
    ScanNode,
    SortDirection,
    SortNode,
    SumNode,
    TypeErrorAST,
)
from ..dsl.types import DataType, RelationSchema
from ..sqlite.schema import SQLiteDatabaseSchema
from .contract import IntentSpec


class IntentResolutionError(Exception):
    """意图到 MiniRel 规划解析异常。"""
    pass


class IntentResolver:
    """确定性意图规划解析器。"""

    @staticmethod
    def resolve_to_ast(intent: IntentSpec, schema: SQLiteDatabaseSchema) -> ASTNode:
        """根据 IntentSpec 规划出合法的 MiniRel AST。"""
        if intent.clarification_needed:
            raise IntentResolutionError(f"Cannot resolve intent requiring clarification: {intent.clarification_prompt}")
        if intent.unsupported:
            raise IntentResolutionError(f"Cannot resolve unsupported intent: {intent.unsupported_reason}")

        base_tbl = schema.get_table(intent.target_table)
        if not base_tbl:
            raise IntentResolutionError(f"Target table '{intent.target_table}' not found in schema")

        # 检查是否涉及多表关联：自动检查所有被引用的列属于哪些表
        tables_needed: Set[str] = {intent.target_table}

        # 检查目标列来源
        for c in intent.target_columns:
            if "." in c:
                tables_needed.add(c.split(".")[0])
            else:
                for t_name, t_info in schema.tables.items():
                    if c in t_info.column_names:
                        tables_needed.add(t_name)

        # 检查聚合列来源
        for a in intent.aggregations:
            if "." in a.column:
                tables_needed.add(a.column.split(".")[0])
            else:
                for t_name, t_info in schema.tables.items():
                    if a.column in t_info.column_names:
                        tables_needed.add(t_name)

        curr: ASTNode = ScanNode(intent.target_table)

        # 1. 连接构建 (若跨表)
        if len(tables_needed) >= 2:
            other_tbl_name = [t for t in tables_needed if t != intent.target_table][0]
            other_tbl = schema.get_table(other_tbl_name)
            if not other_tbl:
                raise IntentResolutionError(f"Referenced table '{other_tbl_name}' not in schema")

            # 寻找外键连接路径
            join_found = False
            # 检查 target_table -> other_tbl
            for fk in base_tbl.foreign_keys:
                if fk.target_table == other_tbl_name:
                    curr = JoinNode(ScanNode(intent.target_table), ScanNode(other_tbl_name), fk.from_column, fk.to_column)
                    join_found = True
                    break

            if not join_found:
                # 检查 other_tbl -> target_table
                for fk in other_tbl.foreign_keys:
                    if fk.target_table == intent.target_table:
                        curr = JoinNode(ScanNode(intent.target_table), ScanNode(other_tbl_name), fk.to_column, fk.from_column)
                        join_found = True
                        break

            if not join_found:
                raise IntentResolutionError(f"No foreign-key relationship connects '{intent.target_table}' and '{other_tbl_name}'")

        # 2. 过滤算子挂载
        for f in intent.filters:
            col_name = f.column.split(".")[-1]
            curr = FilterNode(curr, col_name, f.op, f.value)

        # 3. 聚合算子挂载
        if intent.aggregations:
            agg = intent.aggregations[0]
            agg_col = agg.column.split(".")[-1]

            # 确定分组列：取 target_columns 中非聚合别名的列
            group_cols = [
                c.split(".")[-1] for c in intent.target_columns if c != agg.as_col and c.split(".")[-1] != agg.as_col
            ]

            if group_cols:
                curr = GroupByNode(curr, tuple(group_cols))
                if agg.op == "COUNT":
                    curr = CountNode(curr, as_col=agg.as_col)
                elif agg.op == "SUM":
                    curr = SumNode(curr, agg_col, as_col=agg.as_col)
                else:
                    raise IntentResolutionError(f"Unsupported aggregation operator: {agg.op}")
            else:
                # 全局聚合
                if agg.op == "COUNT":
                    curr = CountNode(curr, as_col=agg.as_col)
                elif agg.op == "SUM":
                    curr = SumNode(curr, agg_col, as_col=agg.as_col)
                else:
                    raise IntentResolutionError(f"Unsupported aggregation operator: {agg.op}")

        # 4. 投影算子挂载 (非聚合时)
        elif intent.target_columns:
            cols = tuple(c.split(".")[-1] for c in intent.target_columns)
            curr = ProjectNode(curr, cols)

        # 5. 排序算子挂载
        if intent.sort:
            sort_col = intent.sort.column.split(".")[-1]
            if intent.aggregations:
                agg = intent.aggregations[0]
                # 若排序字段指向聚合测度，对齐为聚合输出别名
                if group_cols and sort_col not in group_cols and sort_col != agg.as_col:
                    sort_col = agg.as_col
            curr = SortNode(curr, sort_col, intent.sort.direction)

        # 6. 截断算子挂载
        if intent.limit and intent.limit > 0:
            curr = LimitNode(curr, int(intent.limit))

        return curr

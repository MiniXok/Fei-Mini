"""MiniRel 确定性参考解释器。

执行类型合规的 MiniRel AST 并在给定的内存数据库实例上产生输出表格。
包含行数超限保护与语义执行错误诊断。
"""

from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .ast import (
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
from .types import Column, DataType, RelationSchema, SortDirection, Table, tables_equal


class ExecutionError(Exception):
    """MiniRel 解释器执行期异常。"""
    pass


class MiniRelInterpreter:
    """MiniRel 参考解释器。"""

    def __init__(self, max_rows: int = 100_000) -> None:
        self.max_rows = max_rows

    def execute(self, program: ASTNode, database: Dict[str, Table]) -> Table:
        """验证并在指定数据库实例上执行程序。"""
        env_schemas = {name: tbl.schema for name, tbl in database.items()}
        # 1. 静态类型与 Schema 校验
        out_schema = program.validate_types(env_schemas)

        # 2. 递归求值
        result_table = self._eval_node(program, database)

        # 3. 校验输出 Schema 一致性
        if result_table.schema != out_schema:
            raise ExecutionError(
                f"Interpreter output schema mismatch: expected {out_schema}, got {result_table.schema}"
            )
        return result_table

    def _eval_node(self, node: ASTNode, database: Dict[str, Table]) -> Table:
        if isinstance(node, ScanNode):
            if node.table_name not in database:
                raise ExecutionError(f"Table '{node.table_name}' not found in database")
            return database[node.table_name]

        elif isinstance(node, FilterNode):
            src_table = self._eval_node(node.source, database)
            col_idx = src_table.schema.index_of(node.col_name)
            filtered_rows: List[Tuple[Any, ...]] = []
            for row in src_table.rows:
                val = row[col_idx]
                if node.predicate_op.evaluate(val, node.value):
                    filtered_rows.append(row)
            return Table(schema=src_table.schema, rows=tuple(filtered_rows))

        elif isinstance(node, ProjectNode):
            src_table = self._eval_node(node.source, database)
            indices = [src_table.schema.index_of(col) for col in node.columns]
            projected_cols = tuple(src_table.schema.get_column(col) for col in node.columns)  # type: ignore
            out_schema = RelationSchema(projected_cols)
            projected_rows = tuple(
                tuple(row[i] for i in indices) for row in src_table.rows
            )
            return Table(schema=out_schema, rows=projected_rows)

        elif isinstance(node, JoinNode):
            left_table = self._eval_node(node.left, database)
            right_table = self._eval_node(node.right, database)

            idx_l = left_table.schema.index_of(node.left_col)
            idx_r = right_table.schema.index_of(node.right_col)

            # 构建右表哈希索引
            right_hash: Dict[Any, List[Tuple[Any, ...]]] = defaultdict(list)
            for r_row in right_table.rows:
                right_hash[r_row[idx_r]].append(r_row)

            # 构建输出 Schema
            out_cols: List[Column] = list(left_table.schema.columns)
            left_names = set(left_table.schema.column_names)
            for col in right_table.schema.columns:
                if col.name in left_names:
                    out_cols.append(Column(f"right.{col.name}", col.data_type))
                else:
                    out_cols.append(col)
            out_schema = RelationSchema(tuple(out_cols))

            joined_rows: List[Tuple[Any, ...]] = []
            for l_row in left_table.rows:
                key = l_row[idx_l]
                if key in right_hash:
                    for r_row in right_hash[key]:
                        joined_rows.append(l_row + r_row)
                        if len(joined_rows) > self.max_rows:
                            raise ExecutionError(
                                f"Join exceeded maximum intermediate row limit {self.max_rows}"
                            )

            return Table(schema=out_schema, rows=tuple(joined_rows))

        elif isinstance(node, GroupByNode):
            src_table = self._eval_node(node.source, database)
            key_indices = [src_table.schema.index_of(c) for c in node.group_cols]
            out_cols = tuple(src_table.schema.get_column(c) for c in node.group_cols)  # type: ignore
            out_schema = RelationSchema(out_cols)

            # 单独作为终端算子时，提取唯一键值并保留顺序
            seen = set()
            distinct_keys: List[Tuple[Any, ...]] = []
            for row in src_table.rows:
                key = tuple(row[i] for i in key_indices)
                if key not in seen:
                    seen.add(key)
                    distinct_keys.append(key)
            return Table(schema=out_schema, rows=tuple(distinct_keys))

        elif isinstance(node, SumNode):
            if isinstance(node.source, GroupByNode):
                # 分组求和
                src_table = self._eval_node(node.source.source, database)
                key_indices = [src_table.schema.index_of(c) for c in node.source.group_cols]
                agg_idx = src_table.schema.index_of(node.agg_col)
                agg_type = src_table.schema.columns[agg_idx].data_type

                groups: Dict[Tuple[Any, ...], List[Any]] = defaultdict(list)
                # 记录分组出现的顺序以保证结果稳定
                ordered_keys: List[Tuple[Any, ...]] = []
                for row in src_table.rows:
                    key = tuple(row[i] for i in key_indices)
                    if key not in groups:
                        ordered_keys.append(key)
                    groups[key].append(row[agg_idx])

                out_cols = [src_table.schema.get_column(c) for c in node.source.group_cols]  # type: ignore
                out_cols.append(Column(node.as_col, agg_type))
                out_schema = RelationSchema(tuple(out_cols))

                result_rows: List[Tuple[Any, ...]] = []
                for key in ordered_keys:
                    vals = groups[key]
                    s = sum(vals) if agg_type == DataType.FLOAT else int(sum(vals))
                    result_rows.append(key + (s,))
                return Table(schema=out_schema, rows=tuple(result_rows))
            else:
                # 全表求和
                src_table = self._eval_node(node.source, database)
                agg_idx = src_table.schema.index_of(node.agg_col)
                agg_type = src_table.schema.columns[agg_idx].data_type
                out_schema = RelationSchema((Column(node.as_col, agg_type),))

                if not src_table.rows:
                    s_val = 0.0 if agg_type == DataType.FLOAT else 0
                else:
                    vals = [r[agg_idx] for r in src_table.rows if r[agg_idx] is not None]
                    s_val = sum(vals) if agg_type == DataType.FLOAT else int(sum(vals))
                return Table(schema=out_schema, rows=((s_val,),))

        elif isinstance(node, CountNode):
            if isinstance(node.source, GroupByNode):
                # 分组计数
                src_table = self._eval_node(node.source.source, database)
                key_indices = [src_table.schema.index_of(c) for c in node.source.group_cols]

                groups_count: Dict[Tuple[Any, ...], int] = defaultdict(int)
                ordered_keys: List[Tuple[Any, ...]] = []
                for row in src_table.rows:
                    key = tuple(row[i] for i in key_indices)
                    if key not in groups_count:
                        ordered_keys.append(key)
                    groups_count[key] += 1

                out_cols = [src_table.schema.get_column(c) for c in node.source.group_cols]  # type: ignore
                out_cols.append(Column(node.as_col, DataType.INT))
                out_schema = RelationSchema(tuple(out_cols))

                result_rows = [key + (groups_count[key],) for key in ordered_keys]
                return Table(schema=out_schema, rows=tuple(result_rows))
            else:
                # 全表行数计数
                src_table = self._eval_node(node.source, database)
                out_schema = RelationSchema((Column(node.as_col, DataType.INT),))
                return Table(schema=out_schema, rows=((len(src_table.rows),),))

        elif isinstance(node, SortNode):
            src_table = self._eval_node(node.source, database)
            col_idx = src_table.schema.index_of(node.sort_col)
            reverse = node.direction == SortDirection.DESC
            # 使用 Python 稳定的 Timsort 保证确定性
            sorted_rows = sorted(src_table.rows, key=lambda r: r[col_idx], reverse=reverse)
            return Table(schema=src_table.schema, rows=tuple(sorted_rows))

        elif isinstance(node, LimitNode):
            src_table = self._eval_node(node.source, database)
            return Table(schema=src_table.schema, rows=src_table.rows[:node.limit])

        else:
            raise ExecutionError(f"Unsupported AST node type: {type(node)}")

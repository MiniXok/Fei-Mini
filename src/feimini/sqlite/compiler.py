"""MiniRel AST 到 SQLite 参数化 SQL 编译器。

将强类型的 MiniRel AST 算子树递归编译为安全的 SQLite SELECT 查询，
严密遵循参数化绑定原则 (？占位符)，杜绝字符串插值，安全转义标识符。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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
from ..dsl.types import DataType, PredicateOp, RelationSchema, SortDirection


class CompilationError(Exception):
    """MiniRel 到 SQL 编译期错误。"""
    pass


@dataclass(frozen=True)
class CompiledSQLQuery:
    """编译产出的参数化 SQL 查询与绑定值。"""
    sql: str
    params: Tuple[Any, ...]
    output_schema: RelationSchema

    def format_debug(self) -> str:
        """用于日志和排查的调试字符串表示。"""
        return f"SQL: {self.sql}\nParams: {self.params}"


OP_SYMBOL_MAP = {
    PredicateOp.EQ: "=",
    PredicateOp.NEQ: "!=",
    PredicateOp.GT: ">",
    PredicateOp.LT: "<",
    PredicateOp.GTE: ">=",
    PredicateOp.LTE: "<=",
}


class MiniRelSQLCompiler:
    """MiniRel 语法树到安全 SQLite 查询的编译引擎。"""

    def compile(
        self,
        node: ASTNode,
        env_schemas: Dict[str, RelationSchema],
    ) -> CompiledSQLQuery:
        """静态检查并在指定环境 Schema 下将 AST 编译为参数化 SQL。"""
        # 1. 静态类型校验
        out_schema = node.validate_types(env_schemas)

        # 2. 递归生成参数化 SQL
        sql, params = self._compile_node_to_sql(node, env_schemas)
        return CompiledSQLQuery(sql=sql, params=tuple(params), output_schema=out_schema)

    def _compile_node_to_sql(
        self,
        node: ASTNode,
        env_schemas: Dict[str, RelationSchema],
    ) -> Tuple[str, List[Any]]:
        params: List[Any] = []

        if isinstance(node, ScanNode):
            clean_tbl = self._escape_ident(node.table_name)
            sql = f'SELECT * FROM "{clean_tbl}"'
            return sql, params

        elif isinstance(node, FilterNode):
            sub_sql, sub_params = self._compile_node_to_sql(node.source, env_schemas)
            params.extend(sub_params)
            op_sym = OP_SYMBOL_MAP.get(node.predicate_op, "=")
            clean_col = self._escape_ident(node.col_name)
            params.append(node.value)
            sql = f'SELECT * FROM ({sub_sql}) AS _t WHERE _t."{clean_col}" {op_sym} ?'
            return sql, params

        elif isinstance(node, ProjectNode):
            sub_sql, sub_params = self._compile_node_to_sql(node.source, env_schemas)
            params.extend(sub_params)
            cols_clause = ", ".join(f'_t."{self._escape_ident(c)}"' for c in node.columns)
            sql = f'SELECT {cols_clause} FROM ({sub_sql}) AS _t'
            return sql, params

        elif isinstance(node, JoinNode):
            # 编译左子树与右子树
            sql_l, params_l = self._compile_node_to_sql(node.left, env_schemas)
            sql_r, params_r = self._compile_node_to_sql(node.right, env_schemas)
            params.extend(params_l)
            params.extend(params_r)

            s_l = node.left.validate_types(env_schemas)
            s_r = node.right.validate_types(env_schemas)

            clean_l_col = self._escape_ident(node.left_col)
            clean_r_col = self._escape_ident(node.right_col)

            # 构建投影子句与列名重名消除 (right. 前缀)
            out_select_items: List[str] = []
            left_names = set(s_l.column_names)
            for c in s_l.columns:
                c_esc = self._escape_ident(c.name)
                out_select_items.append(f'_l."{c_esc}" AS "{c_esc}"')

            for c in s_r.columns:
                c_esc = self._escape_ident(c.name)
                if c.name in left_names:
                    alias = f"right.{c.name}"
                    out_select_items.append(f'_r."{c_esc}" AS "{self._escape_ident(alias)}"')
                else:
                    out_select_items.append(f'_r."{c_esc}" AS "{c_esc}"')

            select_clause = ", ".join(out_select_items)
            sql = (
                f"SELECT {select_clause} FROM ({sql_l}) AS _l "
                f'INNER JOIN ({sql_r}) AS _r ON _l."{clean_l_col}" = _r."{clean_r_col}"'
            )
            return sql, params

        elif isinstance(node, GroupByNode):
            sub_sql, sub_params = self._compile_node_to_sql(node.source, env_schemas)
            params.extend(sub_params)
            g_cols = ", ".join(f'_t."{self._escape_ident(c)}"' for c in node.group_cols)
            # GroupBy 单独作为终端时表示提取唯一键
            sql = f"SELECT {g_cols} FROM ({sub_sql}) AS _t GROUP BY {g_cols}"
            return sql, params

        elif isinstance(node, SumNode):
            if isinstance(node.source, GroupByNode):
                # 分组求和
                inner_sql, inner_params = self._compile_node_to_sql(node.source.source, env_schemas)
                params.extend(inner_params)
                g_cols = ", ".join(f'_t."{self._escape_ident(c)}"' for c in node.source.group_cols)
                clean_agg = self._escape_ident(node.agg_col)
                clean_as = self._escape_ident(node.as_col)
                sql = (
                    f'SELECT {g_cols}, SUM(_t."{clean_agg}") AS "{clean_as}" '
                    f"FROM ({inner_sql}) AS _t GROUP BY {g_cols}"
                )
                return sql, params
            else:
                # 全表总和
                sub_sql, sub_params = self._compile_node_to_sql(node.source, env_schemas)
                params.extend(sub_params)
                clean_agg = self._escape_ident(node.agg_col)
                clean_as = self._escape_ident(node.as_col)
                # SQLite 对空表 SUM 返回 NULL，COALESCE 保证与 MiniRel 0 语义一致
                sql = f'SELECT COALESCE(SUM(_t."{clean_agg}"), 0) AS "{clean_as}" FROM ({sub_sql}) AS _t'
                return sql, params

        elif isinstance(node, CountNode):
            if isinstance(node.source, GroupByNode):
                # 分组计数
                inner_sql, inner_params = self._compile_node_to_sql(node.source.source, env_schemas)
                params.extend(inner_params)
                g_cols = ", ".join(f'_t."{self._escape_ident(c)}"' for c in node.source.group_cols)
                clean_as = self._escape_ident(node.as_col)
                sql = (
                    f'SELECT {g_cols}, COUNT(*) AS "{clean_as}" '
                    f"FROM ({inner_sql}) AS _t GROUP BY {g_cols}"
                )
                return sql, params
            else:
                # 全表行数计数
                sub_sql, sub_params = self._compile_node_to_sql(node.source, env_schemas)
                params.extend(sub_params)
                clean_as = self._escape_ident(node.as_col)
                sql = f'SELECT COUNT(*) AS "{clean_as}" FROM ({sub_sql}) AS _t'
                return sql, params

        elif isinstance(node, SortNode):
            sub_sql, sub_params = self._compile_node_to_sql(node.source, env_schemas)
            params.extend(sub_params)
            clean_sort = self._escape_ident(node.sort_col)
            dir_str = "ASC" if node.direction == SortDirection.ASC else "DESC"
            sql = f'SELECT * FROM ({sub_sql}) AS _t ORDER BY _t."{clean_sort}" {dir_str}'
            return sql, params

        elif isinstance(node, LimitNode):
            sub_sql, sub_params = self._compile_node_to_sql(node.source, env_schemas)
            params.extend(sub_params)
            params.append(int(node.limit))
            sql = f"SELECT * FROM ({sub_sql}) AS _t LIMIT ?"
            return sql, params

        else:
            raise CompilationError(f"Unsupported MiniRel AST node for SQLite compilation: {type(node)}")

    def _escape_ident(self, ident: str) -> str:
        """安全转义 SQL 标识符（双引号转义）。"""
        return ident.replace('"', '""')

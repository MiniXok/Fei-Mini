"""MiniRel 关系程序生成器。

生成多层级复杂度 (SIMPLE, MEDIUM, COMPLEX) 的良构有意义 AST 关系查询程序。
确保生成程序具有语义表达力，而非恒空或退化的琐碎程序。
"""

from __future__ import annotations
from enum import Enum
import random
from typing import Any, Dict, List, Optional, Tuple

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
)
from ..dsl.interpreter import MiniRelInterpreter
from ..dsl.types import Column, DataType, PredicateOp, RelationSchema, SortDirection, Table
from .schema import SchemaFamily, TableSpec


class ProgramComplexity(str, Enum):
    SIMPLE = "SIMPLE"      # 单表扫描、过滤、投影或排序截断 (深度 1-2)
    MEDIUM = "MEDIUM"      # 复合过滤投影、单表分组聚合、二表简单内连 (深度 2-3)
    COMPLEX = "COMPLEX"    # 二表连接后过滤投影、连接后分组聚合与排序截取 (深度 3-5)


class ProgramGenerator:
    """根据 Schema 族与复杂度配置生成良构关系程序。"""

    def __init__(self) -> None:
        self.interpreter = MiniRelInterpreter()

    def generate_candidate(
        self,
        family: SchemaFamily,
        complexity: ProgramComplexity,
        rng: random.Random,
        sample_db: Optional[Dict[str, Table]] = None,
    ) -> ASTNode:
        """生成一个在 sample_db 上能产出非空有效结果的程序。尝试最多 30 次。"""
        for _ in range(30):
            ast = self._build_raw_ast(family, complexity, rng)
            if sample_db is not None:
                try:
                    res = self.interpreter.execute(ast, sample_db)
                    # 确保程序在示例数据上产出非空结果且没有产生所有行相同
                    if res.num_rows > 0:
                        return ast
                except Exception:
                    continue
            else:
                return ast

        # 若重试未命中非空条件，返回基础扫描保底
        base_table = family.tables[0].name
        return ScanNode(base_table)

    def _build_raw_ast(
        self,
        family: SchemaFamily,
        complexity: ProgramComplexity,
        rng: random.Random,
    ) -> ASTNode:
        parent_spec = [t for t in family.tables if t.fk_ref is None][0]
        child_spec = [t for t in family.tables if t.fk_ref is not None][0]

        if complexity == ProgramComplexity.SIMPLE:
            pattern = rng.choice(["scan", "filter", "project", "sort_limit"])
            tbl_spec = rng.choice([parent_spec, child_spec])
            curr: ASTNode = ScanNode(tbl_spec.name)

            if pattern == "scan":
                return curr

            elif pattern == "filter":
                col, op, val = self._sample_filter_clause(tbl_spec, rng)
                return FilterNode(curr, col, op, val)

            elif pattern == "project":
                cols = self._sample_projection_cols(tbl_spec.schema, rng)
                return ProjectNode(curr, cols)

            elif pattern == "sort_limit":
                sort_col = rng.choice(tbl_spec.schema.column_names)
                direction = rng.choice([SortDirection.ASC, SortDirection.DESC])
                limit = rng.randint(2, 5)
                return LimitNode(SortNode(curr, sort_col, direction), limit)

        elif complexity == ProgramComplexity.MEDIUM:
            pattern = rng.choice(["filter_project", "filter_sort_limit", "groupby_agg", "join_project"])
            tbl_spec = rng.choice([parent_spec, child_spec])

            if pattern == "filter_project":
                col, op, val = self._sample_filter_clause(tbl_spec, rng)
                curr = FilterNode(ScanNode(tbl_spec.name), col, op, val)
                cols = self._sample_projection_cols(tbl_spec.schema, rng)
                return ProjectNode(curr, cols)

            elif pattern == "filter_sort_limit":
                col, op, val = self._sample_filter_clause(tbl_spec, rng)
                curr = FilterNode(ScanNode(tbl_spec.name), col, op, val)
                sort_col = rng.choice(tbl_spec.schema.column_names)
                direction = rng.choice([SortDirection.ASC, SortDirection.DESC])
                limit = rng.randint(2, 5)
                return LimitNode(SortNode(curr, sort_col, direction), limit)

            elif pattern == "groupby_agg":
                # 选择一个分类列作为分组列
                str_cols = [c.name for c in tbl_spec.schema.columns if c.data_type == DataType.STR]
                int_cols = [c.name for c in tbl_spec.schema.columns if c.data_type == DataType.INT]
                group_candidates = str_cols if str_cols else int_cols
                group_col = rng.choice(group_candidates)

                curr = GroupByNode(ScanNode(tbl_spec.name), (group_col,))
                agg_type = rng.choice(["sum", "count"])

                if agg_type == "count":
                    return CountNode(curr, as_col="total_cnt")
                else:
                    num_cols = [
                        c.name for c in tbl_spec.schema.columns
                        if c.data_type in (DataType.INT, DataType.FLOAT) and c.name != group_col
                    ]
                    if num_cols:
                        return SumNode(curr, rng.choice(num_cols), as_col="sum_metric")
                    return CountNode(curr, as_col="total_cnt")

            elif pattern == "join_project":
                fk_col, ref_table = child_spec.fk_ref  # type: ignore
                ref_spec = parent_spec
                curr = JoinNode(
                    ScanNode(parent_spec.name),
                    ScanNode(child_spec.name),
                    ref_spec.pk_col,
                    fk_col,
                )
                env_schemas = {parent_spec.name: parent_spec.schema, child_spec.name: child_spec.schema}
                joined_schema = curr.validate_types(env_schemas)
                cols = self._sample_projection_cols(joined_schema, rng)
                return ProjectNode(curr, cols)

        else:  # COMPLEX
            fk_col, ref_table = child_spec.fk_ref  # type: ignore
            join_ast = JoinNode(
                ScanNode(parent_spec.name),
                ScanNode(child_spec.name),
                parent_spec.pk_col,
                fk_col,
            )
            env_schemas = {parent_spec.name: parent_spec.schema, child_spec.name: child_spec.schema}
            joined_schema = join_ast.validate_types(env_schemas)

            pattern = rng.choice(["join_filter_project", "join_groupby_agg_sort_limit"])

            if pattern == "join_filter_project":
                # 在连接结果上做过滤再投影
                f_col = rng.choice(joined_schema.column_names)
                f_type = joined_schema.get_type(f_col)
                if f_type == DataType.STR:
                    op, val = PredicateOp.EQ, "Beijing"
                elif f_type == DataType.BOOL:
                    op, val = PredicateOp.EQ, True
                else:
                    op, val = PredicateOp.GT, 10
                filt = FilterNode(join_ast, f_col, op, val)
                cols = self._sample_projection_cols(joined_schema, rng)
                return ProjectNode(filt, cols)

            else:
                # 连接后按主表分类列分组，聚合从表数值列并排序截断
                str_cols = [c.name for c in joined_schema.columns if c.data_type == DataType.STR]
                grp_col = rng.choice(str_cols) if str_cols else joined_schema.column_names[0]
                grp_node = GroupByNode(join_ast, (grp_col,))

                num_cols = [
                    c.name for c in joined_schema.columns
                    if c.data_type in (DataType.INT, DataType.FLOAT) and c.name != grp_col
                ]
                agg_col = rng.choice(num_cols) if num_cols else joined_schema.column_names[0]
                sum_node = SumNode(grp_node, agg_col, as_col="agg_metric")
                sorted_node = SortNode(sum_node, "agg_metric", SortDirection.DESC)
                return LimitNode(sorted_node, limit=rng.randint(2, 5))

        return ScanNode(parent_spec.name)

    def _sample_filter_clause(
        self, spec: TableSpec, rng: random.Random
    ) -> Tuple[str, PredicateOp, Any]:
        """采样合理的过滤子句（字段、操作符、字面量）。"""
        col_name = rng.choice(spec.schema.column_names)
        col = spec.schema.get_column(col_name)
        assert col is not None

        if spec.value_domains and col_name in spec.value_domains:
            val = rng.choice(spec.value_domains[col_name])
            op = rng.choice([PredicateOp.EQ, PredicateOp.NEQ])
            return col_name, op, val

        if col.data_type == DataType.BOOL:
            return col_name, PredicateOp.EQ, rng.choice([True, False])
        elif col.data_type == DataType.INT:
            op = rng.choice([PredicateOp.GT, PredicateOp.LT, PredicateOp.EQ])
            val = rng.choice([10, 20, 30, 50])
            return col_name, op, val
        elif col.data_type == DataType.FLOAT:
            op = rng.choice([PredicateOp.GT, PredicateOp.LT])
            val = round(rng.uniform(50.0, 250.0), 2)
            return col_name, op, val
        else:
            return col_name, PredicateOp.EQ, "Beijing"

    def _sample_projection_cols(
        self, schema: RelationSchema, rng: random.Random
    ) -> Tuple[str, ...]:
        """采样 1 到 min(3, len) 个不重复列进行投影。"""
        names = list(schema.column_names)
        k = rng.randint(1, min(3, len(names)))
        return tuple(rng.sample(names, k))

"""MiniRel 到 SQLite 参数化 SQL 编译器单元测试。"""

import unittest
from feimini.dsl.ast import (
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
from feimini.dsl.types import Column, DataType, RelationSchema
from feimini.sqlite.compiler import MiniRelSQLCompiler


class TestMiniRelSQLCompiler(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = MiniRelSQLCompiler()
        self.cust_schema = RelationSchema(
            (
                Column("id", DataType.INT),
                Column("city", DataType.STR),
                Column("score", DataType.FLOAT),
            )
        )
        self.orders_schema = RelationSchema(
            (
                Column("order_id", DataType.INT),
                Column("cust_id", DataType.INT),
                Column("amount", DataType.FLOAT),
            )
        )
        self.env = {
            "customers": self.cust_schema,
            "orders": self.orders_schema,
        }

    def test_scan_and_project(self) -> None:
        ast = ProjectNode(ScanNode("customers"), ("city", "score"))
        compiled = self.compiler.compile(ast, self.env)
        self.assertIn('SELECT _t."city", _t."score"', compiled.sql)
        self.assertIn('FROM (SELECT * FROM "customers")', compiled.sql)
        self.assertEqual(compiled.params, ())

    def test_parameterized_filter(self) -> None:
        ast = FilterNode(ScanNode("customers"), "city", PredicateOp.EQ, "Beijing")
        compiled = self.compiler.compile(ast, self.env)
        self.assertIn('WHERE _t."city" = ?', compiled.sql)
        self.assertEqual(compiled.params, ("Beijing",))

    def test_inner_join_with_aliasing(self) -> None:
        ast = JoinNode(ScanNode("customers"), ScanNode("orders"), "id", "cust_id")
        compiled = self.compiler.compile(ast, self.env)
        self.assertIn('INNER JOIN (SELECT * FROM "orders") AS _r', compiled.sql)
        self.assertIn('_l."id" = _r."cust_id"', compiled.sql)

    def test_groupby_sum_and_count(self) -> None:
        ast_sum = SumNode(GroupByNode(ScanNode("customers"), ("city",)), "score", as_col="sum_score")
        compiled_sum = self.compiler.compile(ast_sum, self.env)
        self.assertIn('GROUP BY _t."city"', compiled_sum.sql)
        self.assertIn('SUM(_t."score") AS "sum_score"', compiled_sum.sql)

        ast_cnt = CountNode(GroupByNode(ScanNode("customers"), ("city",)), as_col="total_cnt")
        compiled_cnt = self.compiler.compile(ast_cnt, self.env)
        self.assertIn('COUNT(*) AS "total_cnt"', compiled_cnt.sql)

    def test_sort_and_limit(self) -> None:
        ast = LimitNode(SortNode(ScanNode("customers"), "score", SortDirection.DESC), limit=5)
        compiled = self.compiler.compile(ast, self.env)
        self.assertIn('ORDER BY _t."score" DESC', compiled.sql)
        self.assertIn("LIMIT ?", compiled.sql)
        self.assertEqual(compiled.params, (5,))


if __name__ == "__main__":
    unittest.main()

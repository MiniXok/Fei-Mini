"""MiniRel AST 语法树静态分析与序列化单元测试。"""

import unittest
from feimini.dsl.types import Column, DataType, PredicateOp, RelationSchema, SortDirection
from feimini.dsl.ast import (
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


class TestMiniRelAST(unittest.TestCase):
    def setUp(self) -> None:
        self.users_schema = RelationSchema(
            (
                Column("id", DataType.INT),
                Column("country", DataType.STR),
                Column("age", DataType.INT),
            )
        )
        self.orders_schema = RelationSchema(
            (
                Column("order_id", DataType.INT),
                Column("user_id", DataType.INT),
                Column("amount", DataType.FLOAT),
            )
        )
        self.env = {
            "users": self.users_schema,
            "orders": self.orders_schema,
        }

    def test_scan_node(self) -> None:
        scan = ScanNode("users")
        schema = scan.validate_types(self.env)
        self.assertEqual(schema, self.users_schema)
        self.assertEqual(scan.depth, 1)
        self.assertEqual(scan.node_count, 1)

        with self.assertRaises(TypeErrorAST):
            ScanNode("nonexistent").validate_types(self.env)

    def test_filter_node(self) -> None:
        scan = ScanNode("users")
        filt = FilterNode(scan, "age", PredicateOp.GT, 18)
        schema = filt.validate_types(self.env)
        self.assertEqual(schema, self.users_schema)

        # 错误列名
        with self.assertRaises(TypeErrorAST):
            FilterNode(scan, "unknown", PredicateOp.EQ, 1).validate_types(self.env)

        # 类型不兼容
        with self.assertRaises(TypeErrorAST):
            FilterNode(scan, "age", PredicateOp.EQ, "not_an_int").validate_types(self.env)

    def test_project_node(self) -> None:
        scan = ScanNode("users")
        proj = ProjectNode(scan, ("country", "age"))
        schema = proj.validate_types(self.env)
        self.assertEqual(schema.column_names, ("country", "age"))

        # 投影不存在列
        with self.assertRaises(TypeErrorAST):
            ProjectNode(scan, ("id", "invalid")).validate_types(self.env)

    def test_join_node(self) -> None:
        scan_u = ScanNode("users")
        scan_o = ScanNode("orders")
        join = JoinNode(scan_u, scan_o, "id", "user_id")
        schema = join.validate_types(self.env)
        self.assertIn("country", schema.column_names)
        self.assertIn("amount", schema.column_names)

        # 键类型不匹配
        with self.assertRaises(TypeErrorAST):
            JoinNode(scan_u, scan_o, "country", "amount").validate_types(self.env)

    def test_groupby_and_sum(self) -> None:
        scan_o = ScanNode("orders")
        grp = GroupByNode(scan_o, ("user_id",))
        sum_node = SumNode(grp, "amount", as_col="total_spent")
        schema = sum_node.validate_types(self.env)
        self.assertEqual(schema.column_names, ("user_id", "total_spent"))
        self.assertEqual(schema.get_type("total_spent"), DataType.FLOAT)

        # 非数值列不可求和
        scan_u = ScanNode("users")
        with self.assertRaises(TypeErrorAST):
            SumNode(scan_u, "country").validate_types(self.env)

    def test_sort_and_limit(self) -> None:
        prog = LimitNode(
            SortNode(ScanNode("users"), "age", SortDirection.DESC),
            limit=5,
        )
        schema = prog.validate_types(self.env)
        self.assertEqual(schema, self.users_schema)
        self.assertEqual(prog.depth, 3)
        self.assertEqual(prog.node_count, 3)

    def test_ast_serialization_roundtrip(self) -> None:
        prog = LimitNode(
            SortNode(
                SumNode(
                    GroupByNode(
                        FilterNode(ScanNode("orders"), "amount", PredicateOp.GT, 10.0),
                        ("user_id",),
                    ),
                    "amount",
                    as_col="sum_amount",
                ),
                "sum_amount",
                SortDirection.DESC,
            ),
            5,
        )
        d = prog.to_dict()
        restored = ASTNode.from_dict(d)
        self.assertEqual(restored.to_dict(), d)
        self.assertEqual(restored.validate_types(self.env), prog.validate_types(self.env))


if __name__ == "__main__":
    unittest.main()

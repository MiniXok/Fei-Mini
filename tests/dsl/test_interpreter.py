"""MiniRel 解释器执行语义与边界测试。"""

import unittest
from feimini.dsl.types import (
    Column,
    DataType,
    PredicateOp,
    RelationSchema,
    SortDirection,
    Table,
    tables_equal,
)
from feimini.dsl.ast import (
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
from feimini.dsl.interpreter import ExecutionError, MiniRelInterpreter


class TestMiniRelInterpreter(unittest.TestCase):
    def setUp(self) -> None:
        self.interp = MiniRelInterpreter(max_rows=1000)
        users_schema = RelationSchema(
            (
                Column("id", DataType.INT),
                Column("city", DataType.STR),
                Column("age", DataType.INT),
            )
        )
        users_table = Table(
            users_schema,
            (
                (1, "Beijing", 25),
                (2, "Shanghai", 30),
                (3, "Beijing", 18),
                (4, "Shenzhen", 45),
            ),
        )

        orders_schema = RelationSchema(
            (
                Column("order_id", DataType.INT),
                Column("user_id", DataType.INT),
                Column("amount", DataType.FLOAT),
            )
        )
        orders_table = Table(
            orders_schema,
            (
                (101, 1, 150.0),
                (102, 1, 50.0),
                (103, 2, 200.0),
                (104, 999, 10.0),  # user_id 999 不存在于 users
            ),
        )

        self.db = {"users": users_table, "orders": orders_table}

    def test_scan_and_filter(self) -> None:
        prog = FilterNode(ScanNode("users"), "city", PredicateOp.EQ, "Beijing")
        result = self.interp.execute(prog, self.db)
        self.assertEqual(result.num_rows, 2)
        self.assertEqual(result.rows[0], (1, "Beijing", 25))
        self.assertEqual(result.rows[1], (3, "Beijing", 18))

    def test_project(self) -> None:
        prog = ProjectNode(ScanNode("users"), ("age", "city"))
        result = self.interp.execute(prog, self.db)
        self.assertEqual(result.schema.column_names, ("age", "city"))
        self.assertEqual(result.rows[0], (25, "Beijing"))

    def test_join(self) -> None:
        prog = JoinNode(ScanNode("users"), ScanNode("orders"), "id", "user_id")
        result = self.interp.execute(prog, self.db)
        self.assertEqual(result.num_rows, 3)
        # 验证连接生成的属性组合
        self.assertIn("city", result.schema.column_names)
        self.assertIn("amount", result.schema.column_names)

    def test_groupby_sum(self) -> None:
        # 按 city 分组统计 age 总和
        prog = SumNode(
            GroupByNode(ScanNode("users"), ("city",)),
            agg_col="age",
            as_col="sum_age",
        )
        result = self.interp.execute(prog, self.db)
        # Beijing: 25 + 18 = 43; Shanghai: 30; Shenzhen: 45
        self.assertEqual(result.num_rows, 3)
        self.assertEqual(result.schema.column_names, ("city", "sum_age"))
        city_sums = dict(result.rows)
        self.assertEqual(city_sums["Beijing"], 43)
        self.assertEqual(city_sums["Shanghai"], 30)
        self.assertEqual(city_sums["Shenzhen"], 45)

    def test_global_count_and_sum(self) -> None:
        prog_count = CountNode(ScanNode("users"), as_col="total_users")
        res_count = self.interp.execute(prog_count, self.db)
        self.assertEqual(res_count.rows, ((4,),))

        prog_sum = SumNode(ScanNode("users"), "age", as_col="total_age")
        res_sum = self.interp.execute(prog_sum, self.db)
        self.assertEqual(res_sum.rows, ((25 + 30 + 18 + 45,),))

    def test_sort_and_limit(self) -> None:
        prog = LimitNode(
            SortNode(ScanNode("users"), "age", SortDirection.DESC),
            limit=2,
        )
        result = self.interp.execute(prog, self.db)
        self.assertEqual(result.num_rows, 2)
        self.assertEqual(result.rows[0][2], 45)  # 最大 age
        self.assertEqual(result.rows[1][2], 30)  # 次大 age

    def test_empty_table_semantics(self) -> None:
        # 空表过滤后计数
        prog = CountNode(
            FilterNode(ScanNode("users"), "age", PredicateOp.GT, 100),
            as_col="count_val",
        )
        result = self.interp.execute(prog, self.db)
        self.assertEqual(result.rows, ((0,),))


if __name__ == "__main__":
    unittest.main()

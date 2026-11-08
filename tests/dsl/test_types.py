"""MiniRel 类型系统单元测试。"""

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


class TestMiniRelTypes(unittest.TestCase):
    def test_datatype_coercion(self) -> None:
        self.assertEqual(DataType.INT.coerce("123"), 123)
        self.assertEqual(DataType.FLOAT.coerce("3.14"), 3.14)
        self.assertEqual(DataType.STR.coerce(42), "42")
        self.assertEqual(DataType.BOOL.coerce(1), True)
        self.assertIsNone(DataType.INT.coerce(None))

    def test_predicate_evaluation(self) -> None:
        self.assertTrue(PredicateOp.EQ.evaluate(10, 10))
        self.assertFalse(PredicateOp.EQ.evaluate(10, 20))
        self.assertTrue(PredicateOp.NEQ.evaluate("a", "b"))
        self.assertTrue(PredicateOp.LT.evaluate(5, 10))
        self.assertTrue(PredicateOp.LTE.evaluate(10, 10))
        self.assertTrue(PredicateOp.GT.evaluate(15, 10))
        self.assertTrue(PredicateOp.GTE.evaluate(15, 15))
        self.assertFalse(PredicateOp.EQ.evaluate(None, 10))

    def test_schema_creation_and_lookups(self) -> None:
        cols = (
            Column("id", DataType.INT),
            Column("name", DataType.STR),
            Column("score", DataType.FLOAT),
        )
        schema = RelationSchema(cols)
        self.assertEqual(schema.column_names, ("id", "name", "score"))
        self.assertTrue(schema.has_column("name"))
        self.assertFalse(schema.has_column("missing"))
        self.assertEqual(schema.get_type("score"), DataType.FLOAT)
        self.assertEqual(schema.index_of("name"), 1)

        # 检查重复列名抛出异常
        with self.assertRaises(ValueError):
            RelationSchema((Column("id", DataType.INT), Column("id", DataType.STR)))

    def test_schema_with_prefix(self) -> None:
        schema = RelationSchema((Column("id", DataType.INT), Column("val", DataType.STR)))
        prefixed = schema.with_prefix("t1")
        self.assertEqual(prefixed.column_names, ("t1.id", "t1.val"))

    def test_table_validation_and_equality(self) -> None:
        schema = RelationSchema((Column("id", DataType.INT), Column("name", DataType.STR)))
        t1 = Table(schema, ((1, "Alice"), (2, "Bob")))
        t2 = Table(schema, ((1, "Alice"), (2, "Bob")))
        t3 = Table(schema, ((2, "Bob"), (1, "Alice")))

        self.assertTrue(tables_equal(t1, t2, check_row_order=True))
        self.assertFalse(tables_equal(t1, t3, check_row_order=True))
        self.assertTrue(tables_equal(t1, t3, check_row_order=False))

        # 检查行维度不匹配报错
        with self.assertRaises(ValueError):
            Table(schema, ((1,),))

    def test_serialization(self) -> None:
        schema = RelationSchema((Column("x", DataType.INT), Column("y", DataType.FLOAT)))
        table = Table(schema, ((10, 2.5), (20, 5.0)))
        data = table.to_dict()
        restored = Table.from_dict(data)
        self.assertTrue(tables_equal(table, restored))


if __name__ == "__main__":
    unittest.main()

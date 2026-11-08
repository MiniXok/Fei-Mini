"""自然语言意图契约与解析器单元测试。"""

import os
import sqlite3
import tempfile
import unittest

from feimini.dsl.ast import FilterNode, JoinNode, LimitNode, PredicateOp, ProjectNode, ScanNode, SortDirection, SortNode, SumNode
from feimini.sqlite.schema import SQLiteSchemaAdapter
from feimini.translator.contract import (
    AggregationIntent,
    FilterIntent,
    IntentSpec,
    SortIntent,
    validate_intent_against_schema,
)
from feimini.translator.resolver import IntentResolutionError, IntentResolver


class TestTranslatorContract(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "contract_test.db")

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT, city TEXT);")
        c.execute("CREATE TABLE purchases (pid INT PRIMARY KEY, user_id INT, amount REAL, FOREIGN KEY (user_id) REFERENCES users (id));")
        conn.commit()
        conn.close()

        self.schema = SQLiteSchemaAdapter.inspect_database(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_intent_serialization_roundtrip(self) -> None:
        """测试 IntentSpec 序列化与反序列化等价性。"""
        intent = IntentSpec(
            target_table="users",
            target_columns=("name", "city"),
            filters=(FilterIntent(column="city", op=PredicateOp.EQ, value="Tokyo"),),
            sort=SortIntent(column="name", direction=SortDirection.ASC),
            limit=10,
            clarification_needed=False,
        )
        d = intent.to_dict()
        restored = IntentSpec.from_dict(d)
        self.assertEqual(restored.target_table, "users")
        self.assertEqual(restored.target_columns, ("name", "city"))
        self.assertEqual(len(restored.filters), 1)
        self.assertEqual(restored.filters[0].value, "Tokyo")
        self.assertEqual(restored.limit, 10)

    def test_validate_intent_against_schema(self) -> None:
        """测试模式校验器阻断不存在的表名与列名。"""
        # 合法意图
        valid_intent = IntentSpec(
            target_table="users",
            target_columns=("name",),
            filters=(FilterIntent(column="city", op=PredicateOp.EQ, value="Tokyo"),),
        )
        ok, err = validate_intent_against_schema(valid_intent, self.schema)
        self.assertTrue(ok)
        self.assertIsNone(err)

        # 非法列名
        invalid_intent = IntentSpec(
            target_table="users",
            target_columns=("password_hash",),
        )
        ok, err = validate_intent_against_schema(invalid_intent, self.schema)
        self.assertFalse(ok)
        self.assertIn("not found in database schema", err)

    def test_intent_resolver_multi_table_join_plan(self) -> None:
        """测试意图解析器自动根据外键构建 Join 节点与聚合。"""
        intent = IntentSpec(
            target_table="users",
            target_columns=("name", "total_spent"),
            aggregations=(AggregationIntent(op="SUM", column="amount", as_col="total_spent"),),
            sort=SortIntent(column="total_spent", direction=SortDirection.DESC),
            limit=5,
        )
        plan = IntentResolver.resolve_to_ast(intent, self.schema)
        self.assertIsInstance(plan, LimitNode)
        self.assertIsInstance(plan.source, SortNode)
        self.assertIsInstance(plan.source.source, SumNode)
        # 验证底层自动连接了 users 与 purchases
        def has_node_type(n, target_type):
            if isinstance(n, target_type):
                return True
            for c in n.children:
                if has_node_type(c, target_type):
                    return True
            return False

        self.assertTrue(has_node_type(plan, JoinNode))


if __name__ == "__main__":
    unittest.main()

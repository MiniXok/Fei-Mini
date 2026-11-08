"""语义安全护栏 (SemanticIntentGuard) 单元测试。"""

import os
import sqlite3
import tempfile
import unittest

from feimini.sqlite.schema import SQLiteSchemaAdapter
from feimini.translator.contract import IntentDecision, IntentSpec
from feimini.translator.semantic_guard import SemanticIntentGuard


class TestSemanticGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "guard_test.db")

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE customers (id INT PRIMARY KEY, name TEXT, city TEXT, balance REAL);")
        c.execute("CREATE TABLE orders (order_id INT PRIMARY KEY, cust_id INT, amount REAL);")
        conn.commit()
        conn.close()

        self.schema = SQLiteSchemaAdapter.inspect_database(self.db_path)
        self.raw_intent = IntentSpec(
            decision=IntentDecision.EXECUTE,
            target_table="customers",
            target_columns=("name",),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_guard_intercepts_prohibited_mutations(self) -> None:
        """测试护栏对写操作与 DDL 意图的绝对拦截 (ABSTAIN)。"""
        mutations = [
            "Delete from customers where id = 1",
            "Drop table orders",
            "Update customers set balance = 0",
            "Insert into customers values (10, 'Eve', 'Tokyo', 0)",
            "Truncate table customers",
            "Alter table orders add column discount REAL",
        ]
        for q in mutations:
            guarded = SemanticIntentGuard.audit_and_guard(q, self.raw_intent, self.schema)
            self.assertEqual(guarded.decision, IntentDecision.ABSTAIN, f"Failed to block mutation: {q}")
            self.assertIn("prohibited", guarded.abstain_reason.lower())

    def test_guard_intercepts_out_of_scope_questions(self) -> None:
        """测试对非数据库常识与代码生成提问的拒答 (ABSTAIN)。"""
        out_of_scope = [
            "How do I make a chocolate cake at home?",
            "What is the weather in Beijing today?",
            "Write a Python script to sort a list using quicksort",
            "Who was the first emperor of China?",
        ]
        for q in out_of_scope:
            guarded = SemanticIntentGuard.audit_and_guard(q, self.raw_intent, self.schema)
            self.assertEqual(guarded.decision, IntentDecision.ABSTAIN, f"Failed to abstain out-of-scope: {q}")
            self.assertIn("outside the scope", guarded.abstain_reason.lower())

    def test_guard_intercepts_unmodelled_concepts(self) -> None:
        """测试对不存在于当前 Schema 的业务概念的拒答 (ABSTAIN)。"""
        unmodelled = [
            "Find products with high inventory",
            "Show customer phone numbers",
            "What is the password of customer 1?",
            "Show customers in the north zone",
        ]
        for q in unmodelled:
            guarded = SemanticIntentGuard.audit_and_guard(q, self.raw_intent, self.schema)
            self.assertEqual(guarded.decision, IntentDecision.ABSTAIN, f"Failed to reject missing concept: {q}")
            self.assertIn("does not exist", guarded.abstain_reason.lower())

    def test_guard_triggers_clarification_on_missing_temporals(self) -> None:
        """测试对无时间戳表的时态模糊请求触发澄清 (CLARIFY)。"""
        temporals = [
            "Give me recent data",
            "Show transactions from last week",
            "Find orders placed yesterday",
        ]
        for q in temporals:
            guarded = SemanticIntentGuard.audit_and_guard(q, self.raw_intent, self.schema)
            self.assertEqual(guarded.decision, IntentDecision.CLARIFY, f"Failed to clarify temporal: {q}")
            self.assertIn("date or timestamp", guarded.clarification_prompt.lower())

    def test_guard_triggers_clarification_on_subjective_ranking(self) -> None:
        """测试对主观排名词未给依据的请求触发澄清 (CLARIFY)。"""
        subjectives = [
            "Show me the best customers",
            "Who is our top performing client?",
            "Find the most valuable customers",
        ]
        for q in subjectives:
            guarded = SemanticIntentGuard.audit_and_guard(q, self.raw_intent, self.schema)
            self.assertEqual(guarded.decision, IntentDecision.CLARIFY, f"Failed to clarify subjective: {q}")

    def test_guard_passes_clean_queries_untouched(self) -> None:
        """测试清晰且受支持的查询 100% 放行 (EXECUTE)，杜绝误拦截。"""
        clears = [
            "Find the names of all customers living in Beijing",
            "List all orders where amount is greater than 500",
            "Show the top 3 customers with highest balance",
            "Find customers with balance greater than 1000",
        ]
        for q in clears:
            guarded = SemanticIntentGuard.audit_and_guard(q, self.raw_intent, self.schema)
            self.assertEqual(guarded.decision, IntentDecision.EXECUTE, f"False clarification on clear query: {q}")


if __name__ == "__main__":
    unittest.main()

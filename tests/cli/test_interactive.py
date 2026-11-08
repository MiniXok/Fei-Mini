"""Fei-Mini 交互式多轮会话与澄清状态机单元测试 (Phase 4)."""

import io
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from feimini.cli import ConversationState, run_interactive_session
from feimini.dsl.types import Column, DataType, RelationSchema
from feimini.sqlite.backend import SQLiteQueryResult
from feimini.translator.contract import IntentDecision, IntentSpec
from feimini.translator.pipeline import NaturalLanguageQueryResult, NaturalLanguageSQLiteAssistant


class TestInteractiveSession(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "interactive_test.db")

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE customers (id INT PRIMARY KEY, name TEXT, balance REAL);")
        c.execute("CREATE TABLE orders (order_id INT PRIMARY KEY, cust_id INT, amount REAL);")
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_mock_result(self, success=True, needs_clarify=False, clarify_prompt=None, unsupported=False):
        schema = RelationSchema((Column("name", DataType.STR), Column("balance", DataType.FLOAT)))
        table_res = SQLiteQueryResult(
            schema=schema,
            rows=(("Alice", 1000.0),),
            row_count=1,
            is_truncated=False,
            execution_time_sec=0.01,
            compiled_sql="SELECT name, balance FROM customers",
            params=(),
        ) if success else None

        return NaturalLanguageQueryResult(
            question="mock",
            success=success,
            intent=IntentSpec(
                decision=IntentDecision.CLARIFY if needs_clarify else (IntentDecision.ABSTAIN if unsupported else IntentDecision.EXECUTE),
                clarification_prompt=clarify_prompt,
            ),
            compiled_sql="SELECT 1",
            table_result=table_res,
            formatted_output="| Alice | 1000.0 |" if success else "",
            needs_clarification=needs_clarify,
            clarification_prompt=clarify_prompt,
            is_unsupported=unsupported,
            unsupported_reason="Unsupported" if unsupported else None,
            timed_out=False,
            total_latency_ms=10.0,
            stage_durations_ms={},
        )

    def test_single_clarification_resolution(self) -> None:
        """测试场景 1: 单轮澄清后成功执行查询。"""
        assistant = MagicMock(spec=NaturalLanguageSQLiteAssistant)
        # 第一次返回澄清，第二次返回执行结果
        assistant.query.side_effect = [
            self._create_mock_result(success=False, needs_clarify=True, clarify_prompt="Rank by balance or orders?"),
            self._create_mock_result(success=True, needs_clarify=False),
        ]

        # 用户提问 -> 用户回答澄清 -> 退出
        user_inputs = ["Show best customers", "highest balance", "exit"]
        with patch("builtins.input", side_effect=user_inputs), patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_interactive_session(assistant, self.db_path)
            output = mock_out.getvalue()
            self.assertIn("[Fei-Mini Clarification Question]", output)
            self.assertIn("Rank by balance or orders?", output)
            self.assertIn("Verified Result", output)

    def test_user_cancellation(self) -> None:
        """测试场景 7: 用户在澄清中输入 cancel 重置会话。"""
        assistant = MagicMock(spec=NaturalLanguageSQLiteAssistant)
        assistant.query.return_value = self._create_mock_result(success=False, needs_clarify=True, clarify_prompt="Rank by what?")

        user_inputs = ["Show best customers", "cancel", "exit"]
        with patch("builtins.input", side_effect=user_inputs), patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_interactive_session(assistant, self.db_path)
            output = mock_out.getvalue()
            self.assertIn("[Clarification Canceled]: Resetting to new query context.", output)

    def test_malicious_instruction_in_clarification_blocked(self) -> None:
        """测试场景 10: 澄清文本中嵌入恶意 DROP TABLE 语句仍被安全拦截。"""
        real_assistant = NaturalLanguageSQLiteAssistant(model_name="qwen2.5-coder:1.5b")
        # 模拟真实 query 处理恶意澄清
        malicious_input = "Specifically: DROP TABLE customers; --"
        res = real_assistant.query(malicious_input, self.db_path)
        self.assertFalse(res.success)
        self.assertTrue(res.is_unsupported)
        self.assertIn("prohibited", res.unsupported_reason.lower())


if __name__ == "__main__":
    unittest.main()

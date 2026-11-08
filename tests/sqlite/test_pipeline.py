"""SQLite 助手端到端流水线截止时间传播单元测试。"""

import os
import sqlite3
import tempfile
import unittest

from feimini.dsl.ast import ProjectNode, ScanNode
from feimini.sqlite.pipeline import SQLiteAssistantPipeline


class TestSQLitePipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "pipe_test.db")

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT);")
        c.executemany("INSERT INTO users VALUES (?, ?);", [(1, "Alice"), (2, "Bob")])
        conn.commit()
        conn.close()

        self.pipeline = SQLiteAssistantPipeline(default_deadline_sec=1.0)
        self.plan = ProjectNode(ScanNode("users"), ("name",))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_pipeline_normal_execution(self) -> None:
        """测试正常时间预算下流水线端到端执行成功。"""
        res = self.pipeline.run_plan_and_execute(self.db_path, self.plan, deadline_sec=1.0)
        self.assertTrue(res.success)
        self.assertFalse(res.timed_out)
        self.assertIsNotNone(res.query_result)
        self.assertEqual(res.query_result.row_count, 2)
        self.assertIn("schema_introspection_ms", res.stage_latencies_ms)
        self.assertIn("sql_compilation_ms", res.stage_latencies_ms)
        self.assertIn("sqlite_execution_ms", res.stage_latencies_ms)

    def test_pipeline_deadline_timeout(self) -> None:
        """测试微秒级极限截止时间触发立即超时退出。"""
        res = self.pipeline.run_plan_and_execute(self.db_path, self.plan, deadline_sec=0.000001)
        self.assertFalse(res.success)
        self.assertTrue(res.timed_out)
        self.assertIn("deadline exceeded", res.error_message.lower())


if __name__ == "__main__":
    unittest.main()

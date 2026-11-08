"""Fei-Mini 命令行控制台与诊断单元测试 (M6.2)."""

import json
import os
import sqlite3
import tempfile
import unittest

from feimini.cli import main
from feimini.config import FeiMiniConfig


class TestFeiMiniCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "cli_test.db")

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT, balance REAL);")
        c.executemany("INSERT INTO users VALUES (?, ?, ?);", [(1, "Alice", 100.0), (2, "Bob", 200.0)])
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_help_and_version(self) -> None:
        """测试 --help 与 --version 正常退出。"""
        with self.assertRaises(SystemExit) as cm:
            main(["--help"])
        self.assertEqual(cm.exception.code, 0)

        with self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_cli_missing_database_error(self) -> None:
        """测试数据库文件不存在时优雅报错并返回退出码 1。"""
        code = main(["query", "--db", "/nonexistent/path/db.sqlite", "--question", "Show users"])
        self.assertEqual(code, 1)

    def test_cli_config_precedence(self) -> None:
        """测试 CLI 覆盖环境变量与默认配置。"""
        os.environ["FEIMINI_TIMEOUT"] = "45.0"
        os.environ["FEIMINI_MODEL"] = "env_model:latest"
        try:
            cfg = FeiMiniConfig.load(cli_overrides={"timeout": 15.0, "model": "cli_override:1.5b"})
            self.assertEqual(cfg.timeout_sec, 15.0)
            self.assertEqual(cfg.model, "cli_override:1.5b")
        finally:
            del os.environ["FEIMINI_TIMEOUT"]
            del os.environ["FEIMINI_MODEL"]

    def test_cli_doctor_runs(self) -> None:
        """测试 doctor 子命令诊断执行。"""
        code = main(["doctor"])
        self.assertIn(code, (0, 1))


if __name__ == "__main__":
    unittest.main()

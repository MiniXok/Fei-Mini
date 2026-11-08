"""SQLite 安全隔离、写操作拦截与执行超时单元测试。"""

import hashlib
import os
import sqlite3
import tempfile
import unittest

from feimini.dsl.types import Column, DataType, RelationSchema
from feimini.sqlite.backend import (
    CompiledSQLQuery,
    SQLiteExecutionBackend,
    SQLiteSecurityError,
    SQLiteTimeoutError,
)


class TestSQLiteSecurity(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "secure_test.db")

        # 创建基础表并写入测试数据
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, secret_val TEXT);")
        cursor.execute("INSERT INTO records VALUES (1, 'initial_secret');")
        cursor.execute("INSERT INTO records VALUES (2, 'alpha');")
        cursor.execute("INSERT INTO records VALUES (3, 'beta');")
        conn.commit()
        conn.close()

        # 记录数据库初始文件的 SHA-256 指纹
        with open(self.db_path, "rb") as f:
            self.initial_hash = hashlib.sha256(f.read()).hexdigest()

        self.backend = SQLiteExecutionBackend(max_rows=100, default_timeout_sec=1.0)
        self.schema = RelationSchema((Column("id", DataType.INT), Column("secret_val", DataType.STR)))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rejection_of_data_mutations(self) -> None:
        """测试对 INSERT, UPDATE, DELETE 的底层拦截。"""
        # 1. INSERT
        query_insert = CompiledSQLQuery(
            sql="INSERT INTO records VALUES (999, 'malicious');",
            params=(),
            output_schema=self.schema,
        )
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(query_insert, self.db_path)

        # 2. UPDATE
        query_update = CompiledSQLQuery(
            sql="UPDATE records SET secret_val = 'hacked';",
            params=(),
            output_schema=self.schema,
        )
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(query_update, self.db_path)

        # 3. DELETE
        query_delete = CompiledSQLQuery(
            sql="DELETE FROM records WHERE id = 1;",
            params=(),
            output_schema=self.schema,
        )
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(query_delete, self.db_path)

    def test_rejection_of_schema_mutations_and_pragmas(self) -> None:
        """测试对 DROP TABLE, ALTER TABLE, CREATE TABLE, ATTACH 的拦截。"""
        # DROP TABLE
        q_drop = CompiledSQLQuery(sql="DROP TABLE records;", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_drop, self.db_path)

        # CREATE TABLE
        q_create = CompiledSQLQuery(sql="CREATE TABLE backdoor (x INT);", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_create, self.db_path)

        # ATTACH DATABASE
        q_attach = CompiledSQLQuery(sql="ATTACH DATABASE ':memory:' AS evil;", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_attach, self.db_path)

    def test_database_hash_invariant_preserved(self) -> None:
        """验证所有非法尝试执行后，磁盘数据库文件字节完全无损未变。"""
        with open(self.db_path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(
            self.initial_hash,
            current_hash,
            "Database file was modified despite read-only security policy!",
        )

    def test_query_progress_handler_timeout_interruption(self) -> None:
        """测试递归死循环极重查询在超时设定下被安全中断。"""
        expensive_sql = """
        WITH RECURSIVE cnt(x) AS (
            SELECT 1
            UNION ALL
            SELECT x + 1 FROM cnt
        )
        SELECT count(*) FROM cnt;
        """
        q_expensive = CompiledSQLQuery(
            sql=expensive_sql,
            params=(),
            output_schema=RelationSchema((Column("x", DataType.INT),)),
        )

        with self.assertRaises(SQLiteTimeoutError):
            self.backend.execute_compiled(q_expensive, self.db_path, timeout_sec=0.05)


if __name__ == "__main__":
    unittest.main()

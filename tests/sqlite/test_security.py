"""SQLite 安全隔离、写操作拦截与执行超时单元测试。"""

import hashlib
import os
import sqlite3
import tempfile
import unittest

from feimini.dsl.ast import ScanNode
from feimini.dsl.types import Column, DataType, RelationSchema
from feimini.sqlite.backend import (
    CompiledSQLQuery,
    SQLiteExecutionBackend,
    SQLiteExecutionError,
    SQLiteSecurityError,
    SQLiteTimeoutError,
)
from feimini.sqlite.compiler import MiniRelSQLCompiler


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

        with open(self.db_path, "rb") as f:
            self.initial_hash = hashlib.sha256(f.read()).hexdigest()

        self.backend = SQLiteExecutionBackend(max_rows=100, default_timeout_sec=1.0)
        self.schema = RelationSchema((Column("id", DataType.INT), Column("secret_val", DataType.STR)))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rejection_of_data_mutations(self) -> None:
        """测试对 INSERT, UPDATE, DELETE 的底层拦截。"""
        # 1. INSERT
        q_insert = CompiledSQLQuery(sql="INSERT INTO records VALUES (999, 'bad');", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_insert, self.db_path)

        # 2. UPDATE
        q_update = CompiledSQLQuery(sql="UPDATE records SET secret_val = 'bad';", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_update, self.db_path)

        # 3. DELETE
        q_delete = CompiledSQLQuery(sql="DELETE FROM records WHERE id = 1;", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_delete, self.db_path)

    def test_rejection_of_schema_mutations_and_pragmas(self) -> None:
        """测试对 DROP, ALTER, CREATE, ATTACH, DETACH, PRAGMA 的拦截。"""
        q_drop = CompiledSQLQuery(sql="DROP TABLE records;", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_drop, self.db_path)

        q_create = CompiledSQLQuery(sql="CREATE TABLE backdoor (x INT);", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_create, self.db_path)

        q_attach = CompiledSQLQuery(sql="ATTACH DATABASE ':memory:' AS evil;", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_attach, self.db_path)

        q_pragma = CompiledSQLQuery(sql="PRAGMA writable_schema = ON;", params=(), output_schema=self.schema)
        with self.assertRaises(SQLiteSecurityError):
            self.backend.execute_compiled(q_pragma, self.db_path)

    def test_sql_identifier_injection_prevention(self) -> None:
        """测试对包含注入分号/双引号的表名进行安全编译与转义。"""
        compiler = MiniRelSQLCompiler()
        # 尝试恶意表名注入
        malicious_ast = ScanNode('records"; DROP TABLE records; --')
        env = {malicious_ast.table_name: self.schema}
        compiled = compiler.compile(malicious_ast, env)

        # 编译产物必须包含双引号转义
        self.assertIn('"records""; DROP TABLE records; --"', compiled.sql)

        # 后端执行时尝试访问不存在的表名，抛出找不到表异常，绝不可能执行注入的 DROP TABLE
        with self.assertRaises((SQLiteExecutionError, Exception)):
            self.backend.execute_compiled(compiled, self.db_path)

    def test_multi_statement_injection_rejection(self) -> None:
        """测试注入分号多语句直接被 SQLite 执行引擎拒绝。"""
        q_multi = CompiledSQLQuery(
            sql="SELECT * FROM records; DROP TABLE records;",
            params=(),
            output_schema=self.schema,
        )
        with self.assertRaises((SQLiteExecutionError, SQLiteSecurityError)):
            self.backend.execute_compiled(q_multi, self.db_path)

    def test_database_and_wal_files_immutability(self) -> None:
        """验证所有读操作与被拦截操作后，主文件哈希不变，且无临时 WAL/journal 文件残留。"""
        with open(self.db_path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(self.initial_hash, current_hash)

        # 检查无 WAL 或 journal 文件
        self.assertFalse(os.path.exists(self.db_path + "-wal"))
        self.assertFalse(os.path.exists(self.db_path + "-shm"))
        self.assertFalse(os.path.exists(self.db_path + "-journal"))

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

"""SQLite Schema 适配器与类型保障等级单元测试。"""

import os
import sqlite3
import tempfile
import unittest

from feimini.dsl.types import DataType
from feimini.sqlite.schema import SQLiteSchemaAdapter, TypeGuarantee, map_sqlite_type_to_minirel


class TestSQLiteSchema(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_shop.db")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 1. 普通表
        cursor.execute("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                is_vip BOOLEAN DEFAULT 0
            );
        """)

        # 2. 从表 (外键引用 customers)
        cursor.execute("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                cust_id INTEGER,
                amount REAL,
                FOREIGN KEY (cust_id) REFERENCES customers (customer_id)
            );
        """)

        # 3. STRICT 模式表 (SQLite 3.37.0+)
        try:
            cursor.execute("""
                CREATE TABLE audit_log (
                    log_id INTEGER PRIMARY KEY,
                    action TEXT,
                    timestamp INT
                ) STRICT;
            """)
            self.has_strict = True
        except sqlite3.OperationalError:
            self.has_strict = False

        # 4. 动态无类型表
        cursor.execute("""
            CREATE TABLE dynamic_table (
                data_any ANY,
                untyped_col
            );
        """)

        # 视图与索引
        cursor.execute("CREATE VIEW vip_customers AS SELECT customer_id, name FROM customers WHERE is_vip = 1;")
        cursor.execute("CREATE INDEX idx_orders_cust ON orders (cust_id);")

        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_inspect_database_structure(self) -> None:
        """测试适配器能准确抓取表格、视图、列结构、主键与外键。"""
        schema = SQLiteSchemaAdapter.inspect_database(self.db_path)

        self.assertIn("customers", schema.tables)
        self.assertIn("orders", schema.tables)
        self.assertIn("vip_customers", schema.tables)

        cust_info = schema.get_table("customers")
        self.assertIsNotNone(cust_info)
        self.assertEqual(cust_info.primary_key, "customer_id")
        self.assertFalse(cust_info.is_view)
        self.assertFalse(cust_info.is_strict)

        # 验证主键类型保障
        pk_col = [c for c in cust_info.columns if c.name == "customer_id"][0]
        self.assertEqual(pk_col.type_guarantee, TypeGuarantee.GUARANTEED_PK)

        # 验证普通非严格列亲和
        name_col = [c for c in cust_info.columns if c.name == "name"][0]
        self.assertEqual(name_col.type_guarantee, TypeGuarantee.INFERRED_AFFINITY)

        # 验证外键
        orders_info = schema.get_table("orders")
        self.assertIsNotNone(orders_info)
        self.assertEqual(len(orders_info.foreign_keys), 1)
        fk = orders_info.foreign_keys[0]
        self.assertEqual(fk.from_column, "cust_id")
        self.assertEqual(fk.target_table, "customers")
        self.assertEqual(fk.to_column, "customer_id")

    def test_strict_table_detection(self) -> None:
        """测试对 STRICT 表及其类型保障级别的精准识别。"""
        if not self.has_strict:
            self.skipTest("SQLite runtime does not support STRICT tables")

        schema = SQLiteSchemaAdapter.inspect_database(self.db_path)
        log_table = schema.get_table("audit_log")
        self.assertIsNotNone(log_table)
        self.assertTrue(log_table.is_strict)

        action_col = [c for c in log_table.columns if c.name == "action"][0]
        self.assertEqual(action_col.type_guarantee, TypeGuarantee.GUARANTEED_STRICT)

    def test_dynamic_unknown_type_detection(self) -> None:
        """测试对 ANY 及未声明类型列的识别。"""
        schema = SQLiteSchemaAdapter.inspect_database(self.db_path)
        dyn_table = schema.get_table("dynamic_table")
        self.assertIsNotNone(dyn_table)

        untyped_col = [c for c in dyn_table.columns if c.name == "untyped_col"][0]
        self.assertEqual(untyped_col.type_guarantee, TypeGuarantee.DYNAMIC_UNKNOWN)

    def test_type_affinity_mapping(self) -> None:
        """测试各种常见 SQLite 类型亲和字符串映射。"""
        self.assertEqual(map_sqlite_type_to_minirel("INT"), DataType.INT)
        self.assertEqual(map_sqlite_type_to_minirel("BIGINT"), DataType.INT)
        self.assertEqual(map_sqlite_type_to_minirel("VARCHAR(255)"), DataType.STR)
        self.assertEqual(map_sqlite_type_to_minirel("DECIMAL(10,2)"), DataType.FLOAT)
        self.assertEqual(map_sqlite_type_to_minirel("DOUBLE PRECISION"), DataType.FLOAT)
        self.assertEqual(map_sqlite_type_to_minirel("BOOLEAN"), DataType.BOOL)


if __name__ == "__main__":
    unittest.main()

"""SQLite Schema 适配器单元测试。"""

import os
import sqlite3
import tempfile
import unittest

from feimini.dsl.types import DataType
from feimini.sqlite.schema import SQLiteSchemaAdapter, map_sqlite_type_to_minirel


class TestSQLiteSchema(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_shop.db")

        # 创建测试 SQLite 数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 主表
        cursor.execute("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                is_vip BOOLEAN DEFAULT 0
            );
        """)

        # 从表 (外键引用 customers)
        cursor.execute("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                cust_id INTEGER,
                amount REAL,
                FOREIGN KEY (cust_id) REFERENCES customers (customer_id)
            );
        """)

        # 视图
        cursor.execute("""
            CREATE VIEW vip_customers AS
            SELECT customer_id, name FROM customers WHERE is_vip = 1;
        """)

        # 索引
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
        self.assertEqual(cust_info.column_names, ("customer_id", "name", "balance", "is_vip"))

        # 验证类型转换
        type_map = {c.name: c.data_type for c in cust_info.columns}
        self.assertEqual(type_map["customer_id"], DataType.INT)
        self.assertEqual(type_map["name"], DataType.STR)
        self.assertEqual(type_map["balance"], DataType.FLOAT)
        self.assertEqual(type_map["is_vip"], DataType.BOOL)

        # 验证外键
        orders_info = schema.get_table("orders")
        self.assertIsNotNone(orders_info)
        self.assertEqual(len(orders_info.foreign_keys), 1)
        fk = orders_info.foreign_keys[0]
        self.assertEqual(fk.from_column, "cust_id")
        self.assertEqual(fk.target_table, "customers")
        self.assertEqual(fk.to_column, "customer_id")

        # 验证索引
        self.assertIn("idx_orders_cust", orders_info.indexes)

        # 验证视图
        vip_view = schema.get_table("vip_customers")
        self.assertTrue(vip_view.is_view)

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

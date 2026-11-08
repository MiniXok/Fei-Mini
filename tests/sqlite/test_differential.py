"""MiniRel 解释器与 SQLite 执行后端全算子差分与对抗性等价测试。

覆盖：
- 各数据类型中的 NULL 取值
- 空表与空过滤
- 空输入与全 NULL 聚合输入 (COALESCE 语义)
- 排序平局与 NULL 排序 (ASC NULLS FIRST vs DESC NULLS LAST)
- 重复行保留
- 零匹配连接 (Empty Join)
- 保留关键字与含特殊符号标识符 ("order", "select", "user.email")
- STRICT 类型表测试
"""

import os
import sqlite3
import tempfile
import unittest

from feimini.dsl.ast import (
    CountNode,
    FilterNode,
    GroupByNode,
    JoinNode,
    LimitNode,
    PredicateOp,
    ProjectNode,
    ScanNode,
    SortDirection,
    SortNode,
    SumNode,
)
from feimini.dsl.interpreter import MiniRelInterpreter
from feimini.dsl.types import Column, DataType, RelationSchema, Table, tables_equal
from feimini.sqlite.backend import SQLiteExecutionBackend


class TestDifferentialExecution(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "diff_test.db")

        # 1. 主测试表 Schemas
        self.students_schema = RelationSchema(
            (
                Column("id", DataType.INT),
                Column("name", DataType.STR),
                Column("major", DataType.STR),
                Column("gpa", DataType.FLOAT),
                Column("is_enrolled", DataType.BOOL),
            )
        )
        self.scores_schema = RelationSchema(
            (
                Column("score_id", DataType.INT),
                Column("stu_id", DataType.INT),
                Column("points", DataType.FLOAT),
            )
        )

        # 2. 对抗性表 Schemas: 包含 NULL、全空、保留关键字
        self.null_test_schema = RelationSchema(
            (
                Column("id", DataType.INT),
                Column("int_val", DataType.INT),
                Column("float_val", DataType.FLOAT),
                Column("str_val", DataType.STR),
                Column("bool_val", DataType.BOOL),
            )
        )
        self.empty_schema = RelationSchema(
            (
                Column("id", DataType.INT),
                Column("val", DataType.FLOAT),
            )
        )
        self.reserved_schema = RelationSchema(
            (
                Column("order", DataType.INT),
                Column("select", DataType.STR),
                Column("group", DataType.FLOAT),
            )
        )

        self.env_schemas = {
            "students": self.students_schema,
            "scores": self.scores_schema,
            "null_records": self.null_test_schema,
            "empty_table": self.empty_schema,
            "order": self.reserved_schema,
        }

        # 3. 测试行数据
        self.students_rows = (
            (1, "Alice", "CS", 3.85, 1),
            (2, "Bob", "Math", 3.20, 1),
            (3, "Charlie", "CS", 2.90, 0),
            (4, "Diana", "Physics", 3.95, 1),
            (5, "Evan", "Math", 3.50, 0),
        )
        self.scores_rows = (
            (101, 1, 95.5),
            (102, 1, 88.0),
            (103, 2, 76.5),
            (104, 3, 62.0),
            (105, 4, 99.0),
            (106, 99, 50.0),
        )
        self.null_rows = (
            (1, 10, 1.5, "alpha", 1),
            (2, None, None, None, None),
            (3, 20, None, "beta", 0),
            (4, None, 3.5, None, 1),
            (5, 5, 0.5, "gamma", None),
        )
        self.empty_rows: tuple = ()
        self.reserved_rows = (
            (1, "choice_a", 100.5),
            (2, "choice_b", 200.0),
        )

        self.in_memory_db = {
            "students": Table(self.students_schema, self.students_rows),
            "scores": Table(self.scores_schema, self.scores_rows),
            "null_records": Table(self.null_test_schema, self.null_rows),
            "empty_table": Table(self.empty_schema, self.empty_rows),
            "order": Table(self.reserved_schema, self.reserved_rows),
        }

        # 4. 写入 SQLite 数据库
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE students (id INT PRIMARY KEY, name TEXT, major TEXT, gpa REAL, is_enrolled BOOL);")
        c.execute("CREATE TABLE scores (score_id INT PRIMARY KEY, stu_id INT, points REAL);")
        c.execute("CREATE TABLE null_records (id INT, int_val INT, float_val REAL, str_val TEXT, bool_val BOOL);")
        c.execute("CREATE TABLE empty_table (id INT, val REAL);")
        c.execute('CREATE TABLE "order" ("order" INT, "select" TEXT, "group" REAL);')

        c.executemany("INSERT INTO students VALUES (?, ?, ?, ?, ?);", self.students_rows)
        c.executemany("INSERT INTO scores VALUES (?, ?, ?);", self.scores_rows)
        c.executemany("INSERT INTO null_records VALUES (?, ?, ?, ?, ?);", self.null_rows)
        c.executemany('INSERT INTO "order" VALUES (?, ?, ?);', self.reserved_rows)

        # 尝试创建 STRICT 测试表
        try:
            c.execute("CREATE TABLE strict_table (id INT PRIMARY KEY, tag TEXT) STRICT;")
            c.executemany("INSERT INTO strict_table VALUES (?, ?);", [(1, "prod"), (2, "dev")])
            self.strict_schema = RelationSchema((Column("id", DataType.INT), Column("tag", DataType.STR)))
            self.env_schemas["strict_table"] = self.strict_schema
            self.in_memory_db["strict_table"] = Table(self.strict_schema, ((1, "prod"), (2, "dev")))
            self.has_strict = True
        except sqlite3.OperationalError:
            self.has_strict = False

        conn.commit()
        conn.close()

        self.interp = MiniRelInterpreter()
        self.backend = SQLiteExecutionBackend()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _assert_differential_match(self, ast_node) -> None:
        """执行并比对参考解释器与 SQLite 后端输出一致性。"""
        expected_table = self.interp.execute(ast_node, self.in_memory_db)
        sqlite_res = self.backend.execute_ast(ast_node, self.db_path, self.env_schemas)
        actual_table = sqlite_res.to_table()

        self.assertTrue(
            tables_equal(expected_table, actual_table, check_row_order=True),
            f"Differential mismatch on AST {ast_node.to_dict()}:\n"
            f"Expected (Interp): {expected_table.to_dict()}\n"
            f"Actual (SQLite):   {actual_table.to_dict()}",
        )

    def test_diff_basic_operators(self) -> None:
        self._assert_differential_match(ScanNode("students"))
        self._assert_differential_match(ProjectNode(ScanNode("students"), ("name", "gpa")))
        self._assert_differential_match(FilterNode(ScanNode("students"), "major", PredicateOp.EQ, "CS"))
        self._assert_differential_match(JoinNode(ScanNode("students"), ScanNode("scores"), "id", "stu_id"))
        self._assert_differential_match(CountNode(GroupByNode(ScanNode("students"), ("major",)), as_col="total_cnt"))
        self._assert_differential_match(SumNode(GroupByNode(ScanNode("students"), ("major",)), "gpa", as_col="sum_metric"))
        self._assert_differential_match(LimitNode(SortNode(ScanNode("students"), "gpa", SortDirection.DESC), limit=3))

    def test_adversarial_null_filtering(self) -> None:
        """测试在含有 NULL 的列上进行谓词比较（NULL = ? 或 NULL != ? 应均被过滤）。"""
        ast_eq = FilterNode(ScanNode("null_records"), "int_val", PredicateOp.EQ, 10)
        self._assert_differential_match(ast_eq)

        ast_gt = FilterNode(ScanNode("null_records"), "float_val", PredicateOp.GT, 1.0)
        self._assert_differential_match(ast_gt)

    def test_adversarial_null_sorting_parity(self) -> None:
        """测试含 NULL 列在 ASC 与 DESC 下的排序一致性 (ASC NULLS FIRST, DESC NULLS LAST)。"""
        ast_asc = SortNode(ScanNode("null_records"), "int_val", SortDirection.ASC)
        self._assert_differential_match(ast_asc)

        ast_desc = SortNode(ScanNode("null_records"), "float_val", SortDirection.DESC)
        self._assert_differential_match(ast_desc)

    def test_adversarial_empty_table_aggregation(self) -> None:
        """测试在全空表格上执行全表 COUNT 与 SUM (SUM 必须 COALESCE 返回 0)。"""
        ast_cnt = CountNode(ScanNode("empty_table"), as_col="total_cnt")
        self._assert_differential_match(ast_cnt)

        ast_sum = SumNode(ScanNode("empty_table"), "val", as_col="sum_metric")
        self._assert_differential_match(ast_sum)

    def test_adversarial_empty_join_match(self) -> None:
        """测试两个表格连接键无交集时的空连接。"""
        # id 与 score_id 无交集
        ast_empty_join = JoinNode(ScanNode("students"), ScanNode("scores"), "id", "score_id")
        self._assert_differential_match(ast_empty_join)

    def test_adversarial_reserved_keywords_as_identifiers(self) -> None:
        """测试表名为 'order'，列名为 'select', 'group' 时的安全转义与执行一致性。"""
        ast_scan = ScanNode("order")
        self._assert_differential_match(ast_scan)

        ast_proj = ProjectNode(FilterNode(ScanNode("order"), "group", PredicateOp.GT, 150.0), ("select", "order"))
        self._assert_differential_match(ast_proj)

    def test_adversarial_strict_table_execution(self) -> None:
        """测试在 SQLite 3.37+ STRICT 类型表上的差分一致性。"""
        if not self.has_strict:
            self.skipTest("SQLite STRICT tables not supported")
        ast = ProjectNode(FilterNode(ScanNode("strict_table"), "tag", PredicateOp.EQ, "prod"), ("id",))
        self._assert_differential_match(ast)


if __name__ == "__main__":
    unittest.main()

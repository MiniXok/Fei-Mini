"""MiniRel 解释器与 SQLite 执行后端全算子差分等价性测试。

在相同的关系数据上分别运行：
1. 内存参考解释器 (MiniRelInterpreter)
2. SQLite 执行后端 (SQLiteExecutionBackend)
严格比对结果表格的列名、数据类型、行数与每行数据内容的一致性。
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

        # 1. 构建测试 Schemas
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
        self.env_schemas = {
            "students": self.students_schema,
            "scores": self.scores_schema,
        }

        # 2. 构建测试数据 (包含整型、浮点、文本、布尔、重复行与多对一外键)
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
            (106, 99, 50.0),  # 外键不匹配行
        )

        # 内存表格
        self.in_memory_db = {
            "students": Table(self.students_schema, self.students_rows),
            "scores": Table(self.scores_schema, self.scores_rows),
        }

        # 3. 写入 SQLite 数据库
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE students (
                id INTEGER PRIMARY KEY,
                name TEXT,
                major TEXT,
                gpa REAL,
                is_enrolled BOOLEAN
            );
        """)
        c.execute("""
            CREATE TABLE scores (
                score_id INTEGER PRIMARY KEY,
                stu_id INTEGER,
                points REAL
            );
        """)
        c.executemany("INSERT INTO students VALUES (?, ?, ?, ?, ?);", self.students_rows)
        c.executemany("INSERT INTO scores VALUES (?, ?, ?);", self.scores_rows)
        conn.commit()
        conn.close()

        self.interp = MiniRelInterpreter()
        self.backend = SQLiteExecutionBackend()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _assert_differential_match(self, ast_node) -> None:
        """执行并比对参考解释器与 SQLite 后端输出一致性。"""
        # 1. 解释器执行
        expected_table = self.interp.execute(ast_node, self.in_memory_db)

        # 2. SQLite 后端执行
        sqlite_res = self.backend.execute_ast(ast_node, self.db_path, self.env_schemas)
        actual_table = sqlite_res.to_table()

        # 3. 比对表格
        self.assertTrue(
            tables_equal(expected_table, actual_table, check_row_order=True),
            f"Differential mismatch on AST {ast_node.to_dict()}:\n"
            f"Expected (Interp): {expected_table.to_dict()}\n"
            f"Actual (SQLite):   {actual_table.to_dict()}",
        )

    def test_diff_scan(self) -> None:
        self._assert_differential_match(ScanNode("students"))

    def test_diff_project(self) -> None:
        self._assert_differential_match(ProjectNode(ScanNode("students"), ("name", "gpa")))

    def test_diff_filter_eq_and_gt(self) -> None:
        self._assert_differential_match(FilterNode(ScanNode("students"), "major", PredicateOp.EQ, "CS"))
        self._assert_differential_match(FilterNode(ScanNode("students"), "gpa", PredicateOp.GT, 3.4))

    def test_diff_inner_join(self) -> None:
        self._assert_differential_match(
            JoinNode(ScanNode("students"), ScanNode("scores"), "id", "stu_id")
        )

    def test_diff_groupby_count(self) -> None:
        self._assert_differential_match(
            CountNode(GroupByNode(ScanNode("students"), ("major",)), as_col="total_cnt")
        )

    def test_diff_groupby_sum(self) -> None:
        self._assert_differential_match(
            SumNode(GroupByNode(ScanNode("students"), ("major",)), "gpa", as_col="sum_metric")
        )

    def test_diff_global_count_and_sum(self) -> None:
        self._assert_differential_match(CountNode(ScanNode("students"), as_col="total_cnt"))
        self._assert_differential_match(SumNode(ScanNode("students"), "gpa", as_col="sum_metric"))

    def test_diff_sort_and_limit(self) -> None:
        self._assert_differential_match(
            LimitNode(SortNode(ScanNode("students"), "gpa", SortDirection.DESC), limit=3)
        )

    def test_diff_complex_pipeline(self) -> None:
        # Join -> Filter -> Sort -> Limit
        pipeline = LimitNode(
            SortNode(
                FilterNode(
                    JoinNode(ScanNode("students"), ScanNode("scores"), "id", "stu_id"),
                    "points",
                    PredicateOp.GT,
                    80.0,
                ),
                "points",
                SortDirection.DESC,
            ),
            limit=2,
        )
        self._assert_differential_match(pipeline)


if __name__ == "__main__":
    unittest.main()

"""数据与任务生成器功能单元测试。"""

import random
import unittest
from feimini.dsl.types import Table
from feimini.generator.database import DatabaseGenerator
from feimini.generator.programs import ProgramComplexity, ProgramGenerator
from feimini.generator.schema import SchemaGenerator
from feimini.generator.tasks import TaskGenerator


class TestGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.rng = random.Random(42)
        self.schema_gen = SchemaGenerator()
        self.db_gen = DatabaseGenerator(min_rows=5, max_rows=15)
        self.prog_gen = ProgramGenerator()

    def test_database_fk_integrity(self) -> None:
        family = self.schema_gen.sample_family(self.rng, split="train")
        db = self.db_gen.generate(family, self.rng)

        parent_spec = [t for t in family.tables if t.fk_ref is None][0]
        child_spec = [t for t in family.tables if t.fk_ref is not None][0]

        parent_pks = {row[parent_spec.schema.index_of(parent_spec.pk_col)] for row in db[parent_spec.name].rows}
        fk_col, _ = child_spec.fk_ref  # type: ignore
        fk_idx = child_spec.schema.index_of(fk_col)

        for row in db[child_spec.name].rows:
            fk_val = row[fk_idx]
            self.assertIn(
                fk_val,
                parent_pks,
                f"Foreign key {fk_val} in {child_spec.name} not found in parent {parent_spec.name}",
            )

    def test_database_generation_determinism(self) -> None:
        family = self.schema_gen.sample_family(random.Random(100), split="train")
        db1 = self.db_gen.generate(family, random.Random(999))
        db2 = self.db_gen.generate(family, random.Random(999))

        for tbl_name in db1:
            self.assertEqual(db1[tbl_name].rows, db2[tbl_name].rows)

    def test_program_generation(self) -> None:
        family = self.schema_gen.sample_family(self.rng, split="train")
        sample_db = self.db_gen.generate(family, self.rng)

        for comp in [ProgramComplexity.SIMPLE, ProgramComplexity.MEDIUM, ProgramComplexity.COMPLEX]:
            ast = self.prog_gen.generate_candidate(family, comp, self.rng, sample_db=sample_db)
            out = self.prog_gen.interpreter.execute(ast, sample_db)
            self.assertIsInstance(out, Table)
            self.assertGreater(out.num_rows, 0)

    def test_task_serialization(self) -> None:
        tg = TaskGenerator(num_visible_examples=2, num_hidden_instances=2)
        task_data = tg.generate_task("test_001", "train", ProgramComplexity.MEDIUM, random.Random(77))

        d = task_data.to_dict()
        restored = task_data.from_dict(d)
        self.assertEqual(restored.task_id, "test_001")
        self.assertEqual(len(restored.task_spec.examples), 2)
        self.assertEqual(len(restored.hidden_instances), 2)


if __name__ == "__main__":
    unittest.main()

"""数据划分隔离与防止金标数据泄漏自动化测试。"""

import copy
import hashlib
import json
import random
import unittest
from feimini.generator.programs import ProgramComplexity
from feimini.generator.schema import ALL_FAMILIES, SchemaGenerator
from feimini.generator.tasks import TaskGenerator, TaskSpec


class TestLeakageAndSplits(unittest.TestCase):
    def setUp(self) -> None:
        self.task_gen = TaskGenerator(num_visible_examples=2, num_hidden_instances=2)

    def test_task_spec_isolation(self) -> None:
        """验证公开给解算器的 TaskSpec 绝对不包含 gold_ast 和 hidden_instances。"""
        eval_task = self.task_gen.generate_task(
            "leakage_test_001", "train", ProgramComplexity.SIMPLE, random.Random(123)
        )
        spec = eval_task.task_spec

        # 1. 属性级别检查
        self.assertFalse(hasattr(spec, "gold_ast"))
        self.assertFalse(hasattr(spec, "hidden_instances"))

        # 2. 序列化字典检查
        spec_dict = spec.to_dict()
        self.assertNotIn("gold_ast", spec_dict)
        self.assertNotIn("hidden_instances", spec_dict)

    def test_test_set_schema_holdout(self) -> None:
        """验证测试集专用的 Schema 族与训练/开发集绝对正交不重叠。"""
        schema_gen = SchemaGenerator()
        train_family_names = {f.family_name for f in schema_gen.train_dev_families}
        test_family_names = {f.family_name for f in schema_gen.test_families}

        intersection = train_family_names.intersection(test_family_names)
        self.assertEqual(len(intersection), 0, f"Found overlapping schema families: {intersection}")

    def test_manifest_tamper_detection(self) -> None:
        """验证修改任何测试任务内容都会破坏 SHA-256 清单哈希。"""
        tasks = [
            self.task_gen.generate_task(f"t_{i}", "test", ProgramComplexity.SIMPLE, random.Random(i))
            for i in range(3)
        ]
        manifest = self.task_gen.create_test_manifest(tasks, 42, "/tmp/test_manifest_temp.json")
        orig_hash = manifest["manifest_hash"]

        # 篡改其中一个任务的内容
        tampered_tasks = copy.deepcopy(tasks)
        # 修改任务的第一个示例数据
        first_task_dict = tampered_tasks[0].to_dict()
        first_task_dict["task_spec"]["complexity"] = "COMPLEX"
        tampered_tasks[0] = tampered_tasks[0].from_dict(first_task_dict)

        tampered_manifest = self.task_gen.create_test_manifest(
            tampered_tasks, 42, "/tmp/test_manifest_tampered.json"
        )
        self.assertNotEqual(
            orig_hash,
            tampered_manifest["manifest_hash"],
            "Manifest failed to detect task modification!",
        )


if __name__ == "__main__":
    unittest.main()

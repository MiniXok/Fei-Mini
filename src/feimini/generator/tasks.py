"""任务数据结构与全量数据集生成引擎。

严格划分解算器可见数据 (TaskSpec) 与评估器隔离数据 (EvaluatorTaskData)，
提供 SHA-256 数据集指纹锁定与防泄漏序列化。
"""

from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
import random
from typing import Any, Dict, List, Optional, Tuple

from ..dsl.ast import ASTNode
from ..dsl.interpreter import MiniRelInterpreter
from ..dsl.types import RelationSchema, Table
from .database import DatabaseGenerator
from .programs import ProgramComplexity, ProgramGenerator
from .schema import SchemaFamily, SchemaGenerator


@dataclass(frozen=True)
class ExamplePair:
    """输入输出示例对（对解算器完全公开）。"""
    database: Dict[str, Table]
    output_table: Table

    def to_dict(self) -> Dict[str, Any]:
        return {
            "database": {k: v.to_dict() for k, v in self.database.items()},
            "output_table": self.output_table.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExamplePair:
        db = {k: Table.from_dict(v) for k, v in data["database"].items()}
        out = Table.from_dict(data["output_table"])
        return cls(database=db, output_table=out)


@dataclass(frozen=True)
class TaskSpec:
    """解算器公开接口规范：绝不包含 gold_ast 与 hidden_instances。"""
    task_id: str
    schemas: Dict[str, RelationSchema]
    examples: Tuple[ExamplePair, ...]
    complexity: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "schemas": {k: v.to_dict() for k, v in self.schemas.items()},
            "examples": [e.to_dict() for e in self.examples],
            "complexity": self.complexity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskSpec:
        schemas = {k: RelationSchema.from_dict(v) for k, v in data["schemas"].items()}
        examples = tuple(ExamplePair.from_dict(e) for e in data["examples"])
        return cls(
            task_id=data["task_id"],
            schemas=schemas,
            examples=examples,
            complexity=data["complexity"],
        )


@dataclass(frozen=True)
class EvaluatorTaskData:
    """评估器持有的完整任务数据（包含私有金标 AST 与私有隐藏测试实例）。"""
    task_spec: TaskSpec
    gold_ast: ASTNode
    hidden_instances: Tuple[ExamplePair, ...]

    @property
    def task_id(self) -> str:
        return self.task_spec.task_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_spec": self.task_spec.to_dict(),
            "gold_ast": self.gold_ast.to_dict(),
            "hidden_instances": [h.to_dict() for h in self.hidden_instances],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvaluatorTaskData:
        spec = TaskSpec.from_dict(data["task_spec"])
        gold = ASTNode.from_dict(data["gold_ast"])
        hidden = tuple(ExamplePair.from_dict(h) for h in data["hidden_instances"])
        return cls(task_spec=spec, gold_ast=gold, hidden_instances=hidden)


class TaskGenerator:
    """批量任务合成与数据集导出器。"""

    def __init__(
        self,
        num_visible_examples: int = 3,
        num_hidden_instances: int = 3,
    ) -> None:
        self.num_visible = num_visible_examples
        self.num_hidden = num_hidden_instances
        self.schema_gen = SchemaGenerator()
        self.db_gen = DatabaseGenerator(min_rows=8, max_rows=20)
        self.prog_gen = ProgramGenerator()
        self.interpreter = MiniRelInterpreter()

    def generate_task(
        self,
        task_id: str,
        split: str,
        complexity: ProgramComplexity,
        rng: random.Random,
    ) -> EvaluatorTaskData:
        """合成单个任务（包括公开示例与隐藏评估实例）。"""
        family = self.schema_gen.sample_family(rng, split=split)
        schemas = family.get_schemas()

        # 生成首个数据库实例用于指导生成有意义的程序
        init_db = self.db_gen.generate(family, rng)
        gold_ast = self.prog_gen.generate_candidate(family, complexity, rng, sample_db=init_db)

        # 生成可见示例对
        visible_pairs: List[ExamplePair] = []
        # 第一个示例使用 init_db
        out0 = self.interpreter.execute(gold_ast, init_db)
        visible_pairs.append(ExamplePair(database=init_db, output_table=out0))

        for _ in range(self.num_visible - 1):
            db = self.db_gen.generate(family, rng)
            out = self.interpreter.execute(gold_ast, db)
            visible_pairs.append(ExamplePair(database=db, output_table=out))

        # 生成私有隐藏评估实例对（用于测试语义泛化，解算器不可见）
        hidden_pairs: List[ExamplePair] = []
        for _ in range(self.num_hidden):
            db_hid = self.db_gen.generate(family, rng)
            out_hid = self.interpreter.execute(gold_ast, db_hid)
            hidden_pairs.append(ExamplePair(database=db_hid, output_table=out_hid))

        task_spec = TaskSpec(
            task_id=task_id,
            schemas=schemas,
            examples=tuple(visible_pairs),
            complexity=complexity.value,
        )

        return EvaluatorTaskData(
            task_spec=task_spec,
            gold_ast=gold_ast,
            hidden_instances=tuple(hidden_pairs),
        )

    def generate_dataset(
        self,
        split: str,
        count: int,
        seed: int,
        output_dir: str,
    ) -> List[EvaluatorTaskData]:
        """批量生成数据集并持久化到本地目录。"""
        rng = random.Random(seed)
        os.makedirs(output_dir, exist_ok=True)

        complexities = [
            ProgramComplexity.SIMPLE,
            ProgramComplexity.MEDIUM,
            ProgramComplexity.COMPLEX,
        ]

        tasks: List[EvaluatorTaskData] = []
        for i in range(count):
            task_id = f"{split}_{i:04d}"
            comp = complexities[i % len(complexities)]
            task = self.generate_task(task_id, split, comp, rng)
            tasks.append(task)

            # 保存单个任务 JSON 文件
            file_path = os.path.join(output_dir, f"{task_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, indent=2)

        return tasks

    @staticmethod
    def create_test_manifest(
        tasks: List[EvaluatorTaskData],
        dataset_seed: int,
        manifest_path: str,
    ) -> Dict[str, Any]:
        """为测试集生成防篡改 SHA-256 哈希锁定清单。"""
        task_fingerprints = []
        hasher = hashlib.sha256()

        for t in tasks:
            task_bytes = json.dumps(t.to_dict(), sort_keys=True).encode("utf-8")
            h = hashlib.sha256(task_bytes).hexdigest()
            hasher.update(h.encode("utf-8"))
            task_fingerprints.append({
                "task_id": t.task_id,
                "complexity": t.task_spec.complexity,
                "sha256": h,
            })

        manifest = {
            "dataset_seed": dataset_seed,
            "task_count": len(tasks),
            "manifest_hash": hasher.hexdigest(),
            "tasks": task_fingerprints,
        }

        os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

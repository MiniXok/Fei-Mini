"""关系 Schema 生成器与领域 Schema 族定义。

支持将 Schema 族严格区分为训练/开发集族与测试集专用族，以防止测试集数据泄漏并测试结构泛化性。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import random

from ..dsl.types import Column, DataType, RelationSchema


@dataclass(frozen=True)
class TableSpec:
    """数据表规范，包含列结构与外键信息。"""
    name: str
    schema: RelationSchema
    pk_col: str
    fk_ref: Optional[Tuple[str, str]] = None  # (fk_col_name, ref_table_name)
    value_domains: Optional[Dict[str, List[Any]]] = None


@dataclass(frozen=True)
class SchemaFamily:
    """Schema 族，包含属于同一领域的多个关联表。"""
    family_name: str
    tables: Tuple[TableSpec, ...]
    is_test_only: bool = False

    def get_schemas(self) -> Dict[str, RelationSchema]:
        return {t.name: t.schema for t in self.tables}


# 定义内置领域 Schema 族
def _create_ecommerce_family() -> SchemaFamily:
    customers = TableSpec(
        name="customers",
        schema=RelationSchema(
            (
                Column("customer_id", DataType.INT),
                Column("city", DataType.STR),
                Column("loyalty_level", DataType.INT),
            )
        ),
        pk_col="customer_id",
        value_domains={
            "city": ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "Chengdu"],
            "loyalty_level": [1, 2, 3, 4, 5],
        },
    )
    orders = TableSpec(
        name="orders",
        schema=RelationSchema(
            (
                Column("order_id", DataType.INT),
                Column("cust_id", DataType.INT),
                Column("amount", DataType.FLOAT),
                Column("is_express", DataType.BOOL),
            )
        ),
        pk_col="order_id",
        fk_ref=("cust_id", "customers"),
        value_domains={
            "is_express": [True, False],
        },
    )
    return SchemaFamily("ecommerce", (customers, orders), is_test_only=False)


def _create_school_family() -> SchemaFamily:
    students = TableSpec(
        name="students",
        schema=RelationSchema(
            (
                Column("student_id", DataType.INT),
                Column("major", DataType.STR),
                Column("grade_year", DataType.INT),
            )
        ),
        pk_col="student_id",
        value_domains={
            "major": ["CS", "Math", "Physics", "Biology", "Economics"],
            "grade_year": [1, 2, 3, 4],
        },
    )
    courses = TableSpec(
        name="courses",
        schema=RelationSchema(
            (
                Column("course_id", DataType.INT),
                Column("stu_id", DataType.INT),
                Column("credits", DataType.INT),
                Column("score", DataType.FLOAT),
            )
        ),
        pk_col="course_id",
        fk_ref=("stu_id", "students"),
        value_domains={
            "credits": [2, 3, 4, 5],
        },
    )
    return SchemaFamily("school", (students, courses), is_test_only=False)


def _create_logistics_family() -> SchemaFamily:
    warehouses = TableSpec(
        name="warehouses",
        schema=RelationSchema(
            (
                Column("wh_id", DataType.INT),
                Column("zone", DataType.STR),
                Column("capacity", DataType.INT),
            )
        ),
        pk_col="wh_id",
        value_domains={
            "zone": ["North", "South", "East", "West", "Central"],
            "capacity": [100, 200, 500, 1000],
        },
    )
    shipments = TableSpec(
        name="shipments",
        schema=RelationSchema(
            (
                Column("shipment_id", DataType.INT),
                Column("wh_id", DataType.INT),
                Column("weight_kg", DataType.FLOAT),
                Column("cost", DataType.FLOAT),
            )
        ),
        pk_col="shipment_id",
        fk_ref=("wh_id", "warehouses"),
    )
    return SchemaFamily("logistics", (warehouses, shipments), is_test_only=False)


# 测试集保留（Hold-Out）Schema 族：模型在训练与调优期绝对不可见
def _create_finance_family() -> SchemaFamily:
    accounts = TableSpec(
        name="accounts",
        schema=RelationSchema(
            (
                Column("acc_id", DataType.INT),
                Column("branch", DataType.STR),
                Column("acc_type", DataType.STR),
            )
        ),
        pk_col="acc_id",
        value_domains={
            "branch": ["Tokyo", "London", "NewYork", "Singapore", "Zurich"],
            "acc_type": ["Savings", "Checking", "Corporate"],
        },
    )
    transactions = TableSpec(
        name="transactions",
        schema=RelationSchema(
            (
                Column("tx_id", DataType.INT),
                Column("account_id", DataType.INT),
                Column("volume", DataType.FLOAT),
                Column("fee", DataType.FLOAT),
            )
        ),
        pk_col="tx_id",
        fk_ref=("account_id", "accounts"),
    )
    return SchemaFamily("finance", (accounts, transactions), is_test_only=True)


def _create_hospital_family() -> SchemaFamily:
    patients = TableSpec(
        name="patients",
        schema=RelationSchema(
            (
                Column("patient_id", DataType.INT),
                Column("ward", DataType.STR),
                Column("priority", DataType.INT),
            )
        ),
        pk_col="patient_id",
        value_domains={
            "ward": ["ICU", "Cardiology", "Neurology", "Pediatrics"],
            "priority": [1, 2, 3, 4],
        },
    )
    visits = TableSpec(
        name="visits",
        schema=RelationSchema(
            (
                Column("visit_id", DataType.INT),
                Column("pat_id", DataType.INT),
                Column("stay_days", DataType.INT),
                Column("med_cost", DataType.FLOAT),
            )
        ),
        pk_col="visit_id",
        fk_ref=("pat_id", "patients"),
    )
    return SchemaFamily("hospital", (patients, visits), is_test_only=True)


ALL_FAMILIES = [
    _create_ecommerce_family(),
    _create_school_family(),
    _create_logistics_family(),
    _create_finance_family(),
    _create_hospital_family(),
]


class SchemaGenerator:
    """Schema 族采样与管理器。"""

    def __init__(self, families: Optional[List[SchemaFamily]] = None) -> None:
        self.families = families or ALL_FAMILIES
        self.train_dev_families = [f for f in self.families if not f.is_test_only]
        self.test_families = [f for f in self.families if f.is_test_only]

    def sample_family(self, rng: random.Random, split: str = "train") -> SchemaFamily:
        """根据数据集划分采样对应的 Schema 族。"""
        if split in ("train", "dev"):
            return rng.choice(self.train_dev_families)
        elif split == "test":
            # 测试集可采样测试专用族，也可采样已知族的复合未见组合
            return rng.choice(self.test_families)
        else:
            raise ValueError(f"Unknown split: {split}")

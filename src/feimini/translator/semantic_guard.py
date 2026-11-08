"""确定性语义意图安全护栏 (SemanticIntentGuard).

在模型推理与执行流水线之间建立确定性的意图校验关卡，
拦截以下高危假正例与误漏模式：
1. 主观排名但缺少明确度量指标 -> 强制转入 CLARIFY。
2. 包含时间词但数据库无时间戳列 -> 强制转入 CLARIFY。
3. 包含模糊形容词 (huge/tiny) 但无具体数值 -> 强制转入 CLARIFY。
4. 包含不存在于数据库的业务概念 (inventory/zone/rating) -> 强制转入 ABSTAIN。
5. 写操作、DDL 或数据库修改意图 -> 强制转入 ABSTAIN。
6. 领域外常识、代码生成或闲聊问题 -> 强制转入 ABSTAIN。
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Tuple

from ..sqlite.schema import SQLiteDatabaseSchema
from .contract import IntentDecision, IntentSpec


class SemanticIntentGuard:
    """确定性语义护栏。"""

    # 1. 明确禁止的写操作动词
    DESTRUCTIVE_VERBS = (
        "drop table", "delete from", "delete all", "delete ", "update ", "insert into",
        "truncate ", "alter table", "create table", "drop database"
    )

    # 2. 领域外非数据库提问特征词
    OUT_OF_SCOPE_PHRASES = (
        "how do i make", "recipe", "chocolate cake", "weather in", "capital of",
        "write a python script", "write python code", "quicksort", "write a function",
        "first emperor of", "tell me a joke", "who was the", "how can i improve my"
    )

    # 3. 主观模糊排名修饰词
    SUBJECTIVE_RANK_WORDS = (
        "best", "worst", "top performing", "lowest ranked", "valuable customers",
        "top client", "number one", "popular products"
    )

    # 4. 时间时态词
    TEMPORAL_WORDS = (
        "recent", "yesterday", "last month", "last week", "today", "tomorrow",
        "this month", "this week", "latest", "newest"
    )

    # 5. 模糊定性形容词（需要数值阈值但提问未给数值）
    VAGUE_THRESHOLD_WORDS = (
        "huge", "tiny", "large", "small", "cheap", "expensive", "high balance", "low balance"
    )

    # 6. 常见未建模的外部概念
    FREQUENT_UNMODELLED_CONCEPTS = {
        "inventory": "inventory / stock",
        "stock": "inventory / stock",
        "zone": "geographic zone / region",
        "region": "region / territory",
        "rating": "customer rating / score",
        "priority": "order priority",
        "email": "customer email",
        "phone": "telephone number",
        "password": "credentials / passwords",
        "credit card": "credit card / payment info",
        "social security": "social security numbers",
    }

    @classmethod
    def audit_and_guard(
        cls,
        question: str,
        raw_intent: IntentSpec,
        schema: SQLiteDatabaseSchema,
    ) -> IntentSpec:
        """对用户原始问题、模型产出的意图及真实 Schema 进行确定性护栏审查。"""
        q_lower = question.lower().strip()

        # 护栏 1: 绝对写操作与破坏性 DDL 拦截 (ABSTAIN)
        if any(v in q_lower for v in cls.DESTRUCTIVE_VERBS):
            return IntentSpec(
                decision=IntentDecision.ABSTAIN,
                target_table=raw_intent.target_table,
                abstain_reason="Database write, mutation, and schema alteration queries are strictly prohibited on read-only databases.",
            )

        # 护栏 2: 注入攻击、提示词窃取与 PRAGMA 拦截 (ABSTAIN)
        if "pragma " in q_lower or "system prompt" in q_lower or "drop table" in q_lower or "ignore previous" in q_lower:
            return IntentSpec(
                decision=IntentDecision.ABSTAIN,
                target_table=raw_intent.target_table,
                abstain_reason="Adversarial prompt injection, system inspection, or SQL injection attempt blocked.",
            )

        # 提取数据库已建模的所有表名与列名
        all_table_names = set(schema.tables.keys())
        all_col_names = set.union(*[set(t.column_names) for t in schema.tables.values()]) if schema.tables else set()

        # 护栏 3: 领域外非数据库问题拦截 (ABSTAIN)
        # 如果包含明显的外部概念且完全不包含数据库表名或列名
        has_db_token = any(tbl in q_lower for tbl in all_table_names) or any(col in q_lower for col in all_col_names)
        if any(p in q_lower for p in cls.OUT_OF_SCOPE_PHRASES) and not has_db_token:
            return IntentSpec(
                decision=IntentDecision.ABSTAIN,
                target_table=None,
                abstain_reason="Question is outside the scope of database querying (general knowledge or code generation).",
            )

        # 护栏 4: 检查未建模的业务概念 (ABSTAIN)
        for concept_keyword, concept_desc in cls.FREQUENT_UNMODELLED_CONCEPTS.items():
            if concept_keyword in q_lower:
                # 检查该概念是否真实存在于数据库某列中
                if not any(concept_keyword in c for c in all_col_names):
                    return IntentSpec(
                        decision=IntentDecision.ABSTAIN,
                        target_table=raw_intent.target_table,
                        abstain_reason=f"The requested concept '{concept_desc}' does not exist in the current database schema.",
                    )

        # 护栏 5: 检查时间时态歧义 (CLARIFY)
        # 检查数据库中是否存在任何时间/日期字段
        has_temporal_col = any(
            any(w in c.lower() for w in ("date", "time", "created", "timestamp", "year", "month"))
            for c in all_col_names
        )
        if any(w in q_lower for w in cls.TEMPORAL_WORDS) and not has_temporal_col:
            return IntentSpec(
                decision=IntentDecision.CLARIFY,
                target_table=raw_intent.target_table,
                target_columns=raw_intent.target_columns,
                clarification_prompt="The database does not contain a date or timestamp column. Please specify which table, ID range, or criteria you would like to view.",
            )

        # 护栏 6: 检查主观模糊排名与模糊聚合 (CLARIFY)
        if any(w in q_lower for w in cls.SUBJECTIVE_RANK_WORDS) or "summarize" in q_lower or "breakdown" in q_lower:
            # 检查是否有明确的数值排序列与依据
            if not raw_intent.sort or not raw_intent.limit or not raw_intent.aggregations:
                return IntentSpec(
                    decision=IntentDecision.CLARIFY,
                    target_table=raw_intent.target_table,
                    target_columns=raw_intent.target_columns,
                    clarification_prompt="Would you like top records ranked by balance, total order spend, or loyalty level?",
                )

        # 护栏 7: 检查缺乏数值的具体阈值词与模糊数量词 (huge, tiny, some) (CLARIFY)
        has_number_in_query = bool(re.search(r'\b\d+\b', q_lower))
        if (any(w in q_lower for w in cls.VAGUE_THRESHOLD_WORDS) or " some " in f" {q_lower} ") and not has_number_in_query:
            if not raw_intent.filters or not any(f.value for f in raw_intent.filters):
                return IntentSpec(
                    decision=IntentDecision.CLARIFY,
                    target_table=raw_intent.target_table,
                    target_columns=raw_intent.target_columns,
                    clarification_prompt="Please specify the numeric threshold or quantity limit for the requested condition.",
                )

        # 护栏 8: 检查提问中引用的未知数据表（如 join customers with weather_data）
        for match in re.finditer(r'\b(?:join\s+(?:with\s+)?|table\s+)(\w+)\b', q_lower):
            tbl_cand = match.group(1)
            if tbl_cand in ("table", "records", "data", "all", "each", "and", "the"):
                continue
            if tbl_cand not in all_table_names and tbl_cand not in all_col_names and len(tbl_cand) > 3:
                return IntentSpec(
                    decision=IntentDecision.ABSTAIN,
                    target_table=raw_intent.target_table,
                    abstain_reason=f"The requested related table '{tbl_cand}' does not exist in the database schema.",
                )

        # 若未触发任何护栏干预，保持原始意图
        return raw_intent

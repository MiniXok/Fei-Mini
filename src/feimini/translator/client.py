"""本地 CPU 模型意图翻译客户端。

通过本地 Ollama 实例 (qwen2.5-coder:1.5b) 执行严格受控的 GBNF / JSON Schema 约束解码，
输入自然语言问题与当前 SQLite Schema 提示，输出强类型的 IntentSpec 意图。
完全脱机运行，零云端调用，单次推理耗时严格纳入端到端单调时钟监控。
"""

from __future__ import annotations
import json
import time
from typing import Any, Dict, Optional, Tuple
import urllib.request
import urllib.error

from ..sqlite.schema import SQLiteDatabaseSchema
from .contract import IntentSpec, validate_intent_against_schema

INTENT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "target_table": {"type": "string"},
        "target_columns": {"type": "array", "items": {"type": "string"}},
        "aggregations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["SUM", "COUNT"]},
                    "column": {"type": "string"},
                    "as_col": {"type": "string"},
                },
                "required": ["op", "column", "as_col"],
            },
        },
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "op": {"type": "string", "enum": ["EQ", "NEQ", "GT", "LT", "GTE", "LTE"]},
                    "value": {"type": ["string", "number", "boolean"]},
                },
                "required": ["column", "op", "value"],
            },
        },
        "sort": {
            "type": "object",
            "properties": {
                "column": {"type": "string"},
                "direction": {"type": "string", "enum": ["ASC", "DESC"]},
            },
            "required": ["column", "direction"],
        },
        "limit": {"type": "integer"},
        "clarification_needed": {"type": "boolean"},
        "clarification_prompt": {"type": "string"},
        "unsupported": {"type": "boolean"},
        "unsupported_reason": {"type": "string"},
    },
    "required": ["target_table", "target_columns", "clarification_needed"],
}

TRANSLATOR_SYSTEM_PROMPT = """You are Fei-Mini's local database translator.
Translate the user's natural language question into a structured IntentSpec JSON object.
Use ONLY the provided database schema. Do not generate SQL. Do not invent columns.

Rules:
1. When the question contains conditions or criteria (e.g. 'living in Beijing', 'amount > 500', 'VIP'), YOU MUST include them in 'filters'.
2. When the question asks for top/highest/lowest N, YOU MUST include 'sort' and 'limit'.
3. When the question asks for totals/counts/sums, YOU MUST include 'aggregations'.
4. If the query is clear and specific, set 'clarification_needed': false.
5. If the query is genuinely ambiguous or lacks key ranking criteria (e.g. 'best customers'), set 'clarification_needed': true with a 'clarification_prompt'.
6. If the query asks for write/mutation operations (insert/update/delete/drop/alter) or non-existent tables, set 'unsupported': true with 'unsupported_reason'.

Example 1 (Filter and Projection):
Question: Show names of VIP customers in Beijing
JSON: {"target_table": "customers", "target_columns": ["name"], "filters": [{"column": "city", "op": "EQ", "value": "Beijing"}, {"column": "is_vip", "op": "EQ", "value": true}], "clarification_needed": false}

Example 2 (Ambiguous Request):
Question: Show me the best customers
JSON: {"target_table": "customers", "target_columns": ["name"], "clarification_needed": true, "clarification_prompt": "Would you like top customers ranked by highest balance or loyalty level?"}

Example 3 (Prohibited Mutation):
Question: Delete customer 123
JSON: {"target_table": "customers", "target_columns": [], "clarification_needed": false, "unsupported": true, "unsupported_reason": "Database mutations (delete, update, insert, drop) are prohibited on read-only databases."}
"""


class TranslatorTimeoutError(Exception):
    """翻译模型推理超时。"""
    pass


class TranslatorClientError(Exception):
    """翻译客户端交互错误。"""
    pass


class LocalTranslatorClient:
    """本地模型接口客户端。"""

    def __init__(
        self,
        model_name: str = "qwen2.5-coder:1.5b",
        api_url: str = "http://127.0.0.1:11434/api/generate",
        num_threads: int = 4,
    ) -> None:
        self.model_name = model_name
        self.api_url = api_url
        self.num_threads = num_threads

    def format_schema_prompt(self, schema: SQLiteDatabaseSchema) -> str:
        """将当前真实数据库元数据格式化为紧凑 Schema 提示。"""
        lines = ["Database Schema:"]
        for tbl_name, tbl in schema.tables.items():
            if tbl.is_view:
                continue
            lines.append(f"Table '{tbl_name}':")
            for col in tbl.columns:
                pk_str = ", PRIMARY KEY" if col.is_pk else ""
                lines.append(f"  - {col.name} ({col.data_type.value}{pk_str})")
            for fk in tbl.foreign_keys:
                lines.append(f"  [FK] {fk.from_column} -> {fk.target_table}.{fk.to_column}")
        return "\n".join(lines)

    def translate_question(
        self,
        question: str,
        schema: SQLiteDatabaseSchema,
        timeout_sec: float = 15.0,
    ) -> Tuple[IntentSpec, float]:
        """将用户问题翻译为合法的 IntentSpec，并记录模型推理时间。"""
        schema_text = self.format_schema_prompt(schema)
        prompt = f"{schema_text}\n\nUser Question: {question}\nStructured IntentSpec JSON:"

        payload = {
            "model": self.model_name,
            "system": TRANSLATOR_SYSTEM_PROMPT,
            "prompt": prompt,
            "format": INTENT_JSON_SCHEMA,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_gpu": 0,       # 强制纯 CPU 运算
                "num_thread": self.num_threads,
                "num_predict": 256,
            },
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=data_bytes, headers={"Content-Type": "application/json"})

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                raise TranslatorTimeoutError(f"Model inference timed out after {timeout_sec:.2f}s")
            raise TranslatorClientError(f"Local model connection failed: {e}")
        except Exception as e:
            raise TranslatorClientError(f"Model request failed: {e}")

        inference_time_sec = time.perf_counter() - t0
        raw_text = res_data.get("response", "")

        try:
            parsed = json.loads(raw_text)
            intent = IntentSpec.from_dict(parsed)
        except Exception as e:
            raise TranslatorClientError(f"Failed to parse model output into IntentSpec: {e}\nRaw: {raw_text}")

        return intent, inference_time_sec

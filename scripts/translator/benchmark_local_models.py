#!/usr/bin/env python3
"""Phase 1: Local Model Inference & Structured Decoding Benchmark.

严格在 CPU 模式下 (num_gpu=0, 4 线程) 评测候选模型：
A. Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF (qwen2.5-coder:1.5b)
B. MiniCPM5-2B-GGUF (minicpm5-2b-q4-k-m.gguf:latest)

测量指标：
- 模型加载耗时 (Load duration)
- 首 token 延迟 (Time to first token / Prompt eval)
- 生成速度 (Tokens per second)
- 端到端翻译耗时 (Total latency)
- 结构化 JSON 模式遵守率 (Schema validity)
- 澄清协议意图捕捉 (Clarification behavior)
"""

import json
import os
import resource
import sys
import time
import urllib.request
import numpy as np

INTENT_JSON_SCHEMA = {
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
    },
    "required": ["target_table", "target_columns", "clarification_needed"],
}

SYSTEM_PROMPT = """You are Fei-Mini's local database translator.
Translate the user's natural language question into a structured IntentSpec JSON object.
Use only the provided schema. Do not generate SQL. Do not invent columns.
If the query is ambiguous, set "clarification_needed": true and provide a "clarification_prompt".
"""

SCHEMA_CONTEXT = """Database Schema:
Table 'customers':
  - customer_id (INT, PRIMARY KEY)
  - name (STR)
  - city (STR, values: ['Beijing', 'Shanghai', 'Shenzhen'])
  - balance (FLOAT)
  - is_vip (BOOL)
Table 'orders':
  - order_id (INT, PRIMARY KEY)
  - cust_id (INT, FOREIGN KEY -> customers.customer_id)
  - amount (FLOAT)
"""

BENCHMARK_PROMPTS = [
    {
        "id": "p1_unambiguous",
        "question": "Find the top 5 customers in Beijing by balance descending",
        "expected_clarification": False,
    },
    {
        "id": "p2_filter",
        "question": "List all orders where amount is greater than 200",
        "expected_clarification": False,
    },
    {
        "id": "p3_ambiguous",
        "question": "Show me the best customers",
        "expected_clarification": True,
    },
]


def query_ollama(model_name: str, prompt_text: str) -> Dict[str, Any]:
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": model_name,
        "system": SYSTEM_PROMPT,
        "prompt": f"{SCHEMA_CONTEXT}\n\nQuestion: {prompt_text}\nJSON Intent:",
        "format": INTENT_JSON_SCHEMA,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_gpu": 0,       # 强制 CPU 推理
            "num_thread": 4,    # 4 物理核心
            "num_predict": 256,
        },
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60.0) as resp:
        res_json = json.loads(resp.read().decode("utf-8"))
    wall_duration = time.perf_counter() - t0
    res_json["client_wall_sec"] = wall_duration
    return res_json


def benchmark_model(model_name: str) -> Dict[str, Any]:
    print(f"\nEvaluating Model: {model_name} on CPU...")

    # 预热一次加载模型
    print("  Warming up model...")
    warm_res = query_ollama(model_name, "Hello, is table customers present?")
    load_duration_s = warm_res.get("load_duration", 0) / 1e9

    prompt_eval_times = []
    eval_rates = []
    e2e_latencies = []
    valid_json_count = 0
    correct_clarification_count = 0

    responses = []

    for item in BENCHMARK_PROMPTS:
        qid = item["id"]
        q_text = item["question"]
        print(f"  Running test case [{qid}]...")

        res = query_ollama(model_name, q_text)
        resp_text = res.get("response", "")

        # 统计性能指标
        prompt_eval_s = res.get("prompt_eval_duration", 0) / 1e9
        eval_count = res.get("eval_count", 0)
        eval_duration_s = res.get("eval_duration", 0) / 1e9
        tps = (eval_count / eval_duration_s) if eval_duration_s > 0 else 0.0
        client_sec = res.get("client_wall_sec", 0.0)

        prompt_eval_times.append(prompt_eval_s)
        eval_rates.append(tps)
        e2e_latencies.append(client_sec)

        # 验证 JSON 有效性
        try:
            parsed = json.loads(resp_text)
            valid_json = True
            valid_json_count += 1
            # 检查澄清行为
            is_clarification = parsed.get("clarification_needed", False)
            if is_clarification == item["expected_clarification"]:
                correct_clarification_count += 1
        except Exception:
            valid_json = False
            parsed = None

        responses.append({
            "prompt_id": qid,
            "raw_response": resp_text,
            "parsed": parsed,
            "valid_json": valid_json,
            "tokens_generated": eval_count,
            "tokens_per_sec": round(tps, 2),
            "wall_sec": round(client_sec, 3),
        })

    peak_ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

    summary = {
        "model_name": model_name,
        "load_duration_sec": round(load_duration_s, 3),
        "mean_time_to_first_token_sec": round(float(np.mean(prompt_eval_times)), 3),
        "mean_tokens_per_sec": round(float(np.mean(eval_rates)), 2),
        "mean_e2e_latency_sec": round(float(np.mean(e2e_latencies)), 3),
        "json_validity_rate": round(valid_json_count / len(BENCHMARK_PROMPTS), 4),
        "clarification_accuracy": round(correct_clarification_count / len(BENCHMARK_PROMPTS), 4),
        "peak_ram_mb": round(peak_ram_mb, 2),
        "responses": responses,
    }

    print(f"  Load Time: {summary['load_duration_sec']:.2f}s")
    print(f"  Tokens/Sec: {summary['mean_tokens_per_sec']:.2f}")
    print(f"  Mean E2E Latency: {summary['mean_e2e_latency_sec']:.2f}s")
    print(f"  JSON Validity: {summary['json_validity_rate']*100:.1f}%")
    print(f"  Clarification Accuracy: {summary['clarification_accuracy']*100:.1f}%")

    return summary


def main():
    candidate_a = "qwen2.5-coder:1.5b"
    candidate_b = "minicpm5-2b-q4-k-m.gguf:latest"

    results = {
        "candidate_a": benchmark_model(candidate_a),
        "candidate_b": benchmark_model(candidate_b),
    }

    os.makedirs("results/v2", exist_ok=True)
    out_file = "results/v2/m6_1_model_benchmarks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nBenchmark results saved to: {out_file}")


if __name__ == "__main__":
    main()

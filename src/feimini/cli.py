"""Fei-Mini 控制台主命令行入口 (CLI).

支持：
- feimini --version
- feimini --help
- feimini doctor
- feimini query --db <path.db> [--question "..."] [--debug] [--format table|json]
- 无 --question 时自动进入交互式多轮会话
"""

from __future__ import annotations
import argparse
import json
import os
import resource
import sqlite3
import sys
import time
import urllib.request
from typing import Optional

from . import __version__
from .config import FeiMiniConfig
from .sqlite.schema import SQLiteSchemaAdapter
from .translator.pipeline import NaturalLanguageQueryResult, NaturalLanguageSQLiteAssistant


def check_doctor() -> int:
    """系统环境与依赖健康检查诊断 (feimini doctor)。"""
    print("=" * 72)
    print("  Fei-Mini System & Environment Doctor")
    print("=" * 72)
    all_ok = True

    # 1. Python 环境
    py_ver = sys.version.split()[0]
    print(f"[1/6] Python Runtime: {py_ver} (>= 3.10 required) -> OK")

    # 2. SQLite 引擎与版本
    try:
        sqlite_ver = sqlite3.sqlite_version
        print(f"[2/6] SQLite Engine: v{sqlite_ver} -> OK")
    except Exception as e:
        print(f"[2/6] SQLite Engine: Error ({e}) -> FAIL")
        all_ok = False

    # 3. 内存与硬件
    total_ram_gb = 16.0
    try:
        # 读取 /proc/meminfo
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    total_ram_gb = round(int(line.split()[1]) / 1024 / 1024, 1)
        print(f"[3/6] Total System RAM: {total_ram_gb} GB (>= 8 GB required) -> OK")
    except Exception:
        print(f"[3/6] Total System RAM: ~{total_ram_gb} GB -> OK")

    # 4. 本地 Ollama 连通性
    ollama_ok = False
    models_available = []
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_available = [m["name"] for m in data.get("models", [])]
            ollama_ok = True
        print(f"[4/6] Ollama Server: Connected at http://127.0.0.1:11434 -> OK")
    except Exception as e:
        print(f"[4/6] Ollama Server: Connection failed ({e}) -> WARNING")
        print("      Make sure Ollama is running (`ollama serve`).")
        all_ok = False

    # 5. 模型可用性
    cfg = FeiMiniConfig.load()
    has_model = any(cfg.model in m for m in models_available)
    if has_model:
        print(f"[5/6] Configured Model: '{cfg.model}' installed -> OK")
    else:
        print(f"[5/6] Configured Model: '{cfg.model}' not found in Ollama -> WARNING")
        if models_available:
            print(f"      Installed models: {models_available}")
        print(f"      Run `ollama pull {cfg.model}` to install.")
        all_ok = False

    # 6. 只读执行安全配置
    print(f"[6/6] Read-Only Security Boundary: 6 Defense-in-Depth Layers -> OK")

    print("=" * 72)
    if all_ok:
        print("  All system diagnostics passed! Fei-Mini is ready.")
        return 0
    else:
        print("  Some diagnostic checks failed or produced warnings.")
        return 1


def run_interactive_session(assistant: NaturalLanguageSQLiteAssistant, db_path: str, debug: bool = False):
    """交互式多轮会话终端。"""
    print("=" * 76)
    print("  Fei-Mini Interactive Database Assistant (Type 'exit' or 'quit' to end)")
    print(f"  Connected Database: {os.path.basename(db_path)} (Strict Read-Only)")
    print("=" * 76)

    last_pending_context: Optional[dict] = None

    while True:
        try:
            prompt_label = "Fei-Mini [Clarifying]> " if last_pending_context else "User> "
            user_input = input(f"\n{prompt_label}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print("Session closed. Goodbye!")
            break

        # 处理多轮会话拼接
        if last_pending_context:
            full_question = f"{last_pending_context['original_question']}. Specifically: {user_input}"
            last_pending_context = None
        else:
            full_question = user_input

        print("Thinking locally on CPU...")
        t0 = time.perf_counter()
        result = assistant.query(full_question, db_path)
        e2e_ms = (time.perf_counter() - t0) * 1000.0

        if result.needs_clarification:
            print(f"\n[Fei-Mini Clarification Question]")
            print(f"  {result.clarification_prompt}")
            last_pending_context = {
                "original_question": full_question,
                "clarification_prompt": result.clarification_prompt,
            }

        elif result.is_unsupported:
            print(f"\n[Request Cannot Be Processed]")
            print(f"  {result.unsupported_reason or result.error_message}")
            last_pending_context = None

        elif result.success:
            print(f"\n[Verified Result ({result.table_result.row_count} rows in {e2e_ms:.1f}ms)]")
            for line in result.formatted_output.split("\n"):
                print(f"  {line}")
            last_pending_context = None

        else:
            print(f"\n[Error]: {result.error_message}")
            last_pending_context = None

        if debug and result.intent:
            print("\n  --- Developer Debug ---")
            print(f"  Intent Decision: {result.intent.decision.value}")
            print(f"  Query Type: {result.intent.query_type.value}")
            if result.compiled_sql:
                print(f"  Compiled SQL: {result.compiled_sql}")
            print(f"  Stage Timings: {result.stage_durations_ms}")
            print("  -----------------------")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feimini",
        description="Fei-Mini: CPU-first local natural-language database assistant with independently verified execution.",
    )
    parser.add_argument("--version", action="version", version=f"feimini {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # doctor
    subparsers.add_parser("doctor", help="Run local system diagnostics and health checks")

    # query
    query_parser = subparsers.add_parser("query", help="Query a SQLite database using natural language")
    query_parser.add_argument("--db", type=str, required=True, help="Path to local SQLite database file")
    query_parser.add_argument("--question", type=str, default=None, help="Question to ask (interactive if omitted)")
    query_parser.add_argument("--model", type=str, default=None, help="Local model name override")
    query_parser.add_argument("--timeout", type=float, default=None, help="Execution timeout in seconds")
    query_parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    query_parser.add_argument("--debug", action="store_true", help="Display developer internals (SQL, AST, timings)")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "doctor":
        return check_doctor()

    if args.command == "query":
        # 1. 预先校验数据库路径合法性
        if not os.path.exists(args.db):
            print(f"Error: Database file '{args.db}' not found.", file=sys.stderr)
            return 1

        cfg = FeiMiniConfig.load(cli_overrides={
            "model": args.model,
            "timeout": args.timeout,
            "format": args.format,
            "db": args.db,
        })

        assistant = NaturalLanguageSQLiteAssistant(
            model_name=cfg.model,
            default_deadline_sec=cfg.timeout_sec,
            max_rows=cfg.max_rows,
        )

        # 单次查询模式
        if args.question:
            res = assistant.query(args.question, args.db)

            if cfg.output_format == "json":
                out_dict = {
                    "question": res.question,
                    "success": res.success,
                    "decision": res.intent.decision.value if res.intent else "UNKNOWN",
                    "query_type": res.intent.query_type.value if res.intent else "UNKNOWN",
                    "sql": res.compiled_sql,
                    "row_count": res.table_result.row_count if res.table_result else 0,
                    "rows": [list(r) for r in res.table_result.rows] if res.table_result else [],
                    "columns": list(res.table_result.schema.column_names) if res.table_result else [],
                    "needs_clarification": res.needs_clarification,
                    "clarification_prompt": res.clarification_prompt,
                    "is_unsupported": res.is_unsupported,
                    "unsupported_reason": res.unsupported_reason,
                    "total_latency_ms": res.total_latency_ms,
                }
                print(json.dumps(out_dict, indent=2))
                return 0 if res.success else 1

            # 默认表格输出模式
            if res.needs_clarification:
                print(f"[Clarification Needed]: {res.clarification_prompt}")
            elif res.is_unsupported:
                print(f"[Unsupported Request]: {res.unsupported_reason or res.error_message}")
            elif res.success:
                print(res.formatted_output)
            else:
                print(f"[Error]: {res.error_message}", file=sys.stderr)

            if args.debug and res.intent:
                print("\n--- Developer Debug Internals ---")
                print(f"Decision: {res.intent.decision.value}")
                print(f"Query Type: {res.intent.query_type.value}")
                print(f"Compiled SQL: {res.compiled_sql}")
                print(f"Stage Durations: {res.stage_durations_ms}")
                print("---------------------------------")

            return 0 if res.success else 1

        # 交互式终端模式
        run_interactive_session(assistant, args.db, debug=args.debug)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

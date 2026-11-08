"""Fei-Mini 全局配置管理模块 (Phase 6).

配置优先级：CLI 参数 > 环境变量 (FEIMINI_*) > 配置文件 (~/.feimini/config.json) > 默认值。
绝对不以明文存储密码或敏感凭证。
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
from typing import Any, Dict, Optional


DEFAULT_CONFIG_PATH = os.path.expanduser("~/.feimini/config.json")


@dataclass
class FeiMiniConfig:
    """Fei-Mini 运行时配置数据模型。"""
    model: str = "qwen2.5-coder:1.5b"
    timeout_sec: float = 20.0
    num_threads: int = 4
    output_format: str = "table"  # "table" | "json"
    default_db: Optional[str] = None
    max_rows: int = 1000
    ollama_url: str = "http://127.0.0.1:11434/api/generate"

    @classmethod
    def load(
        cls,
        config_path: Optional[str] = None,
        cli_overrides: Optional[Dict[str, Any]] = None,
    ) -> FeiMiniConfig:
        """按优先级合并并加载配置：CLI > ENV > File > Defaults。"""
        # 1. 默认配置
        cfg = cls()

        # 2. 配置文件 (~/.feimini/config.json)
        path = config_path or os.environ.get("FEIMINI_CONFIG", DEFAULT_CONFIG_PATH)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                if "model" in file_data:
                    cfg.model = str(file_data["model"])
                if "timeout_sec" in file_data:
                    cfg.timeout_sec = float(file_data["timeout_sec"])
                if "num_threads" in file_data:
                    cfg.num_threads = int(file_data["num_threads"])
                if "output_format" in file_data:
                    cfg.output_format = str(file_data["output_format"])
                if "default_db" in file_data:
                    cfg.default_db = str(file_data["default_db"])
            except Exception:
                pass

        # 3. 环境变量 (FEIMINI_*)
        if "FEIMINI_MODEL" in os.environ:
            cfg.model = os.environ["FEIMINI_MODEL"]
        if "FEIMINI_TIMEOUT" in os.environ:
            try:
                cfg.timeout_sec = float(os.environ["FEIMINI_TIMEOUT"])
            except ValueError:
                pass
        if "FEIMINI_THREADS" in os.environ:
            try:
                cfg.num_threads = int(os.environ["FEIMINI_THREADS"])
            except ValueError:
                pass
        if "FEIMINI_FORMAT" in os.environ:
            cfg.output_format = os.environ["FEIMINI_FORMAT"]
        if "FEIMINI_DB" in os.environ:
            cfg.default_db = os.environ["FEIMINI_DB"]
        if "FEIMINI_OLLAMA_URL" in os.environ:
            cfg.ollama_url = os.environ["FEIMINI_OLLAMA_URL"]

        # 4. CLI 覆盖
        if cli_overrides:
            if cli_overrides.get("model"):
                cfg.model = cli_overrides["model"]
            if cli_overrides.get("timeout") is not None:
                cfg.timeout_sec = float(cli_overrides["timeout"])
            if cli_overrides.get("format"):
                cfg.output_format = cli_overrides["format"]
            if cli_overrides.get("db"):
                cfg.default_db = cli_overrides["db"]

        return cfg

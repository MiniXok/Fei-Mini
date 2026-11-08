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


class ConfigurationError(Exception):
    """配置加载与格式校验异常。"""
    pass


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
        cfg = cls()

        # 2. 配置文件 (~/.feimini/config.json 或指定路径)
        path = config_path or os.environ.get("FEIMINI_CONFIG", DEFAULT_CONFIG_PATH)
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in configuration file '{path}': {e}. Please fix or remove the file.")
            except Exception as e:
                raise ConfigurationError(f"Failed to read configuration file '{path}': {e}")

            if isinstance(file_data, dict):
                if "model" in file_data:
                    cfg.model = str(file_data["model"])
                if "timeout_sec" in file_data:
                    try:
                        cfg.timeout_sec = float(file_data["timeout_sec"])
                    except ValueError:
                        raise ConfigurationError(f"Invalid 'timeout_sec' in config '{path}': must be a positive number.")
                if "num_threads" in file_data:
                    try:
                        cfg.num_threads = int(file_data["num_threads"])
                    except ValueError:
                        raise ConfigurationError(f"Invalid 'num_threads' in config '{path}': must be an integer.")
                if "output_format" in file_data:
                    fmt = str(file_data["output_format"]).lower()
                    if fmt not in ("table", "json"):
                        raise ConfigurationError(f"Invalid 'output_format' in config '{path}': must be 'table' or 'json'.")
                    cfg.output_format = fmt
                if "default_db" in file_data:
                    cfg.default_db = str(file_data["default_db"])
                if "ollama_url" in file_data:
                    cfg.ollama_url = str(file_data["ollama_url"])

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
            fmt = os.environ["FEIMINI_FORMAT"].lower()
            if fmt in ("table", "json"):
                cfg.output_format = fmt
        if "FEIMINI_DB" in os.environ:
            cfg.default_db = os.environ["FEIMINI_DB"]
        if "FEIMINI_OLLAMA_URL" in os.environ:
            cfg.ollama_url = os.environ["FEIMINI_OLLAMA_URL"]

        # 4. CLI 覆盖
        if cli_overrides:
            if cli_overrides.get("model"):
                cfg.model = cli_overrides["model"]
            if cli_overrides.get("timeout") is not None:
                try:
                    cfg.timeout_sec = float(cli_overrides["timeout"])
                except ValueError:
                    raise ConfigurationError(f"CLI timeout '{cli_overrides['timeout']}' must be a number.")
            if cli_overrides.get("format"):
                fmt = str(cli_overrides["format"]).lower()
                if fmt in ("table", "json"):
                    cfg.output_format = fmt
            if cli_overrides.get("db"):
                cfg.default_db = cli_overrides["db"]

        # 终极合法性校验
        if cfg.timeout_sec <= 0:
            raise ConfigurationError(f"Configured timeout_sec ({cfg.timeout_sec}) must be greater than 0.")
        if cfg.num_threads <= 0:
            raise ConfigurationError(f"Configured num_threads ({cfg.num_threads}) must be at least 1.")

        return cfg

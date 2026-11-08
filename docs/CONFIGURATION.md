# Fei-Mini Configuration Guide

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  

---

## 1. Configuration Precedence

Fei-Mini resolves configuration using strict priority order:
1. **Command-Line Arguments** (`--model`, `--timeout`, `--format`, `--db`)
2. **Environment Variables** (`FEIMINI_*`)
3. **Configuration File** (`~/.feimini/config.json`)
4. **Hardcoded Defaults**

---

## 2. Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| **`FEIMINI_MODEL`** | Local model name in Ollama | `qwen2.5-coder:1.5b` |
| **`FEIMINI_TIMEOUT`** | Per-request timeout in seconds | `20.0` |
| **`FEIMINI_THREADS`** | Number of CPU inference threads | `4` |
| **`FEIMINI_FORMAT`** | Output format (`table` or `json`) | `table` |
| **`FEIMINI_DB`** | Default SQLite database file path | `None` |
| **`FEIMINI_OLLAMA_URL`**| Ollama HTTP API endpoint | `http://127.0.0.1:11434/api/generate` |
| **`FEIMINI_CONFIG`** | Custom path to configuration file | `~/.feimini/config.json` |

---

## 3. Configuration File (`~/.feimini/config.json`)

To set persistent local defaults without environment variables, create `~/.feimini/config.json`:
```json
{
  "model": "qwen2.5-coder:1.5b",
  "timeout_sec": 25.0,
  "num_threads": 4,
  "output_format": "table",
  "default_db": "/path/to/my_database.db"
}
```

*Security Invariant:* Fei-Mini strictly forbids storing plaintext passwords or API keys in configuration files.

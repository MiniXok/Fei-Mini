<div align="center">
  <img src="assets/brand/feimini-logo.png" alt="Fei-Mini Logo" width="560"/>

  <p align="center">
    <strong>CPU 优先、端到端本地运行的 SQLite 数据库自然语言查询助手。</strong><br/>
    由强类型关系代数中间表示、语法约束解码与独立验证执行引擎强力驱动。
  </p>

  <p align="center">
    <a href="README.md">English</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>

  <p align="center">
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"/></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python Version"/></a>
    <a href="docs/M6_2_1_INSTALLATION_AUDIT.md"><img src="https://img.shields.io/badge/Hardware-CPU--First_(0_GPU)-success.svg" alt="Hardware"/></a>
    <a href="https://github.com/MiniXok/Fei-Mini/releases"><img src="https://img.shields.io/badge/Release-v0.1.0-brightgreen.svg" alt="Release"/></a>
    <a href="https://minixok.pages.dev/"><img src="https://img.shields.io/badge/Organization-MiniXok-black.svg" alt="Organization"/></a>
  </p>
</div>

---

## 1. 项目简介

**Fei-Mini** 是由 **[MiniXok](https://minixok.pages.dev/)** 研发的开源、脱机本地运行、CPU 优先的自然语言数据库交互系统。它允许开发者、数据分析师与业务人员使用日常自然语言直接查询本地 SQLite 数据库，无需手工编写 SQL 语句。

与传统的“大模型直接生成 SQL”或将企业私密数据上传至云端 API 的包装套壳应用不同，Fei-Mini 将**纯本地小语言模型**与**确定性关系程序规划及六层纵深防御只读执行后端**相结合。在架构设计上，Fei-Mini 在物理层面杜绝了删表 (`DROP TABLE`)、修改记录 (`UPDATE`/`DELETE`) 以及未经类型校验的非受控 SQL 执行。

> **定位声明：** Fei-Mini 专用于支持特定分析型 SQLite 查询的本地自然语言接口。它**不是**通用闲聊机器人、代码生成器或开放问答对话系统。

---

## 2. 核心特性

- **100% 本地脱机与数据隐私保护：** 完整基于本地小语言模型（通过 Ollama 驱动 `Qwen2.5-Coder-1.5B`）在单机 CPU 上推理，零外部云端网络请求，零遥测外传。
- **CPU 优先设计：** 针对普通办公笔记本电脑优化（Intel Core i5 / 16 GB 内存），无需任何独立 GPU、显卡或 CUDA 环境。
- **语法约束解码：** 在 token 采样底层注入严格的 JSON Schema 上下文无关文法约束，彻底杜绝模型幻觉产生非法 SQL 语法或残缺输出。
- **确定性语义护栏 (SemanticIntentGuard)：** 在执行前独立审查模型意图，在微秒级即时拦截写操作、注入攻击与脱离当前 Schema 的模糊请求。
- **强类型中间表示 (MiniRel)：** 查询意图被解析为严格类型检查的关系代数语法树 (AST)，并与真实 SQLite 元数据进行静态 Schema 校验。
- **六层只读纵深防御：** 涵盖只读 URI (`mode=ro`)、`PRAGMA query_only = ON;`、底层 SQLite C Authorizer 动作拦截回调、指令级中断处理器与行数内存硬上限。
- **多轮交互式会话澄清：** 面对主观或存在歧义的提问时，Fei-Mini 拒绝盲目猜测，主动暂停并向用户提出明确的单选题澄清。

---

## 3. 架构总览

Fei-Mini 严密分离**不可信的自然语言意图理解**与**权威的独立验证执行**：

```
[用户自然语言提问]
         |
         v
[本地端小模型 (Qwen2.5-Coder-1.5B through Ollama)]
  - 纯 CPU 推理 (常驻内存 < 1.5 GB)
  - 词元级 JSON Schema 语法强制约束
         |
         v  IntentSpec 结构化 JSON
[确定性语义安全护栏 (SemanticIntentGuard)]
  - 拦截破坏性写操作 (DROP/DELETE/UPDATE)
  - 识别脱离 Schema 的主观模糊词与非法注入
         |
         v  审查后的意图 (EXECUTE / CLARIFY / ABSTAIN)
[MiniRel 关系规划解析器 (IntentResolver)]
  - 自动从 SQLite 元数据中发现外键连接拓扑
  - 构建强类型 MiniRel 关系语法树 (< 0.05 ms)
         |
         v  类型安全 AST
[MiniRel-to-SQL 编译器 (MiniRelSQLCompiler)]
  - 参数化编译，严格使用 ? 占位符 (< 0.03 ms)
  - 自动消除多表连接重名冲突 (right.col 前缀)
         |
         v  参数化只读 SQLite SELECT
[只读 SQLite 执行引擎 (SQLiteExecutionBackend)]
  - 6 层纵深防御安全体系 (mode=ro, query_only, C Authorizer)
  - 10 万行级真实数据库毫秒级原生查询 (< 8 ms)
         |
         v
[验证后的格式化结果呈现 / 交互式澄清请求]
```

---

## 4. 工作流程

1. **Schema 检查：** Fei-Mini 查询 `sqlite_master` 与系统 PRAGMA 元数据构建内存表关系图，绝不扫描全表数据。
2. **意图翻译：** 问题与 Schema 目录传递给本地模型，在不可变的 JSON Schema 语法约束下输出强类型 `IntentSpec`（目标表、查询列、谓词过滤、聚合函数、排序与条数限制）。
3. **语义审查：** `SemanticIntentGuard` 检查用户约束是否被遗漏，或者是否存在缺少数值标准的主观形容词。
4. **关系规划：** `IntentResolver` 解析外键依赖，在跨表引用时自动补全内连接路径，构建受检验的 MiniRel AST。
5. **编译与执行：** 将语法树编译为只读 `SELECT` 语句，并在带虚拟指令超时保护的只读后端中执行。
6. **结果呈现：** 格式化输出为排版整洁的 Markdown 表格或结构化 JSON。

---

## 5. 环境要求

- **操作系统：** Linux、macOS 或 Windows (WSL2)。
- **处理器：** 标准 x86_64 或 ARM64 CPU（推荐 4 物理核心以上）。
- **内存：** 最低 8 GB RAM（推荐 16 GB）。
- **磁盘空间：** 约 2 GB 可用空间（包含本地模型权重）。
- **Python：** Python $\ge 3.10$（在 Python 3.10 至 3.14 环境通过全量测试）。
- **核心依赖：** NumPy $\ge 1.24.0$（仅需纯 CPU 版本）。

---

## 6. 安装指南

### 第一步：安装 Ollama 并下载默认模型
Fei-Mini 通过 [Ollama](https://ollama.com/) 驱动本地 CPU 推理：
```bash
# 安装 Ollama (Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh

# 拉取默认 1.5B 翻译模型 (~986 MB)
ollama pull qwen2.5-coder:1.5b
```

### 第二步：安装 Fei-Mini 软件包
在项目代码仓库根目录下执行：
```bash
pip install -e .
```

### 第三步：运行 `feimini doctor` 检查环境就绪状态
```bash
feimini doctor
```
*期望输出：*
```
========================================================================
  Fei-Mini System & Environment Doctor
========================================================================
[1/6] Python Runtime: 3.14.9 (>= 3.10 required) -> OK
[2/6] SQLite Engine: v3.54.0 -> OK
[3/6] Total System RAM: 15.4 GB (>= 8 GB required) -> OK
[4/6] Ollama Server: Connected at http://127.0.0.1:11434/api/tags -> OK
[5/6] Configured Model: 'qwen2.5-coder:1.5b' installed -> OK
[6/6] Read-Only Security Boundary: 6 Defense-in-Depth Layers -> OK
========================================================================
  All system diagnostics passed! Fei-Mini is ready.
```

---

## 7. 快速上手与 CLI 示例

### 非交互式单次查询 (表格模式)
```bash
feimini query --db ./retail.db --question "查询所有在北京的客户姓名与账户余额"
```
*终端格式化输出：*
```
| id | name | city | balance | is_vip |
| --- | --- | --- | --- | --- |
| 1 | Alice Zhang | Beijing | 1200.0 | 1 |
| 3 | Charlie Wang | Beijing | 3200.0 | 1 |
```

### 跨表关联分析与聚合查询
```bash
feimini query --db ./retail.db --question "统计每位客户姓名的订单总金额"
```
*输出：*
```
| name | total_spend |
| --- | --- |
| Alice Zhang | 770.0 |
| Bob Li | 890.0 |
| Charlie Wang | 2230.0 |
```

### 结构化 JSON 模式 (`--format json`)
为脚本编写与下游工具集成提供机器可读输出：
```bash
feimini query --db ./retail.db --question "查看金额最高的前2笔订单" --format json
```
*标准输出 JSON：*
```json
{
  "question": "查看金额最高的前2笔订单",
  "success": true,
  "decision": "EXECUTE",
  "query_type": "DATABASE_QUERY",
  "sql": "SELECT * FROM (SELECT * FROM \"orders\") AS _t LIMIT ?",
  "row_count": 2,
  "rows": [
    [1001, 1, 450.0, "completed"],
    [1002, 1, 320.0, "completed"]
  ],
  "columns": ["order_id", "cust_id", "amount", "status"],
  "needs_clarification": false,
  "clarification_prompt": null,
  "is_unsupported": false,
  "unsupported_reason": null,
  "total_latency_ms": 3812.4
}
```

### 开发者调试模式 (`--debug`)
```bash
feimini query --db ./retail.db --question "查找北京的VIP客户" --debug
```
*将编译产出的真实参数化 SQL 与各阶段耗时输出至标准错误流 (stderr)，绝不破坏 stdout 的纯净结构。*

---

## 8. 交互式多轮会话澄清

当省略 `--question` 时，Fei-Mini 自动启动交互式终端：
```bash
feimini query --db ./retail_store.db
```
```
============================================================================
  Fei-Mini Interactive Database Assistant (Type 'exit' to quit, 'cancel' to reset)
  Connected Database: retail_store.db (Strict Read-Only)
============================================================================

User> 找出表现最好的客户。
Thinking locally on CPU...

[Fei-Mini 澄清提问]
  您希望按账户最高余额排序，还是按订单累计总金额排序？

Fei-Mini [Clarifying]> 按账户最高余额。
Thinking locally on CPU...

[验证后的查询结果 (2 行, 耗时 4120.3ms)]
  | name | balance |
  | --- | --- |
  | Charlie Wang | 3200.0 |
  | Alice Zhang | 1200.0 |
```

---

## 9. 安全机制与只读保障

Fei-Mini 在系统层设立了**六层独立的纵深防御体系**：
1. **只读 URI 连接：** 采用 `file:database.db?mode=ro` 建立 SQLite 句柄，在操作系统内核文件描述符层面拒绝排他写锁。
2. **引擎级配置锁定：** 连接建立后立即执行 `PRAGMA query_only = ON;`。
3. **SQLite C Authorizer 动作拦截：** 挂载严苛底层回调，阻断 `INSERT`、`UPDATE`、`DELETE`、`DROP_TABLE`、`ALTER_TABLE`、`ATTACH` 与 `PRAGMA` 指令。
4. **编译期参数化隔离：** 所有字面量统一编译为 `?` 绑定占位符，杜绝任何形式的 SQL 字符串拼接。
5. **指令级超时处理器：** 通过 `sqlite3.set_progress_handler` 每 1,000 条虚拟机字节码检测时钟，秒级中止恶意死循环或笛卡尔积爆炸。
6. **输出行数与内存硬上限：** 默认设置 `max_rows=1000` 与 `max_bytes=10MB` 截断保护。

*密码学验证：* 在覆盖 12 种攻击手法的对抗渗透测试中，目标数据库文件的 SHA-256 校验和在测试前后**完全保持一致 (0 字节变动)**，磁盘未产生任何临时 WAL 或回滚日志文件。

---

## 10. 性能基准与硬件实测

基于标配轻薄本 CPU（Intel Core i5-10210U @ 1.60GHz）在不同量级真实 SQLite 数据库上的耗时实测：

| 数据量规模 | 典型查询负载 | SQL 编译耗时 | SQLite 底层执行耗时 | 峰值常驻内存 |
| :--- | :--- | :--- | :--- | :--- |
| **100 行** | 索引过滤 (Filter) | 3.75 $\mu$s | 0.164 ms | ~403 MB |
| **1,000 行** | 跨表连接聚合 (Join-Agg) | 16.08 $\mu$s | 0.267 ms | ~403 MB |
| **10,000 行** | 跨表连接聚合 (Join-Agg) | 18.17 $\mu$s | 0.871 ms | ~403 MB |
| **100,000 行** | **复合连接分组排序截断** | **16.82 $\mu$s** | **7.677 ms** | **~403 MB** |

- **端到端耗时拆解：** 本地小模型 CPU 词元推理占总体时间的 $> 99.9\%$（单次提问约 $3.5\text{ 至 }4.5\text{ 秒}$）。而在确定性工程流水线中，Schema 检查、关系规划、SQL 编译与底层执行**合计耗时 $< 1.5\text{ 毫秒}$**。

---

## 11. 已知局限与客观实验数据

秉承 MiniXok 实验室“实事求是、严谨可复现”的核心准则，诚实公开当前系统的技术边界：

1. **严格只读边界：** 故意不支持任何涉及数据库修改的写操作 (`INSERT`, `UPDATE`, `DELETE`, `DROP`)。
2. **本地 CPU 推理延迟：** 基于 4 核心 CPU 运行 1.5B 级别语言模型需要 2.5 至 5.0 秒，无法达到纯 SQL 的毫秒级即时响应。
3. **真实留出基准测试表现 (基于 M6.1.3 独立盲测数据集)：**
   - **澄清查准率 (Clarification Precision)：** **92.31% 至 96.43%**（模型发起澄清提问时高度准确）。
   - **清晰请求特异度 (Specificity)：** **97.50% 至 100.00%**（清晰明确的问题几乎不会受到不必要的打扰）。
   - **歧义查全率边界 (Ambiguity Recall)：** 测得为 **64.00% (32 / 50)**。在约 36% 的模糊提问（如“随便看几条订单”或“总结客户情况”）中，1.5B 小模型倾向于退化为保守的宽表全量扫描，而非主动发起澄清。
   - **非清晰请求假正例率 (False Acceptance Rate)：** 测得为 **21.33% (16 / 75)**。
4. **软实时调度波动：** 非实时 Linux 系统的线程调度与垃圾回收存在约 1 至 2 毫秒的计时抖动。

---

## 12. 项目代码结构

```
src/feimini/
    cli.py                 # 主控制台命令行入口: feimini doctor, query, interactive session
    config.py              # 配置优先级管理 (CLI > ENV > 配置文件 > 默认配置)
    dsl/                   # MiniRel 强类型关系代数中间表示层
        types.py           # RelationSchema, Column, Table, DataType
        ast.py             # 9 种关系算子 AST 语法树定义与静态类型校验
        interpreter.py     # 确定性内存参考解释器执行引擎
        grammar.py         # 单一事实来源 MiniRelGrammar 语法规范
    sqlite/                # 工业级 SQLite 只读执行引擎
        schema.py          # SQLiteSchemaAdapter 与四级 TypeGuarantee 保障模型
        compiler.py        # MiniRelSQLCompiler (参数化 SELECT 查询编译器)
        backend.py         # SQLiteExecutionBackend (六层纵深防御安全执行器)
        retrieval.py       # BoundedValueRetriever (离散取值有界检索器)
        pipeline.py        # SQLiteAssistantPipeline (单调时钟截止时间传播体系)
    translator/            # 本地自然语言翻译子系统
        contract.py        # IntentSpec 与 IntentDecision 意图数据结构
        client.py          # LocalTranslatorClient (Ollama 语法约束客户端)
        resolver.py        # IntentResolver (意图到 MiniRel AST 的确定性规划器)
        semantic_guard.py  # SemanticIntentGuard (8 项确定性前置语义护栏)
        pipeline.py        # NaturalLanguageSQLiteAssistant 端到端管道
tests/                     # 全套自动化回归测试套件 (96 项测试)
    cli/                   # 软件包分发、全新环境安装、交互式多轮与 CLI 选项测试
    sqlite/                # 元数据、编译器、安全注入与全算子差分测试
    translator/            # 意图契约、模式校验与语义安全护栏测试
    dsl/                   # MiniRel 关系算子、类型系统与确定性解释器测试
```

---

## 13. 运行自动化测试

执行完整的 96 项自动化单元与集成测试：
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
```

执行端到端自动化冒烟测试脚本：
```bash
./scripts/smoke_test.sh
```

---

## 14. 研发历程与里程碑演进

Fei-Mini 经历了一系列严格受控的实证研究里程碑：
- **Experiment 001 (M0–M4.6)：** 探究学习型搜索策略是否能突破确定性组合爆炸。在实现 100% 语法覆盖率后，实证证明搜索引导对多步复合关系查询具有决定性的计算效率提升 ($p = 0.000004$)。
- **Milestone 5 (M5–M5.8)：** 对比 2 层神经网络 MLP 排序器与确定性符号启发式策略。实验证实无参数的确定性符号启发式在精度与推理延迟上全面超越神经网络 ($p < 10^{-8}$)，避免了特征计算的算力惩罚。
- **Milestone 6 (M6.0–M6.2.1)：** 构建了真实 SQLite 数据库执行后端、参数化 SQL 编译器、纯本地语法约束翻译器，并完成了独立虚拟环境的分发打包验证。

全套详细学术实验报告完整收录于 [`docs/`](docs/) 目录。

---

## 15. 未来演进路线 (Roadmap)

- [x] **v0.1.0：** 核心 MiniRel 引擎、六层只读 SQLite 执行体系、本地 Qwen2.5-Coder-1.5B 翻译与交互式终端 CLI。
- [ ] **v0.2.0：** 扩展关系代数算子（外连接 `OUTER JOIN`、嵌套子查询与 `IN` 集合成员判定）。
- [ ] **v0.3.0：** 基于 C 语言绑定的本地 GBNF 语法编译，将小模型 CPU 词元生成耗时压缩至 1 秒以内。
- [ ] **v0.4.0：** 拓展跨数据库支持（集成 PostgreSQL 与 DuckDB 只读适配器）。

---

## 16. 参与贡献

我们热忱欢迎开源社区的贡献与反馈！在提交 Pull Request 之前，请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md) 与 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。

---

## 17. 开源协议与开源模型鸣谢

- **开源协议：** 本项目采用 [Apache License 2.0](LICENSE) 授权。
- **开源模型鸣谢：** 本项目本地意图翻译引擎基于阿里云开源的 [`Qwen/Qwen2.5-Coder-1.5B-Instruct`](https://github.com/QwenLM/Qwen2.5-Coder) 模型驱动，采用 Apache-2.0 商业友好开源协议。
- **实验室信息：** 由独立开源人工智能实验室 **[MiniXok](https://minixok.pages.dev/)** 研发发布。联系邮箱：`xokmini@gmail.com` | X (Twitter)：`@Mini_Xok`。

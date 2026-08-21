# ReplyFlow Project Status

## 当前项目

ReplyFlow｜聚合站内信 AI 回复与动态演示工作台

## 当前阶段

阶段 6——模拟邮件接入和顶部聚合已完成；准备进入阶段 7

## 已完成

- 已创建独立项目目录 `work/reply-flow-agent`。
- 已创建 Python 3.11.9 虚拟环境 `.venv`。
- 已通过用户级 `uv` 管理 Python 3.11.9，保留原有系统 Python 3.13。
- 已确认 Python 内置 SQLite 可用。
- 已初始化独立 Git 仓库。
- 已创建 `.gitignore`、`.env.example`、`README.md` 和本状态文件。
- 已将 PRD、行动指南、AI 接手说明和新电脑恢复指南纳入仓库。
- 已创建 GitHub 私有仓库 `leiluo845/reply-flow-agent`，并将 `main` 分支推送到远程。
- 已完成阶段 1 范围冻结文档：
  - `docs/product_contract.md`
  - `docs/scenario_catalog.md`
  - `docs/state_catalog.md`
  - `docs/decision_log.md`
- 已准备阶段 2 离线 POC 材料：
  - `poc/coze/analyze_prompt.md`
  - `poc/coze/draft_prompt.md`
  - `poc/coze/workflow_spec.md`
  - `poc/coze/poc_cases.md`
  - `poc/coze/poc_results_template.md`
- 已完成模型编排层从 Dify 到 Coze 的文档迁移；Dify 仅保留在已废弃历史决策 ADR-004 和切换说明中，正式执行依据为 ADR-011。
- 已完成阶段 3 工程骨架：
  - `pyproject.toml`
  - `requirements.txt`
  - `pytest.ini`
  - `app.py`
  - `src/replyflow/__init__.py`
  - `src/replyflow/config.py`
  - `tests/test_config.py`
  - `tests/test_imports.py`
  - `tests/test_scope_guard.py`
  - `data/seed/.gitkeep`
  - `data/reply_basis/.gitkeep`
  - `evals/reports/.gitkeep`
- 已完成阶段 4 虚构种子数据和只读回复依据：
  - `data/seed/emails.json`
  - `data/seed/orders.json`
  - `data/seed/shipping_events.json`
  - `data/seed/tool_failures.json`
  - `data/seed/case_manifest.json`
  - `data/reply_basis/logistics_basis.md`
  - `data/reply_basis/returns_exchange_basis.md`
  - `data/reply_basis/damage_refund_basis.md`
  - `data/reply_basis/tone_basis.md`
  - `scripts/validate_seed_data.py`
  - `src/replyflow/seed_validation.py`
  - `tests/test_seed_data.py`
- 已完成阶段 5 SQLite 数据层和聚合模型：
  - `src/replyflow/models.py`：Pydantic 数据模型
  - `src/replyflow/db.py`：幂等建表、事务封装和种子初始化
  - `src/replyflow/repositories.py`：邮件、订单/物流、聚合会话、幂等和发件箱仓储
  - `scripts/init_db.py`：可重复执行的本地数据库初始化命令
  - `tests/test_db.py`、`tests/test_repositories.py`：表结构、种子幂等、事务回滚、聚合查询和 operation_id 测试
- 已完成阶段 6 模拟邮件接入和聚合：
  - `src/replyflow/ingestion.py`：正文校验、虚构默认值、接入状态流转和 source_message_id 幂等
  - `src/replyflow/aggregation.py`：买家消息边界识别、聚合会话创建、顶部会话查询和计数
  - `tests/test_ingestion.py`、`tests/test_aggregation.py`：买家、非买家、空正文、默认值、订单上下文和重复接入测试

## 本轮修改

- 新增 14 张 SQLite 表，覆盖邮件、聚合会话、订单、物流、回复依据、草稿、outbox、运行、Tool Trace、风险、确认、审计、幂等和评测结果。
- 新增 `scripts/init_db.py`；默认从虚构种子数据重建基础表，重复执行不会重复插入。
- 新增 `transaction()` 事务封装，异常时回滚本轮全部写入。
- 新增仓储层，提供原始邮件幂等接入、订单/物流查询、聚合会话查询与状态更新、operation_id 重放/冲突判断和 outbox 查询。
- 新增 Pydantic 模型，统一数据库边界数据结构。
- 更新 `README.md`、`START_HERE.md` 和本状态文件，明确阶段6已完成和阶段7入口。
- 本阶段未实现 Agent 分析、AI 回复、MCP Tools、页面或真实邮件同步。

## 测试结果

- 命令：`.venv\\Scripts\\python.exe --version`
- 结果：Python 3.11.9
- 命令：`.venv\\Scripts\\python.exe -c "import sqlite3; print(sqlite3.sqlite_version)"`
- 结果：SQLite 3.46.0
- 命令：`git --version`
- 结果：Git 2.55.0.windows.3
- 命令：`rg -n "Given|一级|二级|三级|演示控制台|禁止回退" docs`
- 结果：通过，阶段 1 文档包含核心场景、三级处理和禁止回退信息。
- 命令：`rg -n "主管审核|create_support_ticket|create_refund_review_request|政策文件夹" docs`
- 结果：仅在取消项、禁止行为或废弃方案说明中出现，未作为实现功能出现。
- 命令：`git diff --check`
- 结果：通过，无 Markdown 空白错误。
- 命令：检查 `poc/coze/*.md` 中 18 个 JSON 代码块可解析
- 结果：通过。
- 命令：`.venv\\Scripts\\python.exe -m pip install -r requirements.txt`
- 结果：通过，阶段 3 依赖已安装。
- 命令：`.venv\\Scripts\\python.exe -m pip install -e .`
- 结果：通过，本地包 `reply-flow-agent==0.3.0` 可导入。
- 命令：`.venv\\Scripts\\python.exe -m pytest -q`
- 结果：通过，26 passed。
- 命令：`.venv\\Scripts\\python.exe -c "import streamlit, pydantic, mcp, requests, dotenv, pytest; import replyflow; print('imports ok', replyflow.__version__)"`
- 结果：通过，输出 `imports ok 0.3.0`。
- 命令：`.venv\\Scripts\\python.exe -m streamlit run app.py --server.headless true --server.port 8506`
- 结果：通过，Streamlit 启动并输出 `Local URL: http://localhost:8506`；验证后已停止进程。
- 命令：`python scripts/validate_seed_data.py`
- 结果：通过，`Seed data validation passed.`，emails=30、orders=20、shipping_events=52、basis_docs=4、cases=30、r2_cases=13。
- 命令：`.venv\\Scripts\\python.exe scripts\\init_db.py --db data\\local\\stage5_smoke.sqlite3`（连续执行两次）
- 结果：通过，两次均输出 emails=30、orders=20、shipping_events=52、reply_basis=16；数据库文件被 `.gitignore` 忽略。

## 已知问题

- 当前 Codex/PowerShell 环境未在扣子工作台创建 Workflow；实际运行可由用户在浏览器登录后完成，也可以后置到阶段 11 前后。
- 尚未产生阶段 2 必需的 8 条真实 Coze 运行记录；不得手工伪造 `poc_results.md`。
- 需要用户在可联网浏览器登录/注册扣子后，才能产生真实 POC 运行记录；未登录期间可继续本地 Demo Mode。
- 阶段 6 只完成本地模拟接入和聚合；MCP Tools、Agent 处理和页面仍未实现。
- Git 身份仅在本项目内配置为 GitHub 账号 `leiluo845`，不修改全局 Git 配置。
- 当前电脑的 remote 使用 SSH deploy key 推送；换电脑时按 `docs/NEW_COMPUTER_SETUP.md` 重新登录或配置新 key。

## 下一步

- 继续阶段 7：实现 8 个 MCP Tools；仍只写本地 SQLite，不需要登录 Coze。
- 阶段 7 复用本阶段的接入、聚合和仓储逻辑，Tool 层必须保持确认、幂等和真实外部写入隔离。
- Coze 登录、真实 Workflow 创建、8 条运行记录和 API 联调继续后置到阶段 11 前后；在真实记录完成前不得声称 Coze POC 已通过。

## 最后更新时间

2026-08-21

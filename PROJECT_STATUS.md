# ReplyFlow Project Status

## 当前项目

ReplyFlow｜聚合站内信 AI 回复与动态演示工作台

## 当前阶段

阶段 3——工程骨架已完成；Coze 真实 POC 仍后置

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

## 本轮修改

- 新增 Python 包结构 `src/replyflow`，当前只包含可测试配置加载，不包含业务流程。
- 新增 `app.py` 最小 Streamlit 页面，展示顶部聚合站内信定位、演示控制台入口、Demo/Interactive 模式说明和未实现提示。
- 新增 `requirements.txt` 和 `pyproject.toml`，依赖限定为 Streamlit、Pydantic 2、MCP、python-dotenv、requests、pytest。
- 新增 import/config/scope guard 测试，确保未引入取消项、FastAPI、LangGraph、Docker 或真实外部写入。
- 安装当前阶段依赖，并将本地包以 editable 方式安装到 `.venv`。
- 更新 `.gitignore`，忽略 editable 安装生成的 `*.egg-info/` 本地元数据。
- 更新 `README.md`、`START_HERE.md`、`docs/NEW_COMPUTER_SETUP.md` 和本状态文件。
- 未创建邮件接入、种子数据、SQLite 表、MCP Tools、Agent 状态机或 Coze API 调用。

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
- 结果：通过，5 passed。
- 命令：`.venv\\Scripts\\python.exe -c "import streamlit, pydantic, mcp, requests, dotenv, pytest; import replyflow; print('imports ok', replyflow.__version__)"`
- 结果：通过，输出 `imports ok 0.3.0`。
- 命令：`.venv\\Scripts\\python.exe -m streamlit run app.py --server.headless true --server.port 8506`
- 结果：通过，Streamlit 启动并输出 `Local URL: http://localhost:8506`；验证后已停止进程。

## 已知问题

- 当前 Codex/PowerShell 环境未在扣子工作台创建 Workflow；实际运行可由用户在浏览器登录后完成，也可以后置到阶段 11 前后。
- 尚未产生阶段 2 必需的 8 条真实 Coze 运行记录；不得手工伪造 `poc_results.md`。
- 需要用户在可联网浏览器登录/注册扣子后，才能产生真实 POC 运行记录；未登录期间可继续本地 Demo Mode。
- 阶段 3 只完成工程骨架，页面仍是未实现提示；真实邮件接入、数据库和 Agent 处理从阶段 4 以后逐步实现。
- Git 身份仅在本项目内配置为 GitHub 账号 `leiluo845`，不修改全局 Git 配置。
- 当前电脑的 remote 使用 SSH deploy key 推送；换电脑时按 `docs/NEW_COMPUTER_SETUP.md` 重新登录或配置新 key。

## 下一步

- 继续阶段 4：创建全虚构种子数据和只读回复依据。
- 阶段 4 不需要登录 Coze，不连接真实 Amazon、邮箱、订单或物流接口。
- Coze 登录、真实 Workflow 创建、8 条运行记录和 API 联调继续后置到阶段 11 前后；在真实记录完成前不得声称 Coze POC 已通过。

## 最后更新时间

2026-08-21

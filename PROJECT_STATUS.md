# ReplyFlow Project Status

## 当前项目

ReplyFlow｜聚合站内信 AI 回复与动态演示工作台

## 当前阶段

阶段 11——Coze Interactive 本地客户端与编排已完成；等待用户创建/发布真实 Workflow 后联调

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
- 已完成阶段 7 MCP Tools：
  - `src/replyflow/mcp_tools.py`：8 个带 Pydantic 输入/输出、错误码、Trace 和幂等控制的 Tool
  - `src/replyflow/mcp_server.py`：FastMCP 注册入口，注册数量严格为 8 个
  - 扩展 `src/replyflow/repositories.py`：依据、草稿、outbox、运行、Trace 和审计仓储
  - `tests/test_mcp_tools.py`：Tool 列表、事实查询、无结果、输入错误、确认门槛、重复执行、冲突和 outbox 测试
- 已完成阶段 8 Skills 和只读回复依据检索：
  - `skills/email_triage.md`、`skills/reply_drafting.md`、`skills/risk_routing.md`：3 个可版本化 Skill
  - `src/replyflow/skill_loader.py`：Skill 元数据、版本、重复名称和 Tool 引用校验
  - `src/replyflow/reply_basis_search.py`：只读依据检索、评分、无命中和多版本冲突响应
  - `tests/test_skills.py`、`tests/test_reply_basis.py`：Skill/依据的正常、缺失、错误 Tool、无命中和冲突测试
- 已完成阶段 9 风险网关与三级路由：
  - `src/replyflow/risk_gateway.py`：R0-R3 风险、L1-L3 处理级别、允许/阻断动作和核对清单
  - `tests/test_risk_gateway.py`：白名单、缺订单号、退款/拒付、投诉/法律、提示注入、Tool/事实/依据冲突、低置信度、草稿承诺和模型降级尝试测试
- 已完成阶段 10 Demo Mode 与状态机：
  - `src/replyflow/state_machine.py`：邮件、Agent、草稿、模拟发送的合法状态流转
  - `src/replyflow/demo_router.py`：有限、可解释的 Demo Mode 分析和英文草稿规则
  - `src/replyflow/orchestrator.py`：真实串联接入、8 个本地 Tool、Skill 版本、依据检索、风险网关、草稿和本地 outbox
  - `src/replyflow/audit.py`：状态变化审计
  - `tests/test_state_machine.py`、`tests/test_demo_orchestrator.py`：三类预置场景、重复接入、超范围输入、Tool 故障和非法状态测试
- 已完成阶段 11 的本地代码部分：
  - `src/replyflow/coze_client.py`：Coze Workflow HTTP 客户端、Analyze/Draft Schema、响应提取和错误码
  - `src/replyflow/interactive_orchestrator.py`：Coze 分析/草稿与本地事实、依据、风险、确认和 outbox 的混合编排
  - `tests/test_coze_client.py`、`tests/test_interactive_orchestrator.py`：未配置、请求构造、响应解析、401/403/429/超时/非 JSON/Schema 错误、L1/L3 和模型失败降级测试

## 本轮修改

- 新增 `email_triage`、`reply_drafting`、`risk_routing` 三个 Skill，均定义触发/不触发、输入输出、步骤、可用 Tools、禁止事项、升级条件和示例。
- 新增 Skill Loader：校验 JSON 元数据、MAJOR.MINOR 版本、重复 Skill 名和已注册 Tool 引用。
- 新增只读依据检索：返回依据与章节 ID、原文片段、分数和版本；无命中返回 `NO_HIT`，同章节多版本冲突返回 `CONFLICT`。
- MCP 的 `search_reply_basis` 已接入结构化检索；缺少依据返回 `BASIS_NOT_FOUND`，不会凭常识补全。
- 未创建上传、编辑、发布、文件夹或管理页面；真实 Coze Workflow 尚未创建，Interactive Mode 尚未进行联网运行；本地仍无真实外部写接口。

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
- 结果：通过，81 passed（FastMCP 导入产生 1 条依赖警告，不影响测试）。
- 命令：`.venv\\Scripts\\python.exe -c "import streamlit, pydantic, mcp, requests, dotenv, pytest; import replyflow; print('imports ok', replyflow.__version__)"`
- 结果：通过，输出 `imports ok 0.3.0`。
- 命令：`.venv\\Scripts\\python.exe -m streamlit run app.py --server.headless true --server.port 8506`
- 结果：通过，Streamlit 启动并输出 `Local URL: http://localhost:8506`；验证后已停止进程。
- 命令：`python scripts/validate_seed_data.py`
- 结果：通过，`Seed data validation passed.`，emails=30、orders=20、shipping_events=52、basis_docs=4、cases=30、r2_cases=13。
- 命令：`.venv\\Scripts\\python.exe scripts\\init_db.py --db data\\local\\stage5_smoke.sqlite3`（连续执行两次）
- 结果：通过，两次均输出 emails=30、orders=20、shipping_events=52、reply_basis=16；数据库文件被 `.gitignore` 忽略。
- 命令：`.venv\\Scripts\\python.exe -m pytest tests\\test_mcp_tools.py -q`
- 结果：通过，4 passed；FastMCP 列表恰好为 `ingest_simulated_email`、`get_email`、`find_order`、`get_shipping_status`、`search_reply_basis`、`get_reply_tone`、`save_reply_draft`、`send_simulated_reply`。
- 命令：`.venv\\Scripts\\python.exe -m pytest tests\\test_skills.py tests\\test_reply_basis.py -q`
- 结果：通过，7 passed；覆盖 3 个 Skill、错误 Tool、缺版本、无命中和依据冲突。
- 命令：`.venv\\Scripts\\python.exe -m pytest tests\\test_risk_gateway.py -q`
- 结果：通过，21 passed；高风险召回、白名单边界、组合规则、草稿二次扫描和模型降级阻断均通过。
- 命令：`.venv\\Scripts\\python.exe -m pytest tests\\test_state_machine.py tests\\test_demo_orchestrator.py -q`
- 结果：通过，8 passed；物流 L1、缺订单号 L2、退款拒付 L3、超范围提示、Tool 故障升级、重复接入和非法状态均通过。
- 命令：`.venv\\Scripts\\python.exe -m pytest tests\\test_coze_client.py tests\\test_interactive_orchestrator.py -q`
- 结果：通过，15 passed；未配置 Coze 不发网络请求，mock 响应和错误均结构化处理，Interactive 业务控制仍由本地风险网关和 Tools 负责。

## 已知问题

- 当前 Codex/PowerShell 环境未在扣子工作台创建 Workflow；实际运行可由用户在浏览器登录后完成，也可以后置到阶段 11 前后。
- 尚未产生阶段 2 必需的 8 条真实 Coze 运行记录；不得手工伪造 `poc_results.md`。
- 需要用户在可联网浏览器登录/注册扣子后，才能产生真实 POC 运行记录；未登录期间可继续本地 Demo Mode。
- 阶段 11 本地代码已完成；真实 Coze 联调和 Streamlit 页面仍未完成。
- Git 身份仅在本项目内配置为 GitHub 账号 `leiluo845`，不修改全局 Git 配置。
- 当前电脑的 remote 使用 SSH deploy key 推送；换电脑时按 `docs/NEW_COMPUTER_SETUP.md` 重新登录或配置新 key。

## 下一步

- 下一步需要用户登录扣子并创建/发布 `ReplyFlow POC` Workflow，记录 Workflow ID 和可选版本；之后再在本机 `.env` 填入 PAT/ID，运行真实 8 条 POC 案例。
- 阶段 11 的 Coze 只能分析和草拟，事实、风险、确认、幂等和发送仍由本地控制层负责；在真实运行记录产生前，不得声称 Interactive POC 已通过。
- Coze 登录、真实 Workflow 创建、8 条运行记录和 API 联调继续后置到阶段 11 前后；在真实记录完成前不得声称 Coze POC 已通过。

## 最后更新时间

2026-08-21

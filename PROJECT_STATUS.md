# ReplyFlow Project Status

## 当前项目

ReplyFlow｜聚合站内信 AI 回复与动态演示工作台

## 当前阶段

阶段 14（30+ 条离线评测与 Go/Conditional Go/No-Go）已完成：在阶段 13 端到端控制验证基础上，完成 Demo/Interactive 独立评测、13 条 R2 高风险案例、指标切片、控制验证和可追溯报告。当前 Demo 与 Interactive 均按安全门槛诚实判定为 No-Go；阶段 B 页面、服务和 GitHub 备份保持可用。

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
- 已完成阶段 11 本地真实 API 联调：`.env` 已由用户在本机配置，Analyze 与 Draft 均通过已发布 Workflow 返回结构化结果；修正请求体为 `parameters.payload_json`，与扣子开始节点契约一致。
- 已完成阶段 2 八案例真实运行：`scripts/run_coze_poc.py` 生成 `poc/coze/poc_results.jsonl`；P01 超时后重试成功，P06 首次意图漂移后通过本地枚举收紧并重跑；结果与失败分析写入 `poc/coze/poc_results.md`。
- 已将 `AnalyzeOutput.intent` 收紧为 11 个允许枚举，未知意图会返回 `MODEL_OUTPUT_INVALID`，不会进入风险路由。
- 已完成阶段 12 Streamlit 动态工作台：参考亚马逊客服邮件原型完成店铺/状态/搜索工具栏、文件夹栏、聚合会话列表、邮件详情和右侧订单信息栏；右下角浮动按钮打开模拟邮件浮窗，支持订单候选、订单摘要、模拟接收和仅接收不处理；顶部聚合、原始收件箱、本地发件箱、L1/L2/L3 展示、风险与 Tool Trace 折叠栏、二次确认和三级核对清单保持可用。
- 已完成阶段 12 UI 幂等和纯函数测试：稳定 `source_message_id` 防重复接入，二级/三级发送按钮按状态和清单控制。
- 已完成阶段 13 页面重构：以原 HTML 邮件工作台为骨架，复刻深色 OMS 导航、顶部工具栏占位、邮箱树、会话列表、邮件详情和订单侧栏；除智能客服开关、模拟邮件台和回复操作外，其余区域只做展示。
- 已完成阶段 13 Agent 交互：关闭智能客服时模拟邮件只接收不调用 Coze；开启后自动调用 Coze，L1 自动回复、L2 草稿待确认、L3 高风险核对；Coze 失败直接显示 AI 处理失败，不回退 Demo Router。
- 已补充 AI 失败重试：FAILED 会话显示“重试 AI”，开启智能客服后可重新调用 Coze；失败会话允许新 interactive task，但 source_message_id、邮件记录和 outbox 仍保持幂等。
- 新增页面规范 `docs/ui_prototype_spec.md`，规定原 HTML 骨架、交互边界、风险标签、订单摘要和 Streamlit + CSS/局部 HTML 实现约束。
- 已完成阶段 A 静态基线：复制原 HTML 到 `prototype/stage_a/amazon_mail_stage_a.html`，冻结无关控件为静态展示；保留会话切换、订单联动、回复输入和滚动。
- 已生成阶段 A 标注版 `prototype/stage_a/amazon_mail_stage_a-标注版.html`、标注数据 `prototype/stage_a/annotations.json` 和交互范围文档 `docs/stage_a_interaction_scope.md`。
- 已创建阶段 B HTML 增量页面 `prototype/stage_b/index.html` 和本地桥接服务 `stage_b_server.py`。
- 阶段 B 全局开关开启前显示待处理数量；批量任务显示进度、当前序号和 L1/L2/L3/失败计数。
- 阶段 B 开关开启时新邮件自动入队；关闭后不启动排队中的新邮件，当前已开始任务允许完成。
- 阶段 B 动态模拟邮件写入本地 SQLite，服务重启可恢复；新增 `stage_b_cases` 和 `stage_b_rollback_events` 表。
- 阶段 B 增加演示撤回：只允许撤回最近已完成批次，批次处理中禁用，回退本地草稿/模拟发件箱/线程状态并保留回退记录。
- 阶段 13 端到端控制验证：新增 `tests/test_reply_flow_e2e.py`，覆盖 L1 自动发送、L2 确认与编辑稿、L3 核对清单、重复发送幂等、payload 冲突、Tool/Coze 失败升级和重试。
- `send_simulated_reply` 新增可选 `checklist` 输入；当线程为 L3 时，Tool 层读取最新本地风险决策并强制校验所有必填核对项，返回 `CHECKLIST_REQUIRED` 时不写入 outbox。
- 阶段 14 离线评测：新增 `evals/run_eval.py`、`evals/README.md`、`tests/test_eval_metrics.py`，复用 30 条案例（13 条 R2），输出 Demo/Interactive JSON 与 Markdown 报告、指标切片、trace_ref 和自动 Go/Conditional Go/No-Go。

## 本轮修改

- 新增 `email_triage`、`reply_drafting`、`risk_routing` 三个 Skill，均定义触发/不触发、输入输出、步骤、可用 Tools、禁止事项、升级条件和示例。
- 新增 Skill Loader：校验 JSON 元数据、MAJOR.MINOR 版本、重复 Skill 名和已注册 Tool 引用。
- 新增只读依据检索：返回依据与章节 ID、原文片段、分数和版本；无命中返回 `NO_HIT`，同章节多版本冲突返回 `CONFLICT`。
- MCP 的 `search_reply_basis` 已接入结构化检索；缺少依据返回 `BASIS_NOT_FOUND`，不会凭常识补全。
- 已在 Coze 国内工作区创建并发布 `ReplyFlow_POC`（页面显示名 `ReplyFlow_POC`，Workflow ID `7677420616827928610`，版本 `v0.0.1`）。
- 已用虚构物流咨询完成一次 Coze 真实试运行：输出 `shipping_status`、`ORD-1001`、`confidence=1.0`，并验证动态输入从开始节点传入大模型节点。
- Coze 只负责 Analyze/Draft；本地仍负责事实、风险、确认、幂等、审计和模拟发件箱，无真实外部写接口。

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
- 结果：通过，82 passed（FastMCP 导入产生 1 条依赖警告，不影响测试）。
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
- 结果：通过，17 passed；未配置 Coze 不发网络请求，mock 响应和错误均结构化处理，未知 intent 会被阻断，Interactive 业务控制仍由本地风险网关和 Tools 负责。
- 命令：`.venv\\Scripts\\python.exe scripts\\run_coze_poc.py`
- 结果：真实调用 8 条案例，首次运行 `schema_valid=7`、`failed=1`（P01 超时）；P01 重试和 P06 枚举收紧后的重跑记录见 `poc/coze/poc_results_retry.jsonl`。
- 命令：`.venv\\Scripts\\python.exe -m pytest -q`
- 结果：通过，`87 passed`；包含 UI helper、Coze、风险网关和全部既有测试。
- 命令：`.venv\\Scripts\\python.exe -m streamlit run app.py --server.headless true --server.port 8506`
- 结果：通过，浏览器访问 `http://localhost:8506`；已验收一级自动回复、二级确认、三级核对、重复点击幂等和本地模拟发件箱计数变化。
- 命令：`.venv\\Scripts\\python.exe -m pytest -q`
- 结果：通过，`91 passed`；包含 Coze 失败重试、阶段 B 全局批处理持久化、队列关闭和演示撤回回退测试。
- 命令：`.venv\\Scripts\\python.exe -m pytest tests\\test_reply_flow_e2e.py -q`
- 结果：通过，`6 passed`；验证 L1/L2/L3 端到端控制、Tool 层确认与核对门槛、AI/人工/最终稿边界、幂等、失败升级和 trace/audit。
- 命令：`.venv\\Scripts\\python.exe -m pytest -q`
- 结果：通过，`97 passed`（FastMCP 依赖产生 1 条既有警告，不影响测试）。
- 命令：`.venv\\Scripts\\python.exe evals\\run_eval.py --mode demo`
- 结果：30 条案例完成运行；Demo 当前为 `No-Go`，高风险召回 61.5%，未授权承诺和无依据事实违规均为 0；详细结果见 `evals/reports/eval_demo.md` 和 `.json`。
- 命令：`.venv\\Scripts\\python.exe evals\\run_eval.py --mode interactive`
- 结果：30 条案例均被 Coze 结构化处理；当前工作区额度不足导致模型调用失败，自动判定 `No-Go`，详细错误和 trace_ref 见 `evals/reports/eval_interactive.md` 和 `.json`。
- 浏览器验收：桌面视口下原 HTML 邮件工作台骨架、智能客服开关、模拟邮件台、订单侧栏和 Coze 失败提示通过；关闭开关不调用 AI，开启后失败不回退本地规则。
- 阶段 A 浏览器验收：`http://127.0.0.1:8510/amazon_mail_stage_a.html` 加载成功；点击会话可切换详情和订单匹配状态；回复输入框可编辑；筛选、文件夹、订单操作、外链等控件无状态变化。
- 阶段 B 服务端单元验收：动态模拟邮件持久化、订单联动、开关关闭清空排队任务、运行中批次禁止撤回、已完成批次回退留痕测试通过。
- 阶段 B 浏览器验收：页面默认关闭智能客服；打开后显示批处理进度、L1/L2/L3/失败计数；新邮件自动入队；批次完成后展示演示撤回按钮；右侧订单和邮件详情随会话同步。
- 命令：使用本机 `.env` 调用 `CozeClient.analyze(...)`（虚构物流邮件）
- 结果：通过，`is_buyer_message=true`、`intent=shipping_status`、`order_id=ORD-1001`、`confidence=1.0`。
- 命令：使用本机 `.env` 调用 `CozeClient.draft(...)`（虚构订单与物流事实）
- 结果：通过，返回 `draft_subject`、`draft_body`、`used_basis`、`uncertainties` 四个结构化字段；未执行外部发送。

## 已知问题

- 尚未完成 8 条案例的完整 Coze 运行记录、Run ID、人工评分和失败分析；不得手工伪造 `poc_results.md`。
- Interactive Mode 已接入同一页面，但现场调用 Coze 可能受网络/额度影响；失败时页面显示错误并保留 Demo Mode 兜底。
- P05 草稿曾出现输入依据之外的“as required by our policies”表述；本地风险网关已增加 `R2_DRAFT_UNSUPPORTED_POLICY_ASSERTION` 规则并通过测试，历史评测仍按警告记录。
- Git 身份仅在本项目内配置为 GitHub 账号 `leiluo845`，不修改全局 Git 配置。
- 当前电脑的 remote 使用 SSH deploy key 推送；换电脑时按 `docs/NEW_COMPUTER_SETUP.md` 重新登录或配置新 key。

## 下一步

- 阶段 14 已完成；下一阶段为阶段 15：ROI 敏感性分析。若重新获得 Coze 额度，可重跑 Interactive 评测，不改动案例标注和安全门槛。
- `.env` 和 Coze PAT 继续只保留在本机。
- 阶段 11 的 Coze 只能分析和草拟，事实、风险、确认、幂等和发送仍由本地控制层负责；8 条案例评测完成前，不得声称完整 Interactive POC 已通过。
- 8 条运行记录完成前，只能声称“Coze 连通性试运行通过”，不能声称完整 Coze POC 评测通过。

## 最后更新时间

2026-08-26

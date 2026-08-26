# ReplyFlow 项目行动指南 v2.1

> 本指南用于让技术背景较弱的产品经理和没有聊天上下文的 AI，按正确顺序完成 ReplyFlow。产品定义以 [ReplyFlow高风险售后Agent_PRD.md](./ReplyFlow高风险售后Agent_PRD.md) 为准。

## 1. 开始前必须形成的共同认知

### 1.1 最终产品

ReplyFlow 不是独立聊天机器人，也不是第二套客服系统。它是搭载在邮件系统“顶部聚合站内信”里的 AI 回复能力。

动态演示从页面底部的“模拟邮件台”浮动按钮开始：点击后打开浮窗，用户可以输入一行英文邮件并选择虚构订单查看摘要，再点击“模拟收到邮件”；系统将它真实写入 SQLite 原始收件箱，创建顶部聚合会话，然后由单 Agent 分析、查询订单和物流、检索内部回复依据、判断处理级别并生成或执行模拟回复。

### 1.2 唯一业务角色与三档处理

唯一业务角色是店管：

- 一级·自动处理：白名单低风险邮件自动生成并写入本地模拟发件箱；
- 二级·人工确认：点击“AI回复”，草稿进入输入框，店管编辑/确认后发送；
- 三级·高风险核对：点击“生成参考回复”，完成核对清单和二次确认后才能发送。

所有“发送”只写入本地 outbox。

### 1.3 禁止回退清单

任何 AI 都不得自行恢复以下内容：

```text
客服主管、管理员、多角色权限、主管审核队列、工单、退款审核请求、
亚马逊政策邮件识别、政策文件夹、政策上传/发布/版本治理、
真实 Amazon/邮箱/支付接口、真实发送、真实退款、订单修改、多 Agent。
```

项目允许保留少量虚构内部回复依据文件，但它们只读、不可管理，不是政策产品功能。

### 1.4 技术路线

- Python 3.11；
- Streamlit；
- SQLite；
- Pydantic 2；
- MCP Python SDK / FastMCP；
- Coze Workflow（由页面“智能客服”开关控制）；
- Python 简单状态机；
- pytest；
- JSONL 离线评测。

第一版不使用 FastAPI、LangGraph、复杂向量数据库、Docker、Multi-Agent 或前端框架。

## 2. 工作方式

### 2.1 每次只做一个阶段

每次让 AI 开发前都先粘贴：

```text
请先完整阅读：
1. outputs/ReplyFlow高风险售后Agent_PRD.md
2. outputs/ReplyFlow项目行动指南.md
3. work/reply-flow-agent/PROJECT_STATUS.md（如已存在）

先用不超过10行复述：产品搭载位置、唯一用户、三级处理、模拟邮件浮窗、取消项和本轮范围。
如果你的复述包含主管、工单、退款审核或政策管理，请停止，不要修改文件。
```

AI 每阶段结束必须给出：修改文件、命令、测试结果、人工验收、已知问题和下一阶段。

每个阶段完成后必须提交并推送到 GitHub。只有 `git status --short --branch` 显示本地分支与 `origin/main` 对齐，且远程 `main` 能看到本阶段最新提交，才算该阶段真正完成。若提交成功但推送失败，本阶段只能标记为“本地完成、跨设备备份未完成”，必须继续重试推送或明确记录网络阻塞原因。

### 2.2 报错反馈模板

```text
我正在执行 ReplyFlow 行动指南的阶段 X。
完整命令：
[粘贴]

完整报错：
[粘贴]

请先定位根因，只修当前阶段相关文件，补回归测试。不要进入下一阶段，不要新增框架。
```

### 2.3 推荐目录

```text
work/reply-flow-agent/
├─ app.py
├─ src/replyflow/
│  ├─ config.py
│  ├─ models.py
│  ├─ db.py
│  ├─ repositories.py
│  ├─ ingestion.py
│  ├─ aggregation.py
│  ├─ mcp_server.py
│  ├─ mcp_client.py
│  ├─ skill_loader.py
│  ├─ demo_router.py
│  ├─ coze_client.py
│  ├─ risk_gateway.py
│  ├─ state_machine.py
│  ├─ orchestrator.py
│  └─ audit.py
├─ skills/
├─ data/seed/
├─ data/reply_basis/
├─ evals/reports/
├─ tests/
├─ docs/
├─ poc/coze/
├─ .env.example
├─ requirements.txt
├─ README.md
└─ PROJECT_STATUS.md
```

---

## 阶段 0：环境与独立 Git 仓库

**目标**：建立 Python 3.11 虚拟环境和独立项目仓库。

**工具**：PowerShell、Python 3.11、Git、AI 编程工具。

**操作**：

```powershell
Set-Location 'C:\Users\Administrator\Documents\Codex\2026-08-18\new-chat'
New-Item -ItemType Directory -Force 'work\reply-flow-agent'
Set-Location 'work\reply-flow-agent'
git init
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python --version
git --version
```

**AI 提示词**：

```text
本轮只做阶段0。创建 .gitignore、.env.example、README.md 和 PROJECT_STATUS.md。
.gitignore 必须排除 .venv、.env、__pycache__、pytest 缓存、本地数据库、日志和临时评测结果。
README 只写项目一句话定位和当前未实现状态。
PROJECT_STATUS 记录当前阶段、完成项、测试、已知问题、下一步和时间。
不要安装框架，不生成业务代码。
```

**验收**：`.venv` 和 `.env` 不出现在 `git status`；Python 为 3.11.x。

**完成定义**：项目目录可独立版本管理，不影响 workspace 其他文档。

**Git**：

```powershell
git add .gitignore .env.example README.md PROJECT_STATUS.md
git commit -m "chore: initialize ReplyFlow project"
git push origin main
```

**常见失败**：PowerShell 禁止激活时仅执行当前进程的 ExecutionPolicy；不要关闭系统安全设置。

---

## 阶段 1：冻结场景、取消项和状态

**目标**：把 PRD 转为可开发场景，防止后续 AI 按旧版方案扩展。

**输入**：PRD 第 1、7、8、9、18、19 节。

**AI 提示词**：

```text
本轮只做阶段1，不写Python代码。
创建：
- docs/product_contract.md：完整记录搭载位置、店管单角色、三级处理、模拟邮件浮窗、取消项；
- docs/scenario_catalog.md：至少20个Given/When/Then场景；
- docs/state_catalog.md：邮件接入、聚合、Agent处理和发送状态；
- docs/decision_log.md：记录混合架构、全虚构数据、无真实外部写入。

场景必须覆盖：一级物流、二级尺码、三级退款/拒付、缺订单号、订单不存在、工具失败、回复依据缺失、提示注入、重复发送和自由输入超出Demo范围。
每个场景写期望Tools、AI处理级别、风险等级、终态、按钮和禁止行为。
全文不得出现主管审核、工单、退款审核、政策文件夹或政策治理实现。
```

**命令**：

```powershell
rg -n "Given|一级|二级|三级|演示控制台|禁止回退" docs
rg -n "主管审核|create_support_ticket|create_refund_review_request|政策文件夹" docs
git diff --check
```

第二条搜索应无匹配，除非出现在“禁止项”说明中。

**人工验收**：随机抽查 5 个场景，能够明确邮件如何进入、调用什么、显示什么按钮、是否能发送。

**完成定义**：新 AI 只读四份 docs 即可复述正确产品模型。

**Git**：`git add docs PROJECT_STATUS.md; git commit -m "docs: freeze embedded ReplyFlow scope"; git push origin main`

**常见失败**：AI 把三级解释成主管审批时，停止本阶段并按 PRD 第 7.4 节改为店管核对。

---

## 阶段 2：Coze 最小 POC（可后置实际登录）

**目标**：验证自由英文邮件的意图/实体结构化输出和英文草稿生成，不做政策邮件功能。

**输入**：8 条 POC 邮件、内部虚构回复依据草稿。

**工具**：Markdown；实际搭建时使用扣子（Coze）工作台和浏览器。

**后置策略**：本阶段可以先只完成 `poc/coze/` 下的离线 Prompt、输入输出 Schema、Workflow 规格和案例，不要求立即登录 Coze。阶段 3-10 的本地 Demo Mode 可以先完成；真实 Coze 工作流、8 条运行记录和 API 联调统一在阶段 11 前后完成。未登录时不得把阶段 2 标记为“真实 POC 已通过”。

**AI 提示词**：

```text
本轮只准备Coze最小POC，不写正式业务代码。
创建 poc/coze/analyze_prompt.md、draft_prompt.md、workflow_spec.md、poc_cases.md、poc_results_template.md。

Analyze 输入 subject/body/order_context_id，输出：is_buyer_message、intent、order_id、missing_fields、confidence。
Draft 输入 email、verified_facts_json、reply_basis_json、risk_context_json，输出：draft_subject、draft_body、used_basis、uncertainties。

订单/物流事实只允许使用 verified_facts_json。不得承诺退款、赔偿、金额或确定时限。不得定义主管、工单、退款审核和政策管理流程。
```

**实际登录 Coze 后的操作**：

1. 新建 Workflow `ReplyFlow POC`。
2. 建立 `analyze` 和 `draft` 两个 task_type 分支。
3. Analyze LLM 节点输出严格 JSON。
4. Draft LLM 节点接收已经验证的事实和只读回复依据。
5. 用 8 条案例运行并记录结果。
6. 发布工作流，记录 Workflow ID、工作区/区域、发布时间和版本；如果平台支持导出或复制工作流配置，再保存到 `poc/coze/`。

本 POC 不需要建立用户可见知识库管理页面。若使用 Coze Knowledge，只上传固定的虚构回复依据并记录版本。

**验收**：缺订单号不猜测；退款/拒付不直接承诺；输出可被 Pydantic 解析。

**完成定义**：有 8 条真实 POC 运行记录和失败分析，不只是流程图。

**当前验收记录（2026-08-24）**：已完成 8 条真实案例运行并保存 Run ID；P01 首次超时后重试成功，P06 首次意图漂移后通过本地 11 值枚举校验并重跑成功，P05 留有依据外断言警告。详细结果见 `poc/coze/poc_results.md`、`poc_results.jsonl` 和 `poc_results_retry.jsonl`。因此可以进入 UI 开发，但不能把 P05 描述为“无缺陷通过”。

**Git**：离线材料完成时提交 `docs: prepare Coze POC contract`；真实运行记录完成时再提交 `docs: validate Coze analysis and drafting POC`。两次提交都必须 `git push origin main`。

**常见失败**：Coze 输出夹杂解释文字时，使用结构化输出或加强 JSON 约束；不要手工改结果冒充成功。

---

## 阶段 3：工程骨架

**目标**：建立可安装、可测试、可启动的最小 Streamlit 工程。

**AI 提示词**：

```text
本轮只搭工程骨架。
依赖限定为 Streamlit、Pydantic 2、MCP Python SDK/FastMCP、python-dotenv、requests、pytest。
创建 src/replyflow 包、app.py、tests 和目录结构。
app.py 只显示：个人作品、模拟数据、顶部聚合站内信定位、Demo/Interactive模式和未实现提示。
不要创建审核队列、角色切换、政策管理、工单或退款页面。
添加import/config测试并更新README、PROJECT_STATUS。
```

**命令**：

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```

**验收**：页面可打开；未配置 Coze 不崩溃；没有独立聊天首页。

**完成定义**：工程可启动，业务逻辑尚未塞入页面。

**Git**：`git add .; git commit -m "feat: scaffold ReplyFlow embedded workbench"; git push origin main`

**常见失败**：AI 加入 FastAPI、LangGraph、Docker 或前端框架时，删除无必要依赖再提交。

---

## 阶段 4：虚构种子数据和只读回复依据

**目标**：创建支撑动态演示的邮件、订单、物流和内部回复依据。

**AI 提示词**：

```text
本轮只做全虚构种子数据。
创建至少30封英文邮件、20个订单、物流轨迹、4份只读回复依据（物流、退换、破损、语气）。
所有姓名、邮箱、店铺、订单、SKU均虚构；邮箱用example.com。
覆盖一级、二级、三级和异常场景，至少10条R2。
回复依据文件只含 basis_id、section_id、version和内容，不包含上传/发布/审批/政策邮件字段。
创建 validate_seed_data.py 和测试，验证ID关联、场景分布、风险分布、时间金额逻辑。
运行时数据不得读取expected标签作为答案。
```

**文件**：`data/seed/*.json`、`data/reply_basis/*.md`、`scripts/validate_seed_data.py`、`tests/test_seed_data.py`。

**命令**：

```powershell
python scripts\validate_seed_data.py
python -m pytest tests\test_seed_data.py -q
rg -n "@example.com|basis_id|section_id" data
```

**验收**：邮件英文自然且不只是改名；内部依据不出现用户管理状态；无真实公司数据。

**完成定义**：数据关联完整，三档处理均有案例。

**Git**：`git add data scripts tests PROJECT_STATUS.md; git commit -m "feat: add fictional ReplyFlow data"; git push origin main`

**常见失败**：数据过于完美时，增加缺订单号、拼写错误、多诉求、订单冲突和工具失败案例。

---

## 阶段 5：SQLite 数据层和聚合模型

**目标**：实现原始邮件、聚合会话、订单物流、草稿和 outbox 的本地状态。

**AI 提示词**：

```text
本轮只做SQLite数据层。
按PRD第13节创建Pydantic模型、建表、repositories和init_db.py。
必须包含 emails、aggregate_threads、orders、shipping_events、reply_basis、reply_drafts、outbox、task_runs、tool_traces、risk_decisions、confirmations、audit_logs、idempotency_keys、evaluation_results。
不要创建 users/roles/approvals/support_tickets/refund_review_requests/policy_management 表。
实现幂等初始化、事务回滚、唯一operation_id和聚合查询测试。
```

**命令**：

```powershell
python scripts\init_db.py
python scripts\init_db.py
python -m pytest tests\test_db.py tests\test_repositories.py -q
```

**验收**：初始化两次不重复；本地数据库不提交 Git；表结构没有取消项。

**完成定义**：可从种子数据重建所有状态。

**Git**：`git add src scripts tests PROJECT_STATUS.md; git commit -m "feat: add ReplyFlow data and aggregation model"; git push origin main`

**常见失败**：数据库提交到 Git 时，补 `.gitignore` 并只提交初始化脚本和种子。

---

## 阶段 6：模拟邮件接入与聚合

**目标**：先完成“输入邮件—原始收件箱—顶部聚合站内信”，暂不运行 Agent。

**AI 提示词**：

```text
本轮只实现模拟邮件接入和会话聚合。
实现 ingestion.py、aggregation.py：
- 输入正文必填；主题/发件人为空时生成虚构值；
- 可选order_context_id只作为平台同步上下文；
- ingest后写emails，记录RECEIVING/RECEIVED/WRITTEN_TO_INBOX；
- 判断买家站内信并创建aggregate_threads，初始状态WAITING_ANALYSIS；
- 非买家消息只留在原始收件箱；
- 重复接入用source_message_id幂等；
- 新建integration tests覆盖一行输入、空输入、非买家消息、重复接入和关联订单上下文；
- 不做Agent分析、AI回复、页面和真实邮件同步。
```

**命令**：

```powershell
python -m pytest tests\test_ingestion.py tests\test_aggregation.py -q
python -m pytest -q
```

**人工验收**：调用测试辅助脚本输入一行邮件后，emails 增加 1，aggregate_threads 增加 1；重复调用不增加。

**完成定义**：动态演示的前半段有真实数据库变化，不是 UI 动画。

**Git**：`git add src tests PROJECT_STATUS.md; git commit -m "feat: add simulated email ingestion and aggregation"; git push origin main`

**常见失败**：系统为缺失订单号自动选择订单时立即修正；关联订单只可由演示者显式选择。

---

## 阶段 7：8 个 MCP Tools

**目标**：以 MCP 暴露接入、事实查询、依据检索、草稿和模拟发送。

**工具清单**：

```text
ingest_simulated_email
get_email
find_order
get_shipping_status
search_reply_basis
get_reply_tone
save_reply_draft
send_simulated_reply
```

**AI 提示词**：

```text
本轮只实现PRD规定的8个MCP Tools。
工具调用repositories，不散落SQL；Pydantic校验输入输出；统一错误码和trace_id。
save_reply_draft与send_simulated_reply要求confirmed=true、operation_id。
相同key同payload返回旧结果，不重复写；不同payload返回IDEMPOTENCY_CONFLICT。
send只写本地outbox。
不得实现create_support_ticket、create_refund_review_request、policy upload/publish和任何真实外部接口。
添加正常、无结果、未确认、重复执行、冲突和Tool Trace测试。
```

**命令**：`python -m pytest tests\test_mcp_tools.py -q; python -m pytest -q`

**验收**：工具恰好为 PRD 所需 8 个；连续模拟发送只产生一条 outbox。

**完成定义**：Tool 层能独立证明事实来源和写入限制。

**Git**：`git add src tests README.md PROJECT_STATUS.md; git commit -m "feat: add ReplyFlow MCP tools"; git push origin main`

**常见失败**：只在页面控制确认不合格；MCP 写工具必须独立拒绝未确认请求。

---

## 阶段 8：Skills 和内部回复依据检索

**目标**：建立三项可版本化 Skill 和本地只读依据检索。

**AI 提示词**：

```text
创建 skills/email_triage.md、reply_drafting.md、risk_routing.md。
每个Skill包含name/version、触发与不触发、输入输出、步骤、可用Tools、禁止事项、升级条件和示例。
实现skill_loader.py，校验Skill引用的Tool存在。
实现reply_basis_search.py，返回basis_id、section_id、quote、score、version；无命中/冲突要结构化返回。
不创建知识库管理页面，不创建政策文件夹，不从邮件更新依据。
添加缺文件、缺版本、错误Tool、正常检索、无命中和冲突测试。
```

**命令**：`python -m pytest tests\test_skills.py tests\test_reply_basis.py -q`

**验收**：能解释 Skill、Tool、MCP、内部依据的区别；依据只读且页面无管理入口。

**完成定义**：Skills 和依据可版本化、可测试。

**Git**：`git add skills src tests PROJECT_STATUS.md; git commit -m "feat: add ReplyFlow skills and reply basis"; git push origin main`

**常见失败**：AI 把 reply_basis 重命名为政策中心并加管理状态时，按 PRD 禁止项删除。

---

## 阶段 9：风险网关与三级路由

**目标**：代码化处理级别和高风险核对要求。

**AI 提示词**：

```text
实现risk_gateway.py。
输入邮件、分析、事实、依据结果、工具错误、置信度和草稿；输出risk_level、ai_level、matched_rules、allowed_actions、blocked_actions、checklist。
一级仅限PRD白名单；二级对应人工确认；退款/赔偿/拒付/投诉/法律/事实冲突/工具失败/低置信度/金额责任时限承诺均为R2+三级。
草稿后再次扫描；模型不能降低代码结果。
三级由店管核对，不得生成主管审核、工单或退款审核流程。
参数化测试覆盖每条规则、边界值、组合命中和模型试图降级。
```

**命令**：`python -m pytest tests\test_risk_gateway.py -q`

**验收**：退款+chargeback 必为三级；普通有证据物流可为一级；无订单号为二级澄清；草稿新引入承诺会升级。

**完成定义**：高风险召回测试 100%，处理级别可解释。

**Git**：`git add src tests PROJECT_STATUS.md; git commit -m "feat: add AI level routing and risk gateway"; git push origin main`

**常见失败**：把“缺订单号请求补充”自动判为一级时，以 PRD v2.1 为准改成二级，除非后续用户明确重新决策。

---

## 阶段 10：Demo Mode 与状态机

**目标**：在无模型凭证时让预置案例和有限自由输入真实运行。

**AI 提示词**：

```text
实现state_machine.py、demo_router.py、orchestrator.py、audit.py。
状态必须覆盖接收、写入收件箱、聚合、分析、查事实、分级、草稿、自动回复/等待确认/高风险核对、发送和失败。
Demo Mode使用有限可解释规则，不调用模型；仍真实调用8个MCP Tools、risk_gateway和SQLite。
支持三个预置案例；自由文本超出规则范围时明确提示切换Interactive Mode，不返回预写万能答案。
一级自动写本地outbox；二级停在WAITING_USER_CONFIRMATION；三级停在WAITING_HIGH_RISK_CHECK。
添加正常、缺订单号、退款拒付、超范围、Tool失败、非法状态跳转和幂等测试。
```

**命令**：`python -m pytest tests\test_state_machine.py tests\test_demo_orchestrator.py -q`

**验收**：清空所有模型 Key 后仍能跑三个案例；Trace 显示真实 MCP 调用。

**完成定义**：稳定演示不依赖网络和模型。

**Git**：`git add src tests PROJECT_STATUS.md; git commit -m "feat: add ReplyFlow demo workflow"; git push origin main`

**常见失败**：Demo 直接按 case_id 返回整段答案不合格；必须逐步调用本地能力。

---

## 阶段 11：Coze Interactive Mode

**目标**：支持模拟邮件浮窗的自由输入和订单上下文选择。

**配置**：Coze 工作流已由用户在国内工作区创建并发布。固定 Workflow ID 为 `7677420616827928610`，当前版本为 `v0.0.1`。

```dotenv
COZE_API_BASE_URL=https://api.coze.cn/v1
COZE_API_TOKEN=
COZE_WORKFLOW_ID=7677420616827928610
COZE_WORKFLOW_VERSION=
COZE_TIMEOUT_SECONDS=30
```

**AI 提示词**：

```text
实现coze_client.py：通过 `POST {COZE_API_BASE_URL}/workflow/run` 调用已发布 Workflow；请求使用 Bearer PAT、Workflow ID 和 parameters；本项目的开始节点只有 `payload_json`，因此必须将业务输入序列化为 JSON 字符串并放在 `parameters.payload_json` 中；Analyze 和 Draft 两次工作流调用；Pydantic 校验；处理401/403/429/超时/非JSON/Schema错误；不记录 Token。具体响应字段以实际 Coze OpenAPI 返回为准，不得凭空假设。
Python必须在Analyze后调用本地Tools，再把verified_facts_json和reply_basis_json传给Draft。
Coze不能执行发送、退款、改订单、工单、审批，也不能覆盖risk_gateway。
失败时明确提示并允许切Demo Mode，不静默伪造结果。
添加mock测试并更新.env.example和README。
```

**命令**：`python -m pytest tests\test_coze_client.py tests\test_interactive_orchestrator.py -q`

**验收**：未配置 Key 时不崩溃；配置 PAT 后自由输入可分析；Coze 请求不含 expected 答案和不必要数据；已发布工作流可用 `task_type=analyze` 真实试运行。

**完成定义**：工作流已发布、至少一条真实输入通过，且本地 Analyze/Draft API 联调通过；完整 8 条评测仍作为本阶段后续验收。

**Git**：`git add src tests .env.example README.md PROJECT_STATUS.md; git commit -m "feat: add Coze interactive mode"; git push origin main`

**常见失败**：不要把 Coze PAT/Token 粘贴给 AI；只提供脱敏错误和响应结构。

---

## 阶段 12：顶部聚合站内信与模拟邮件浮窗 UI（历史实现）

**目标**：完成最有说服力的动态页面：输入一行邮件并看到它进入站内信、分级和回复。

**AI 提示词**：

```text
本轮只做 Streamlit 顶部聚合站内信和动态模拟邮件浮窗，不改核心规则；页面只保留 Coze 单一模式，由智能客服开关控制是否调用。

页面结构：
1. 页面右下角固定“模拟收到邮件”浮动按钮，点击打开模态浮窗；
2. 文件夹栏：顶部聚合站内信、原始收件箱、发件箱、原邮箱站内信和亚马逊邮件，并展示计数；
3. 会话列表栏：当前文件夹内的邮件/会话；
4. 详情栏：邮件线程、级别标签、回复输入框和操作；
5. 依据栏：订单详情、AI依据、风险与Tool Trace。

原始文件夹只查看邮件原件，完整AI能力只出现在顶部聚合站内信。点击模拟收到邮件后，先更新原始收件箱，再更新顶部站内信；两条记录必须通过email_id/thread_id关联。发件箱展示本地outbox。

浮窗字段：正文必填、主题可选、模拟发件人可选、关联模拟订单可选；订单候选展示订单号、商品、金额、履约状态，选中后即时展示订单摘要。是否调用 AI 由页面“智能客服”开关决定。
按钮：模拟收到邮件、清空输入；智能客服关闭时只接收，开启时接收后自动调用 Coze。
接收后数据库计数变化，新会话置顶并自动选中，状态时间线动态刷新。

一级展示AI已回复；二级显示“AI回复”并把草稿写入输入框；三级显示“生成参考回复”、风险原因和核对清单，未全部勾选时发送禁用。
只显示店管，不显示角色切换。无审核队列、工单、退款审核和政策管理页面。
所有页面持续标识模拟数据/模拟发送。添加UI helper测试。
```

**命令**：

```powershell
python -m pytest -q
python -m streamlit run app.py
```

**人工验收脚本**：

1. 打开页面“智能客服”开关，点击底部“模拟邮件台”，选择 `ORD-1001` 查看订单摘要，输入 `Hi, where is order ORD-1001?`；
2. 点击“模拟收到邮件”；
3. 确认收件箱计数和顶部站内信计数增加；
4. 确认新会话置顶、显示 AI分析中，再变为一级并模拟回复；
5. 输入无订单号 `Where is my package?`，确认二级且不查物流；
6. 输入退款拒付句子，确认三级、发送禁用；
7. 完成核对清单后模拟发送；
8. 重复点击，outbox 不重复。

**完成定义**：面试官能看到真实动态流程，而不是静态展示或动画。

**当前验收记录**：阶段 12 的原控制台实现已被阶段 13 的原型复刻页面替换；保留邮件接入、订单上下文、L1/L2/L3、幂等和本地 outbox 能力。

## 阶段 A：原邮件工作台静态基线（当前完成阶段）

**目标**：先把原始亚马逊客服邮件 HTML 作为可核对的主展示页面，暂不接入 Agent。

**执行要求**：

1. 使用用户提供的 `0730亚马逊客服邮件能力建设原型.html` 作为页面基线，不用 Streamlit 重新拼接页面 DOM。
2. 保留原页面 6 条静态会话和原型订单信息；不把后端 30 封测试邮件全部放入首页。
3. 只保留点击会话切换详情、订单匹配联动、回复输入框输入/编辑/清空和区域滚动。
4. 导航、筛选、文件夹、排序、搜索、分页、时间切换、提醒、同步、订单操作、外链、弹窗、保存草稿和发送均只做视觉展示。
5. 不显示智能客服开关、AI 风险标签、模拟邮件台、Coze 错误或任何阶段 B 控件。

**输出文件**：

- `prototype/stage_a/amazon_mail_stage_a.html`
- `prototype/stage_a/amazon_mail_stage_a-标注版.html`
- `prototype/stage_a/annotations.json`
- `docs/stage_a_interaction_scope.md`

**验收**：启动 `python -m http.server 8510 --bind 127.0.0.1 --directory prototype/stage_a`，访问 `http://127.0.0.1:8510/amazon_mail_stage_a.html`；确认页面加载、邮件切换、订单联动、回复输入正常，其他控件不改变业务状态。

**Git**：阶段 A 完成后必须更新 `PROJECT_STATUS.md`，运行测试，提交并执行 `git push origin main`。

**当前状态**：已完成。阶段 B 未开始，必须等待用户明确指令。

---

## 阶段 13：原邮件工作台复刻与 Coze 单模式 Agent UI（阶段 B 规划）

**目标**：在不新建客服系统的前提下，把 Agent 接入原 HTML 邮件工作台骨架。

**执行状态**：本节是阶段 B 规划。阶段 A 完成后暂停，只有用户明确要求“继续阶段 B”时才执行。

**执行要求**：

1. 页面固定复刻深色 OMS 导航、顶部邮件工具栏、邮箱树、会话列表、邮件详情和右侧订单栏；导航、筛选、搜索、文件夹、分页和订单操作只做视觉占位。
2. 页面不展示 Demo Mode / Interactive Mode 切换，只展示“智能客服”开关，默认关闭。
3. 关闭开关时模拟邮件只接收并聚合，不调用 Coze；开启开关时自动调用 Coze。
4. L1 自动模拟回复，L2 草稿写入输入框等待店管确认，L3 草稿写入输入框并强制高风险核对。
5. Coze 失败只显示“AI 处理失败”和错误码，不回退本地规则、不伪造草稿。
6. FAILED 会话显示“重试 AI”按钮；开启智能客服后可重新调用 Coze，复用原邮件和订单上下文，不重复创建邮件。
7. 页面底部“模拟邮件台”打开浮窗；选择订单后即时展示摘要，提交邮件后新会话置顶并自动选中。
8. 使用 `st.container(border=True)` 或独立局部 HTML 卡片，不使用原始 HTML 包裹后续 Streamlit 组件，避免空白遮罩。
9. 智能客服开关是全局开关；打开前提示当前待处理数量，确认后批量处理所有待分析/失败的买家站内信，并显示当前序号和 L1/L2/L3/失败计数。
10. 开关保持开启时，新接入买家站内信自动进入处理队列；关闭后允许当前任务完成，但清空尚未开始的排队任务。
11. 阶段 B 增加一次性按钮“撤回上一轮处理（演示）”：仅已完成批次可撤回，批次进行中禁用；回退本地模拟发件箱、草稿和线程状态，并在 `stage_b_rollback_events` 留痕。

**历史验收结果**：旧版 Streamlit Agent 工作台曾验证原型骨架、智能客服开关、模拟邮件台、订单侧栏和 Coze 失败状态；阶段 B HTML 增量页面现已包含全局批处理、进度和演示撤回能力，需按本节重新验收。

**Git**：`git add app.py src tests README.md PROJECT_STATUS.md; git commit -m "feat: build dynamic aggregated inbox demo"; git push origin main`

**常见失败**：Streamlit rerun 重复执行时，使用 session state + operation_id 修复，不能只把按钮隐藏。

---

## 阶段 13：确认、核对、幂等与审计端到端

**目标**：证明三级控制无法从 UI、控制层或 Tool 层绕过。

**AI 提示词**：

```text
本轮只补端到端控制：
- 一级自动处理仍生成operation_id和审计；
- 二级需要店管confirmed；
- 三级必须checklist全true且二次确认；
- 保存AI原稿、店管编辑稿和最终发送稿；
- 重复点击不重复发送；同key不同payload冲突；
- 每个状态、Tool、确认和失败都有trace_id。

创建E2E测试覆盖一级自动发送、二级编辑发送、三级未核对阻断、三级核对后发送、重复发送、幂等冲突、Tool失败。
不要加入任何主管、审批、工单或退款审核。
```

**命令**：`python -m pytest tests\test_reply_flow_e2e.py -q; python -m pytest -q`

**验收**：直接调用 MCP 写 Tool 也不能绕过确认；三级缺一个勾选项都不能发送。

**完成定义**：人机协同是端到端约束，不是提示文案。

**Git**：`git add src tests PROJECT_STATUS.md; git commit -m "test: verify ReplyFlow control loop"; git push origin main`

**常见失败**：如果一级自动处理与“confirmed=true”冲突，控制层以系统确认类型写入，但仍需风险网关通过、白名单命中和完整审计。

**完成记录（2026-08-26）**：已完成 `tests/test_reply_flow_e2e.py`，覆盖 L1 自动发送、L2 未确认阻断/编辑稿发送、L3 未完成清单阻断/完成清单发送、重复发送幂等与 payload 冲突、Tool 失败升级、Coze 失败重试和 trace/audit 留痕。`send_simulated_reply` 已新增 `checklist` 输入，并在 Tool 层对 L3 的全部必填项执行二次校验，避免仅依赖 UI 禁用按钮。阶段测试 6 passed，全量测试 97 passed（1 条 FastMCP 依赖警告）。

---

## 阶段 14：30+ 条评测与 Go/No-Go

**目标**：评测动态接入、处理级别、安全和任务能力。

**AI 提示词**：

```text
创建至少30条独立JSONL评测案例，至少10条R2。
标注expected_source、intent、order_id、tools、ai_level、risk、terminal_state、must_not_claim。
运行时不得读取expected字段。
实现--mode demo/interactive，分别输出JSON和Markdown报告。
计算PRD第5.3节指标，按意图/级别/风险切片，安全失败置顶，每条失败带trace_ref。
评测接入后是否写emails和aggregate_threads，二级是否停待确认，三级未核对是否阻断，幂等是否有效。
自动输出Go/Conditional Go/No-Go；不得降低安全门槛或改标签迁就输出。
```

**命令**：

```powershell
python -m pytest tests\test_eval_metrics.py -q
python evals\run_eval.py --mode demo
python -m pytest -q
```

配置 Coze 后再运行 Interactive。

**验收**：Demo/Interactive 分开；失败可回溯；高风险漏判时必须 No-Go。

**完成定义**：评测结果可复现，处理级别开放范围有证据。

**Git**：`git add evals tests docs PROJECT_STATUS.md; git commit -m "feat: add ReplyFlow evaluation and go-no-go"; git push origin main`

**常见失败**：Demo 100% 时先检查是否按 case_id 或 expected 硬编码。

**完成记录（2026-08-26）**：已新增 `evals/run_eval.py`、`evals/README.md`、`tests/test_eval_metrics.py`，复用 30 条种子案例（13 条 R2），按独立临时 SQLite 运行 Demo/Interactive，输出逐案例 JSON/Markdown、意图/级别/风险切片、trace_ref 和控制验证。Demo 当前真实结果为 No-Go（高风险召回 61.5%，复杂语义覆盖不足）；Interactive 因 Coze 工作区额度不足记录为结构化失败并判定 No-Go，未伪造模型结果。阶段测试和全量测试均通过。

---

## 阶段 15：ROI 敏感性分析

**目标**：展示自动处理和人工确认在什么条件下可能有价值，不虚构真实收益。

**AI 提示词**：

```text
实现参数化ROI页面：月邮件量、一级占比、二级占比、三级占比、原人工时间、AI后处理时间、人工小时成本、单次模型成本、维护成本、错误概率和单次预期损失。
输出人工节省、模型成本、维护成本、风险成本、净收益和盈亏平衡量。
提供保守/基准/乐观假设，显著标注“敏感性分析，不代表真实收益”。
金额使用Decimal并测试边界。
```

**命令**：`python -m pytest tests\test_roi.py -q; python -m streamlit run app.py`

**验收**：三级占比升高或审核时间增加时，收益合理下降。

**完成定义**：页面同时能展示值得做和不值得做的参数区间。

**Git**：`git add src app.py tests README.md PROJECT_STATUS.md; git commit -m "feat: add ReplyFlow ROI sensitivity analysis"; git push origin main`

**完成记录（2026-08-26）**：已新增 `src/replyflow/roi.py` 与 `tests/test_roi.py`。计算模型将未被 L1/L2/L3 路由的邮件保留在人工路径，使用 `Decimal` 输出人工节省、人工节省价值、模型成本、维护成本、风险成本、净收益和盈亏平衡量；页面底部新增可展开的 ROI 敏感性分析面板，提供保守/基准/乐观预置情景、可编辑参数、正负收益提示和明确的虚构数据免责声明。ROI 专项测试 10 条、全量测试 108 条均通过。

---

## 阶段 16：README、HTML/PDF、视频和面试脚本

**目标**：形成可运行 Demo、案例说明、评测证据和演示兜底。

**AI 提示词**：

```text
完善README：嵌入式定位、取消项、三级处理、动态模拟邮件浮窗、架构、Coze/自建职责、8个MCP Tools、3个Skills、启动方式、评测、Go/No-Go、限制。
创建5-7分钟面试演示脚本：
1. 输入一级物流邮件并动态进入站内信；
2. 输入二级邮件，点击AI回复并编辑；
3. 输入三级退款拒付，展示核对与阻断；
4. 展示Tool Trace、幂等和评测；
5. 解释混合架构和模拟边界。

创建单页HTML/PDF案例说明和2-3分钟录屏分镜。只能使用本项目虚构数据和实际评测数字；不使用参考原型中的真实姓名、店铺、邮箱和订单。
HTML不能替代可运行Streamlit Demo。
```

**命令**：

```powershell
python -m pytest -q
python evals\run_eval.py --mode demo
python -m streamlit run app.py
```

**人工验收**：录屏从“输入一行邮件”开始；明确 Demo/Interactive 和模拟发送；不展示 Key。

**完成定义**：可运行 Demo + 代码 + 评测 + HTML/PDF + 视频五类材料齐全。

**Git**：提交 README、docs 和轻量案例页并推送到 GitHub；通常不提交视频。

**常见失败**：如果视频只展示预置静态会话，重新录制动态接入过程。

---

## 3. 最终自查清单

### 3.1 产品定位

- [ ] ReplyFlow 搭载在顶部聚合站内信，不是独立聊天产品。
- [ ] 右下角模拟邮件浮窗可输入一行邮件、选择订单并真实改变数据库状态。
- [ ] 原始收件箱、聚合会话、Agent处理和 outbox 能串联展示。
- [ ] 唯一业务角色是店管。

### 3.2 三级处理

- [ ] 一级只在白名单和风险网关均通过时模拟自动回复。
- [ ] 二级点击 AI回复后，草稿真实写入输入框。
- [ ] 三级显示风险原因和核对清单，未完成不能发送。
- [ ] 页面处理级别和后台 R0-R3 没有混淆。

### 3.3 Agent 能力

- [ ] 单 Agent 状态机真实运行。
- [ ] `email_triage`、`reply_drafting`、`risk_routing` 三个 Skill 可加载。
- [ ] 8 个 MCP Tools 可独立测试。
- [ ] 订单/物流来自 Tool，内部回复依据只读检索。
- [ ] Demo 和 Interactive 结果分开。

### 3.4 取消项

- [ ] 无主管、管理员或角色切换。
- [ ] 无审核队列、工单和退款审核。
- [ ] 无政策邮件、政策文件夹和政策治理页面。
- [ ] 无真实 Amazon、邮箱、支付和订单写接口。
- [ ] 无 Multi-Agent。

### 3.5 安全与证据

- [ ] 高风险识别 100%，无依据事实和未授权承诺 0%。
- [ ] 所有写入有确认、operation_id 和审计。
- [ ] Coze PAT/Token、真实数据和敏感日志不进入 Git/截图/视频。
- [ ] 30+ 独立评测，失败案例可回放。

## 4. 推荐面试演示顺序

1. **30秒**：说明它是嵌入顶部聚合站内信的个人研究作品，数据与发送均为模拟。
2. **60秒**：点击右下角“模拟收到邮件”，选择订单并输入一级物流邮件，点击“模拟收到邮件”。
3. **60秒**：展示原始收件箱和聚合站内信计数、新会话置顶、Tool Trace、一级自动回复。
4. **60秒**：输入二级尺码邮件，点击“AI回复”，修改一处后发送。
5. **90秒**：输入三级退款拒付邮件，展示风险原因、核对清单和未核对发送拦截。
6. **45秒**：重复发送，展示 operation_id 幂等。
7. **60秒**：展示评测与 Go/No-Go，解释当前自动化边界。
8. **45秒**：解释 Coze + 自建控制层和为什么没有真实公司落地也有验证价值。

面试时先讲邮件动态进入和业务控制，再讲 MCP、Skill、Coze 等技术概念。

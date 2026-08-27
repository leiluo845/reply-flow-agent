# ReplyFlow

ReplyFlow 是嵌入电商邮件系统顶部聚合站内信的 AI 回复能力作品：通过模拟邮件接入、订单/物流事实查询和三级处理规则，演示店管如何完成低风险自动处理、中风险人工确认和高风险核对。

## 当前状态

阶段 0：已完成项目目录、Python 3.11.9 虚拟环境和独立 Git 仓库初始化。

阶段 1：已完成产品契约、场景目录、状态目录和决策日志冻结。

阶段 2：已完成真实运行记录，8 条案例均有 Run ID 或重试记录；P05 保留依据外断言警告，尚未宣称全部案例无缺陷通过。

阶段 3：已完成最小 Python 工程骨架。项目可以安装依赖、运行测试，并启动阶段 B 本地 HTTP 演示服务。

阶段 4：已完成全虚构种子数据、只读回复依据和校验脚本。

阶段 5：已完成 SQLite 数据层、Pydantic 模型、幂等种子初始化和仓储层。可执行 `python scripts/init_db.py` 初始化本地数据库；数据库文件位于 `data/local/`，不会提交到 Git。

阶段 6：已完成模拟邮件接入和顶部聚合。输入一封虚构邮件会真实增加原始收件箱记录；买家消息会创建 `WAITING_ANALYSIS` 聚合会话，非买家消息不会进入顶部聚合。

阶段 7：已完成 8 个 MCP Tools。Tools 只调用本地仓储和 SQLite；草稿/模拟发送必须显式确认，并通过 `operation_id` 防重复和冲突。

阶段 8：已完成 3 个可版本化 Skills 和只读回复依据检索。检索结果包含依据 ID、章节、引用片段、分数和版本；无命中或冲突会结构化返回。

阶段 9：已完成确定性风险网关。R0/R1/R2/R3 分别映射到低风险、人工确认、高风险核对和架构阻断；模型输出不能降低本地结果。

阶段 10：已完成离线 Demo Mode。输入三类预置邮件会真实调用本地 Tools、Skill/依据层和风险网关，分别展示 L1 自动回复、L2 待确认、L3 高风险核对；无需 Coze 凭证。

阶段 11：已完成 Coze Interactive 客户端、Interactive 编排本地代码、mock 测试和真实 Analyze/Draft API 联调。请求体使用开始节点要求的 `parameters.payload_json`；未知 intent 会被本地 Schema 阻断。

阶段 13：已完成原亚马逊客服邮件工作台骨架复刻，并合并进入阶段 B HTML 主演示页；旧版 Streamlit 工作台已废弃并从仓库移除。

阶段 A：已完成原 HTML 客服邮件页面基线。主展示文件为 `prototype/stage_a/amazon_mail_stage_a.html`；阶段 A 只保留会话切换、订单联动、回复输入和滚动，不调用 Coze、不显示 Agent 控件。标注版和交互范围见 `prototype/stage_a/` 与 `docs/stage_a_interaction_scope.md`。

阶段 B：已完成原 HTML 基线上的全局智能客服增量页面草稿。运行 `stage_b_server.py` 后，开启全局开关可批量处理待处理站内信，显示进度和 L1/L2/L3 计数；开启期间新邮件自动入队；最近一轮完成后可使用“撤回上一轮处理（演示）”。

阶段 14：已完成 30 条离线评测（其中 13 条 R2），支持 `--mode demo/interactive`，输出 JSON/Markdown 报告、指标切片、trace_ref 和自动 Go/Conditional Go/No-Go。当前 Demo 因复杂语义和高风险覆盖不足为 No-Go；Interactive 因 Coze 工作区额度不足为 No-Go，均保留真实失败证据，不伪造模型结果。

阶段 15：已完成参数化 ROI 敏感性分析。`src/replyflow/roi.py` 使用 `Decimal` 计算人工节省、模型/维护/风险成本、净收益和盈亏平衡量；内置保守/基准/乐观三档假设。ROI 结果通过案例页和本地报告展示，所有结果均为虚构敏感性分析，不代表真实业务收益。

阶段 16：已完成面试交付材料：单页 [HTML 案例说明](./docs/replyflow_case_study.html)、[PDF 案例说明](./docs/replyflow_case_study.pdf)、[5–7 分钟面试脚本](./docs/interview_script.md) 和 [2–3 分钟录屏分镜](./docs/video_storyboard.md)。案例页只使用项目虚构数据和阶段 14 实际评测数字；HTML/PDF 用于讲解，不能替代可运行的阶段 B 主演示页。

## 项目定位与演示路径

ReplyFlow 不是独立聊天机器人，而是在电商邮件系统“顶部聚合站内信”上增量接入的单 Agent 回复能力。唯一可运行的主演示页是阶段 B HTML 页面；右下角「模拟邮件台」用于输入一行虚构邮件、选择虚构订单并观察状态变化：

```text
模拟邮件台 → 原始收件箱 → 顶部聚合站内信 → Coze Analyze/Draft
→ 本地事实/风险网关 → L1 自动回复 / L2 草稿确认 / L3 高风险核对
→ 本地模拟 outbox、Trace、Audit
```

唯一业务角色是店管。智能客服是页面外部的全局开关，不属于某一封邮件：关闭时只接收和聚合邮件；开启后确认处理当前全部待处理买家站内信，并让后续新邮件自动入队。所有发送均为本地模拟写入，不连接真实 Amazon、邮箱、支付或订单接口。

## Agent 能力清单

### 3 个 Skills

- `email_triage`：读取邮件、提取显式订单号、调用订单查询，不生成回复。
- `reply_drafting`：基于已验证事实和只读依据生成英文草稿，禁止凭空补全。
- `risk_routing`：结合本地规则、工具结果和草稿承诺决定 R0–R3 与 L1–L3。

### 8 个 MCP Tools

`ingest_simulated_email`、`get_email`、`find_order`、`get_shipping_status`、`search_reply_basis`、`get_reply_tone`、`save_reply_draft`、`send_simulated_reply`。

其中订单/物流/回复依据 Tool 为只读事实边界；草稿和发送 Tool 必须显式确认并使用 `operation_id`，L3 还必须通过完整核对清单。

## Coze 与自建控制层

Coze 负责概率型能力：意图识别、实体抽取和英文草稿生成。Python 本地层负责确定性能力：邮件接入、聚合、事实查询、风险网关、状态机、确认、幂等、审计和模拟 outbox。这样的分工让模型编排可以替换，同时把高风险写入边界留在可测试、可回放的代码中。

## 三级处理与取消项

| 级别 | 页面动作 |
|---|---|
| L1 | 低风险且事实完整时自动写入本地模拟 outbox |
| L2 | 生成草稿进入原回复框，店管确认/编辑后模拟发送 |
| L3 | 生成草稿并显示高风险提示，核对清单未完成时阻断发送 |

本项目不做主管/管理员/审批、政策邮件治理、工单、退款审核、真实外部写接口、Multi-Agent、LangGraph、FastAPI 或独立前端框架；这些范围会削弱“嵌入原邮件工作台”的展示重点。

## 评测与限制

- Demo：30 条案例、13 条 R2；动态接入率 100%（29/29），未授权承诺违规 0，无依据订单事实违规 0，高风险召回 61.5%，结论为 **No-Go**。
- Interactive：因 Coze 工作区额度不足记录为 **No-Go**，不伪造模型成功结果。
- 详细报告：[Demo 报告](./evals/reports/eval_demo.md)、[Interactive 报告](./evals/reports/eval_interactive.md)。
- ROI 面板是可编辑的保守/基准/乐观敏感性分析，不代表真实财务收益。

## 面试材料

- [技术图谱](./docs/技术图谱.md)
- [单页 HTML 案例说明](./docs/replyflow_case_study.html)
- [PDF 案例说明](./docs/replyflow_case_study.pdf)
- [5–7 分钟面试脚本](./docs/interview_script.md)
- [2–3 分钟录屏分镜](./docs/video_storyboard.md)

实际录屏需在本地手动完成；录制应从模拟邮件浮窗输入开始，不能只播放预置静态会话。

本项目只使用虚构数据，不连接真实 Amazon、邮箱、支付或订单写入接口。

## 本地启动

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
python scripts\validate_seed_data.py
.\.venv\Scripts\python.exe stage_b_server.py --port 8511
```

唯一主演示地址：`http://127.0.0.1:8511/`。页面默认全局智能客服关闭；开启后会提示待处理数量、批量处理所有待处理站内信并展示进度、L1/L2/L3/失败计数。新邮件在开关开启期间会自动加入队列；关闭后不再启动排队任务。

旧版 `app.py` / Streamlit 工作台已废弃并从仓库删除；不要启动 `8506`。阶段 A HTML 仅作为原型基线资料保留，不是可运行演示入口。

阶段 B 页面仍只使用虚构数据；所有发送和撤回均为本地演示状态。

生成/更新 PDF 案例页：

```powershell
$pdf = "C:\\Users\\Administrator\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe"
& $pdf scripts\generate_case_study_pdf.py
```

阶段 4 的数据只用于本地演示和离线评测，不连接真实业务系统。

继续开发或在新电脑恢复项目时，请先阅读 [START_HERE.md](./START_HERE.md)。正式需求以仓库中的 [PRD](./docs/requirements/ReplyFlow高风险售后Agent_PRD.md) 和[行动指南](./docs/requirements/ReplyFlow项目行动指南.md)为准。

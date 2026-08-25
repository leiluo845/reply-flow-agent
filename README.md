# ReplyFlow

ReplyFlow 是嵌入电商邮件系统顶部聚合站内信的 AI 回复能力作品：通过模拟邮件接入、订单/物流事实查询和三级处理规则，演示店管如何完成低风险自动处理、中风险人工确认和高风险核对。

## 当前状态

阶段 0：已完成项目目录、Python 3.11.9 虚拟环境和独立 Git 仓库初始化。

阶段 1：已完成产品契约、场景目录、状态目录和决策日志冻结。

阶段 2：已完成真实运行记录，8 条案例均有 Run ID 或重试记录；P05 保留依据外断言警告，尚未宣称全部案例无缺陷通过。

阶段 3：已完成最小工程骨架。项目现在可以安装依赖、运行测试，并启动一个仅展示定位和未实现提示的 Streamlit 页面。

阶段 4：已完成全虚构种子数据、只读回复依据和校验脚本。

阶段 5：已完成 SQLite 数据层、Pydantic 模型、幂等种子初始化和仓储层。可执行 `python scripts/init_db.py` 初始化本地数据库；数据库文件位于 `data/local/`，不会提交到 Git。

阶段 6：已完成模拟邮件接入和顶部聚合。输入一封虚构邮件会真实增加原始收件箱记录；买家消息会创建 `WAITING_ANALYSIS` 聚合会话，非买家消息不会进入顶部聚合。

阶段 7：已完成 8 个 MCP Tools。Tools 只调用本地仓储和 SQLite；草稿/模拟发送必须显式确认，并通过 `operation_id` 防重复和冲突。

阶段 8：已完成 3 个可版本化 Skills 和只读回复依据检索。检索结果包含依据 ID、章节、引用片段、分数和版本；无命中或冲突会结构化返回。

阶段 9：已完成确定性风险网关。R0/R1/R2/R3 分别映射到低风险、人工确认、高风险核对和架构阻断；模型输出不能降低本地结果。

阶段 10：已完成离线 Demo Mode。输入三类预置邮件会真实调用本地 Tools、Skill/依据层和风险网关，分别展示 L1 自动回复、L2 待确认、L3 高风险核对；无需 Coze 凭证。

阶段 11：已完成 Coze Interactive 客户端、Interactive 编排本地代码、mock 测试和真实 Analyze/Draft API 联调。请求体使用开始节点要求的 `parameters.payload_json`；未知 intent 会被本地 Schema 阻断。

阶段 13：已完成原亚马逊客服邮件工作台骨架复刻。旧版 Streamlit 工作台仍可运行，用于保留既有 Agent 逻辑回归。

阶段 A：已完成原 HTML 客服邮件页面基线。主展示文件为 `prototype/stage_a/amazon_mail_stage_a.html`；阶段 A 只保留会话切换、订单联动、回复输入和滚动，不调用 Coze、不显示 Agent 控件。标注版和交互范围见 `prototype/stage_a/` 与 `docs/stage_a_interaction_scope.md`。

阶段 B：已完成原 HTML 基线上的全局智能客服增量页面草稿。运行 `stage_b_server.py` 后，开启全局开关可批量处理待处理站内信，显示进度和 L1/L2/L3 计数；开启期间新邮件自动入队；最近一轮完成后可使用“撤回上一轮处理（演示）”。

本项目只使用虚构数据，不连接真实 Amazon、邮箱、支付或订单写入接口。

## 本地启动

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
python scripts\validate_seed_data.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

阶段 3 页面只是工作台骨架，不会产生真实发送；阶段 5 数据层只读写本地虚构数据库。Coze Workflow、POC 记录和动态 UI 均已完成，页面发送仍只写入本地 outbox。

当前 Agent 工作台地址：`http://localhost:8506`（本机启动 Streamlit 后）。阶段 A 静态基线可用 `python -m http.server 8510 --bind 127.0.0.1 --directory prototype/stage_a` 启动，访问 `http://127.0.0.1:8510/amazon_mail_stage_a.html`。阶段 A 不写入 SQLite；旧版 Agent 工作台的发送仍只写入本地 outbox。

阶段 B 预览：`.venv\Scripts\python.exe stage_b_server.py --port 8511`，访问 `http://127.0.0.1:8511/`。该页面仍只使用虚构数据；所有发送和撤回均为本地演示状态。

阶段 4 的数据只用于本地演示和离线评测，不连接真实业务系统。

继续开发或在新电脑恢复项目时，请先阅读 [START_HERE.md](./START_HERE.md)。正式需求以仓库中的 [PRD](./docs/requirements/ReplyFlow高风险售后Agent_PRD.md) 和[行动指南](./docs/requirements/ReplyFlow项目行动指南.md)为准。

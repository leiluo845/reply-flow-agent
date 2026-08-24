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

阶段 13：已完成原亚马逊客服邮件工作台骨架复刻。运行 `streamlit run app.py` 后打开“智能客服”开关，点击页面底部“模拟邮件台”，输入虚构邮件并选择订单查看摘要；关闭开关只接收邮件，开启后调用 Coze，展示 L1/L2/L3 风险分级、草稿确认和本地模拟发件箱变化。

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

当前页面地址：`http://localhost:8506`（本机启动 Streamlit 后）。所有发送都只写入 SQLite 本地模拟发件箱。

阶段 4 的数据只用于本地演示和离线评测，不连接真实业务系统。

继续开发或在新电脑恢复项目时，请先阅读 [START_HERE.md](./START_HERE.md)。正式需求以仓库中的 [PRD](./docs/requirements/ReplyFlow高风险售后Agent_PRD.md) 和[行动指南](./docs/requirements/ReplyFlow项目行动指南.md)为准。

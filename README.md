# ReplyFlow

ReplyFlow 是嵌入电商邮件系统顶部聚合站内信的 AI 回复能力作品：通过模拟邮件接入、订单/物流事实查询和三级处理规则，演示店管如何完成低风险自动处理、中风险人工确认和高风险核对。

## 当前状态

阶段 0：已完成项目目录、Python 3.11.9 虚拟环境和独立 Git 仓库初始化。

阶段 1：已完成产品契约、场景目录、状态目录和决策日志冻结。

阶段 2：进行中。已准备 Coze POC 提示词、Workflow 规格、8 条测试案例和结果模板；尚未完成真实 Coze Workflow 运行记录，因此不能视为阶段 2 完成。

阶段 3：已完成最小工程骨架。项目现在可以安装依赖、运行测试，并启动一个仅展示定位和未实现提示的 Streamlit 页面。

阶段 4：已完成全虚构种子数据、只读回复依据和校验脚本。

阶段 5：已完成 SQLite 数据层、Pydantic 模型、幂等种子初始化和仓储层。可执行 `python scripts/init_db.py` 初始化本地数据库；数据库文件位于 `data/local/`，不会提交到 Git。

阶段 6：已完成模拟邮件接入和顶部聚合。输入一封虚构邮件会真实增加原始收件箱记录；买家消息会创建 `WAITING_ANALYSIS` 聚合会话，非买家消息不会进入顶部聚合。

阶段 7：已完成 8 个 MCP Tools。Tools 只调用本地仓储和 SQLite；草稿/模拟发送必须显式确认，并通过 `operation_id` 防重复和冲突。

阶段 8：已完成 3 个可版本化 Skills 和只读回复依据检索。检索结果包含依据 ID、章节、引用片段、分数和版本；无命中或冲突会结构化返回。

本项目只使用虚构数据，不连接真实 Amazon、邮箱、支付或订单写入接口。

## 本地启动

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
python scripts\validate_seed_data.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

阶段 3 页面只是工作台骨架，不会调用 Coze，也不会产生真实发送；阶段 5 数据层同样只读写本地虚构数据库。

阶段 4 的数据只用于本地演示和离线评测，不连接真实业务系统。

继续开发或在新电脑恢复项目时，请先阅读 [START_HERE.md](./START_HERE.md)。正式需求以仓库中的 [PRD](./docs/requirements/ReplyFlow高风险售后Agent_PRD.md) 和[行动指南](./docs/requirements/ReplyFlow项目行动指南.md)为准。

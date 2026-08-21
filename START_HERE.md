# START HERE：ReplyFlow 项目接手说明

本文件用于让一个没有历史聊天上下文的人或 AI 在新电脑上继续推进 ReplyFlow。开始工作前，必须依次完整阅读：

1. [PROJECT_STATUS.md](./PROJECT_STATUS.md)
2. [ReplyFlow PRD v2.1](./docs/requirements/ReplyFlow高风险售后Agent_PRD.md)
3. [ReplyFlow 项目行动指南 v2.1](./docs/requirements/ReplyFlow项目行动指南.md)
4. [阶段 1 产品契约](./docs/product_contract.md)
5. [阶段 1 场景目录](./docs/scenario_catalog.md)
6. [阶段 1 状态目录](./docs/state_catalog.md)
7. [阶段 1 决策日志](./docs/decision_log.md)
8. [新电脑恢复指南](./docs/NEW_COMPUTER_SETUP.md)
9. [阶段 2 Coze Workflow Spec](./poc/coze/workflow_spec.md)
10. [阶段 2 POC Cases](./poc/coze/poc_cases.md)

## 当前状态

- 阶段 0 已完成：Python 3.11.9 虚拟环境、独立 Git 仓库和基础文件已建立。
- 阶段 1 已完成：产品契约、场景目录、状态目录和决策日志已冻结。
- 阶段 2 进行中：Coze POC 提示词、Workflow 规格、8 条测试案例和结果模板已准备。
- 阶段 2 尚未完成：还缺 Coze Workflow 的 8 条真实运行记录、Run ID、人工评分和失败分析。
- 阶段 3 已完成：最小 Python/Streamlit 工程骨架、配置模块、测试和空目录结构已创建；页面可启动但只显示未实现提示。
- 阶段 4 已完成：全虚构种子数据、只读回复依据和校验脚本已创建。
- 阶段 5 已完成：SQLite 数据层、Pydantic 模型、幂等建库/种子初始化和仓储层已实现并通过测试。
- 当前下一步是阶段 6：模拟邮件接入和顶部聚合站内信会话创建。阶段 6 不需要登录 Coze。
- 实际登录扣子、创建 Workflow 和运行 8 条案例可后置到阶段 11 前后。登录前不得伪造 Run/Execute ID 或 POC 通过结论。

接手者不能只相信本段状态。必须检查 Git、现有文件和测试结果；若 `PROJECT_STATUS.md` 更新日期更晚，以实际仓库和测试结果为准。

## 不可改变的产品契约

- 产品形态：嵌入邮件系统“顶部聚合站内信”的 AI 回复能力，不是独立聊天产品。
- 唯一业务角色：店管。
- 一级：白名单低风险场景通过风险网关后写入本地模拟发件箱。
- 二级：店管点击“AI回复”，编辑或确认草稿后模拟发送。
- 三级：店管点击“生成参考回复”，完成高风险核对清单后模拟发送。
- 演示入口：折叠的“演示控制台（模拟邮件接入）”，支持输入邮件并真实改变 SQLite 状态。
- 数据边界：全部使用虚构数据，不连接真实 Amazon、邮箱、支付或订单写接口。
- 技术路线：Python 3.11、Streamlit、SQLite、Pydantic、MCP Python SDK、Coze Workflow、本地状态机、pytest 和 JSONL 评测。

不得新增主管、管理员、审批队列、工单、退款审核、政策邮件、政策文件夹、政策治理、真实发送、真实退款、Multi-Agent、LangGraph 或 FastAPI。

## 工作方式

1. 每次只执行行动指南中的一个阶段。
2. 开始前说明本轮范围、修改文件和验收标准。
3. 新增核心逻辑必须有测试。
4. 完成后更新 `PROJECT_STATUS.md`，运行测试并提交 Git。
5. 将提交推送到 GitHub；未推送的本地修改不能视为跨设备备份完成。
6. `.env` 和 Coze PAT/Token 不得提交；换电脑后根据 `.env.example` 重新配置。

## 给新 AI 的启动提示词

```text
你现在接手 ReplyFlow AI Agent 产品作品集项目。

请完整阅读 START_HERE.md、PROJECT_STATUS.md、docs/requirements 下的 PRD 和行动指南，以及 docs/product_contract.md、docs/scenario_catalog.md、docs/state_catalog.md、docs/decision_log.md，然后检查 git status、git log、当前代码与测试。

用户技术背景较弱，说明使用中文。每次只完成一个阶段，不使用真实公司数据，不虚构业务收益，不新增 PRD 禁止的角色、工单、政策治理或真实外部写操作。完成后报告修改文件、命令、测试、人工验收、已知问题和下一步，并更新 PROJECT_STATUS.md。

当前阶段是阶段 6：模拟邮件接入和顶部聚合站内信会话创建。阶段 3 工程骨架、阶段 4 虚构种子数据和阶段 5 SQLite 数据层均已完成；先运行 `python -m pytest -q` 确认基线通过，再按行动指南阶段 6 实现 ingestion.py、aggregation.py 和对应测试。不要登录真实 Amazon，不要连接真实邮箱，不要伪造 Coze 运行记录。
```

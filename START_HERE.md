# START HERE：ReplyFlow 项目接手说明

本文件用于让一个没有历史聊天上下文的人或 AI 在新电脑上继续推进 ReplyFlow。开始工作前，必须依次完整阅读：

1. [PROJECT_STATUS.md](./PROJECT_STATUS.md)
2. [ReplyFlow PRD v2.0](./docs/requirements/ReplyFlow高风险售后Agent_PRD.md)
3. [ReplyFlow 项目行动指南 v2.0](./docs/requirements/ReplyFlow项目行动指南.md)
4. [阶段 1 产品契约](./docs/product_contract.md)
5. [阶段 1 场景目录](./docs/scenario_catalog.md)
6. [阶段 1 状态目录](./docs/state_catalog.md)
7. [阶段 1 决策日志](./docs/decision_log.md)
8. [新电脑恢复指南](./docs/NEW_COMPUTER_SETUP.md)

## 当前状态

- 阶段 0 已完成：Python 3.11.9 虚拟环境、独立 Git 仓库和基础文件已建立。
- 阶段 1 已完成：产品契约、场景目录、状态目录和决策日志已冻结。
- 尚未安装业务框架，尚未编写业务代码。
- 下一阶段是阶段 2：Dify 最小 POC。

接手者不能只相信本段状态。必须检查 Git、现有文件和测试结果；若 `PROJECT_STATUS.md` 更新日期更晚，以实际仓库和测试结果为准。

## 不可改变的产品契约

- 产品形态：嵌入邮件系统“顶部聚合站内信”的 AI 回复能力，不是独立聊天产品。
- 唯一业务角色：店管。
- 一级：白名单低风险场景通过风险网关后写入本地模拟发件箱。
- 二级：店管点击“AI回复”，编辑或确认草稿后模拟发送。
- 三级：店管点击“生成参考回复”，完成高风险核对清单后模拟发送。
- 演示入口：折叠的“演示控制台（模拟邮件接入）”，支持输入邮件并真实改变 SQLite 状态。
- 数据边界：全部使用虚构数据，不连接真实 Amazon、邮箱、支付或订单写接口。
- 技术路线：Python 3.11、Streamlit、SQLite、Pydantic、MCP Python SDK、Dify Workflow、本地状态机、pytest 和 JSONL 评测。

不得新增主管、管理员、审批队列、工单、退款审核、政策邮件、政策文件夹、政策治理、真实发送、真实退款、Multi-Agent、LangGraph 或 FastAPI。

## 工作方式

1. 每次只执行行动指南中的一个阶段。
2. 开始前说明本轮范围、修改文件和验收标准。
3. 新增核心逻辑必须有测试。
4. 完成后更新 `PROJECT_STATUS.md`，运行测试并提交 Git。
5. 将提交推送到 GitHub；未推送的本地修改不能视为跨设备备份完成。
6. `.env` 和 API Key 不得提交；换电脑后根据 `.env.example` 重新配置。

## 给新 AI 的启动提示词

```text
你现在接手 ReplyFlow AI Agent 产品作品集项目。

请完整阅读 START_HERE.md、PROJECT_STATUS.md、docs/requirements 下的 PRD 和行动指南，以及 docs/product_contract.md、docs/scenario_catalog.md、docs/state_catalog.md、docs/decision_log.md，然后检查 git status、git log、当前代码与测试。

用户技术背景较弱，说明使用中文。每次只完成一个阶段，不使用真实公司数据，不虚构业务收益，不新增 PRD 禁止的角色、工单、政策治理或真实外部写操作。完成后报告修改文件、命令、测试、人工验收、已知问题和下一步，并更新 PROJECT_STATUS.md。

当前下一阶段是阶段 2：Dify 最小 POC。先汇报当前真实状态和本轮建议，不要一次生成整个项目。
```

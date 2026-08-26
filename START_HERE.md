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
11. [页面规范：原邮件工作台内置 Agent](./docs/ui_prototype_spec.md)
12. [技术图谱](./docs/技术图谱.md)

## 当前状态

- 阶段 0 已完成：Python 3.11.9 虚拟环境、独立 Git 仓库和基础文件已建立。
- 阶段 1 已完成：产品契约、场景目录、状态目录和决策日志已冻结。
- 阶段 2 已完成：Coze `ReplyFlow_POC` 已发布（Workflow ID `7677420616827928610`，版本 `v0.0.1`），本地 Analyze/Draft API 联调和 8 条案例运行记录已保存。
- 阶段 3 已完成：最小 Python/Streamlit 工程骨架、配置模块、测试和空目录结构已创建；页面可启动但只显示未实现提示。
- 阶段 4 已完成：全虚构种子数据、只读回复依据和校验脚本已创建。
- 阶段 5 已完成：SQLite 数据层、Pydantic 模型、幂等建库/种子初始化和仓储层已实现并通过测试。
- 阶段 6 已完成：模拟邮件接入、买家消息聚合、非买家原始收件箱保留和 source_message_id 幂等已实现并通过测试。
- 阶段 7 已完成：8 个 MCP Tools、Pydantic Schema、统一错误码/Trace、确认门槛和 operation_id 幂等已实现并通过测试。
- 阶段 8 已完成：3 个可版本化 Skills、Tool 引用校验、只读回复依据检索、评分、无命中和冲突响应已实现并通过测试。
- 阶段 9 已完成：确定性风险网关、R0-R3 风险、L1-L3 处理级别、允许/阻断动作、核对清单和模型降级阻断已实现并通过测试。
- 阶段 10 已完成：Demo Mode 状态机、有限规则路由、三类预置场景、Tool 故障升级、超范围提示和本地 outbox 串联已实现并通过测试。
- 阶段 11 本地代码已完成：Coze 客户端、Analyze/Draft Schema、错误处理和 Interactive 编排 mock 测试已通过；真实 Workflow 已发布并完成 1 条试运行。
- 阶段 12 已完成：Streamlit 动态工作台、右下角模拟邮件浮窗、顶部聚合、订单摘要、L1/L2/L3 交互、三级核对和模拟发件箱已实现并通过浏览器验收。
- 阶段 13、14、15、16 已完成：页面重构、端到端控制测试、30 条离线评测、ROI 敏感性分析和面试交付材料均已提交；`.env` 中的 Coze PAT 只保留在用户本机。
- 阶段 A 已完成：原始 HTML 客服邮件页面已复制到 `prototype/stage_a/amazon_mail_stage_a.html`，仅保留会话切换、订单联动、回复输入和滚动；不调用 Coze、不显示 Agent 控件。交互范围见 `docs/stage_a_interaction_scope.md`。
- 阶段 B 已完成：主页面 `prototype/stage_b/index.html` + `stage_b_server.py` 接入全局智能客服批处理、进度条、新邮件自动入队、失败重试和演示撤回。
- 阶段 16 面试材料：`docs/replyflow_case_study.html`、`docs/replyflow_case_study.pdf`、`docs/interview_script.md`、`docs/video_storyboard.md`；实际录屏需人工按分镜完成，通常不提交视频文件。
- 8 条案例完成前不得声称完整 POC 评测通过；不得把 PAT 写入聊天、仓库、截图或日志。

接手者不能只相信本段状态。必须检查 Git、现有文件和测试结果；若 `PROJECT_STATUS.md` 更新日期更晚，以实际仓库和测试结果为准。

## 不可改变的产品契约

- 产品形态：嵌入邮件系统“顶部聚合站内信”的 AI 回复能力，不是独立聊天产品。
- 唯一业务角色：店管。
- 一级：白名单低风险场景通过风险网关后写入本地模拟发件箱。
- 二级：店管点击“AI回复”，编辑或确认草稿后模拟发送。
- 三级：店管点击“生成参考回复”，完成高风险核对清单后模拟发送。
- 演示入口：页面底部“模拟邮件台”浮动按钮，点击打开浮窗；支持输入邮件、选择订单并真实改变 SQLite 状态。
- 阶段 A 页面入口：使用 `python -m http.server 8510 --bind 127.0.0.1 --directory prototype/stage_a`，访问 `http://127.0.0.1:8510/amazon_mail_stage_a.html`。阶段 A 为静态基线，不改变 SQLite。
- 数据边界：全部使用虚构数据，不连接真实 Amazon、邮箱、支付或订单写接口。
- 技术路线：Python 3.11、Streamlit、CSS/局部 HTML、SQLite、Pydantic、MCP Python SDK、Coze Workflow、本地状态机、pytest 和 JSONL 评测。

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

当前阶段 16 已完成；如继续工作，应先检查 `PROJECT_STATUS.md` 和行动指南，除非用户明确指定，否则不要新增功能范围。不要登录真实 Amazon，不要连接真实邮箱，不要伪造 Coze 运行记录。
```

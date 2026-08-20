# ReplyFlow Project Status

## 当前项目

ReplyFlow｜聚合站内信 AI 回复与动态演示工作台

## 当前阶段

阶段 2——Dify 最小 POC（进行中）

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
  - `poc/dify/analyze_prompt.md`
  - `poc/dify/draft_prompt.md`
  - `poc/dify/workflow_spec.md`
  - `poc/dify/poc_cases.md`
  - `poc/dify/poc_results_template.md`

## 本轮修改

- 创建 Dify Analyze Prompt：输入邮件主题/正文/上下文，输出严格 JSON 的买家消息识别、意图、订单号、缺失字段和置信度。
- 创建 Dify Draft Prompt：只允许基于 `verified_facts_json` 和 `reply_basis_json` 生成英文草稿，禁止承诺退款、赔偿、金额或确定时限。
- 创建 Dify Workflow 规格，明确 Dify 只负责概率型分析与草稿生成；本地 Python 控制层负责状态、MCP Tool、风险网关、确认、幂等、审计和模拟发送。
- 创建 8 条虚构 POC 案例，覆盖普通物流、尺码换货、拒付威胁、缺订单号、破损退款、订单不存在、提示注入和非买家平台通知。
- 创建 POC 结果模板，要求记录真实 Dify Run ID、原始输出、Schema 解析、人工评分和失败分析。
- 更新 `START_HERE.md`、`PROJECT_STATUS.md` 和 `README.md`，明确阶段 2 为进行中，不能把离线材料误判为阶段完成。
- 未安装 Streamlit、MCP SDK、Pydantic 或其他业务依赖。
- 未创建业务代码、数据库或真实外部接口。

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
- 命令：检查 `poc/dify/*.md` 中 18 个 JSON 代码块可解析
- 结果：通过。

## 已知问题

- 当前 Codex/PowerShell 环境访问 `https://cloud.dify.ai` 超时，暂时无法创建 Dify Workflow。
- 尚未产生阶段 2 必需的 8 条真实 Dify 运行记录；不得手工伪造 `poc_results.md`。
- 需要用户在可联网浏览器登录/注册 Dify Cloud 后继续运行 POC。
- 尚未安装业务框架和依赖；按行动指南后续阶段逐步安装。
- Git 身份仅在本项目内配置为 GitHub 账号 `leiluo845`，不修改全局 Git 配置。
- 当前电脑的 remote 使用 SSH deploy key 推送；换电脑时按 `docs/NEW_COMPUTER_SETUP.md` 重新登录或配置新 key。

## 下一步

- 在浏览器进入 Dify Cloud，创建 `ReplyFlow POC` Workflow。
- 按 `poc/dify/workflow_spec.md` 配置 Analyze 和 Draft 分支。
- 将 `poc/dify/poc_results_template.md` 复制为 `poc/dify/poc_results.md`，运行 `poc/dify/poc_cases.md` 的 8 条案例并填写真实 Run ID、输出、评分和失败分析。
- 真实结果完成后，阶段 2 才可标记完成并提交 `docs: validate Dify analysis and drafting POC`。

## 最后更新时间

2026-08-20

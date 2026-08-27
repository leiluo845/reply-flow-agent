# ReplyFlow 新电脑恢复指南

## 1. 需要安装

- Git for Windows
- Python 3.11.x
- PowerShell
- 任意 AI 编程工具；当前项目可继续使用 Codex

阶段 2 的离线契约不需要扣子账号；实际创建 Workflow、运行 POC 或接入 Interactive Mode 时才需要扣子工作台账号。Docker、SQLite 命令行、VS Code、Cursor 和 Coze CLI 都不是恢复项目的必要条件。

## 2. 克隆私有仓库

先在新电脑登录有权限的 GitHub 账号，然后执行：

```powershell
Set-Location '你准备保存项目的目录'
git clone https://github.com/leiluo845/reply-flow-agent.git
Set-Location 'reply-flow-agent'
```

如果使用 GitHub CLI：

```powershell
gh auth login
gh repo clone leiluo845/reply-flow-agent
Set-Location 'reply-flow-agent'
```

当前这台电脑因为 GitHub HTTPS 连接不稳定，已为本仓库配置过一把仅用于 `reply-flow-agent` 的可写 deploy key，并把本地 remote 切到 SSH。换电脑时不需要复用这台电脑的私钥；推荐先用 GitHub CLI 登录后克隆。如果新电脑 HTTPS 仍不稳定，再为新电脑单独配置 SSH key 或 deploy key。

## 3. 重建 Python 环境

`.venv` 不会上传 GitHub，必须在新电脑重建：

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python --version
```

Python 必须显示 `3.11.x`。如果新电脑没有 Python 3.11，可从 Python 官网安装 3.11.9，或者使用 `uv`：

```powershell
python -m pip install --user --index-url https://pypi.org/simple uv
python -m uv python install 3.11.9
python -m uv venv --python 3.11.9 .venv
```

安装阶段 3 依赖并把本地包装入虚拟环境：

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest -q
```

测试通过后，启动唯一的阶段 B 主演示页：

```powershell
python stage_b_server.py --port 8511
```

访问 `http://127.0.0.1:8511/`。旧版 `app.py` / Streamlit 工作台已废弃并从仓库删除，不要启动 `8506`。

阶段 16 案例页材料也已纳入仓库：`docs/replyflow_case_study.html`、`docs/replyflow_case_study.pdf`、`docs/interview_script.md`、`docs/video_storyboard.md`。如需重建 PDF，运行 `python scripts/generate_case_study_pdf.py`；该命令依赖 `reportlab`，已写入 `requirements.txt`。

## 4. 恢复本地配置

```powershell
Copy-Item '.env.example' '.env'
```

随后手工填写 `COZE_API_BASE_URL`、Coze Personal Access Token、`COZE_WORKFLOW_ID` 和版本备注。国内工作区默认地址为 `https://api.coze.cn/v1`；不要从聊天记录或公开文件复制不确定的 Token，不要把 `.env` 提交到 Git。

## 5. 接续工作

```powershell
git status
git log -5 --oneline
Get-Content '.\START_HERE.md'
Get-Content '.\PROJECT_STATUS.md'
```

把 `START_HERE.md` 中的启动提示词交给新的 AI。阶段 1 后，新 AI 还必须阅读 `docs/product_contract.md`、`docs/scenario_catalog.md`、`docs/state_catalog.md` 和 `docs/decision_log.md`。开始修改前先运行仓库已有测试；完成一个阶段后执行：

```powershell
git add .
git commit -m '填写本阶段提交说明'
git push
```

## 6. 不会被 GitHub 备份的内容

- `.venv`
- `.env` 和所有模型凭证
- 本地 SQLite 数据库
- 日志和临时评测输出
- 尚未提交或尚未推送的改动

这些内容需要重建或通过安全的密码管理工具单独保存。

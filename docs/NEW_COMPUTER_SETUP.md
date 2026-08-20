# ReplyFlow 新电脑恢复指南

## 1. 需要安装

- Git for Windows
- Python 3.11.x
- PowerShell
- 任意 AI 编程工具；当前项目可继续使用 Codex

阶段 2 开始才需要 Dify Cloud 账号。Docker、SQLite 命令行、VS Code、Cursor 和 Dify CLI 都不是恢复项目的必要条件。

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

项目产生依赖清单后，再执行对应安装命令。阶段 1 当前没有业务依赖需要恢复。

## 4. 恢复本地配置

```powershell
Copy-Item '.env.example' '.env'
```

随后手工填写 Dify 地址和 API Key。不要从聊天记录或公开文件复制不确定的密钥，不要把 `.env` 提交到 Git。

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
- `.env` 和所有 API Key
- 本地 SQLite 数据库
- 日志和临时评测输出
- 尚未提交或尚未推送的改动

这些内容需要重建或通过安全的密码管理工具单独保存。

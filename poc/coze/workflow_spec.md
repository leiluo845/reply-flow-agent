# ReplyFlow Coze POC：Workflow Spec（工作流规格）

> 版本：v0.1（阶段 2）  
> 目标：用最小 Coze Workflow 验证“分析”和“生成草稿”两个概率型能力；确定性状态、工具、风险和发送仍归本地 Python 控制层。

## 1. 为什么拆成两个 task_type

ReplyFlow 的正式流程需要先分析邮件，再由本地工具取得事实，最后生成草稿。POC 阶段不把订单查询、发送等业务写入 Coze，避免把高风险控制藏在模型工作流中。因此使用一个工作流、一个 `task_type` 分支：

```text
Start
  -> task_type == "analyze" ? -> Analyze LLM -> Parse JSON -> End(analyze_result)
  -> task_type == "draft"   ? -> Draft LLM   -> Parse JSON -> End(draft_result)
```

如果当前 Coze 版本不方便在一个 Workflow 中做条件分支，可以复制为两个 Workflow：`ReplyFlow POC - Analyze` 和 `ReplyFlow POC - Draft`。这不改变产品架构，也不构成 Multi-Agent。

## 2. Coze 节点配置

### 2.1 Start 节点输入变量

| 变量 | 类型 | Analyze 必填 | Draft 必填 | 示例 |
|---|---|---:|---:|---|
| `task_type` | string | 是 | 是 | `analyze` / `draft` |
| `subject` | string | 是（最大 300 字符） | 否 | `Where is my order?` |
| `body` | string | 是（最大 8,000 字符） | 否 | `Could you check...` |
| `order_context_id` | string | 否 | 否 | `demo-thread-001` |
| `email_json` | string/JSON | 否 | 是 | `{"subject":"...","body":"..."}` |
| `verified_facts_json` | string/JSON | 否 | 是 | 本地工具验证后的事实 |
| `reply_basis_json` | string/JSON | 否 | 是 | 固定只读依据 |
| `risk_context_json` | string/JSON | 否 | 是 | 本地风险上下文 |

不要把 Coze PAT/Token、真实邮箱、真实订单或公司内部数据作为输入。

### 2.2 Analyze 分支

1. **If/Else 节点**：`task_type == "analyze"`。
2. **LLM 节点**：粘贴 `analyze_prompt.md` 的 System Prompt；关闭不必要的对话记忆；温度建议 0 或最低可用值。
3. **结构化输出**：配置 JSON Schema；若无法配置，则在后续 Code/Template 节点中只做 JSON 解析，不做业务决策。
4. **End 节点**：输出 `analyze_result`，原样保留模型 JSON 和运行 ID。

建议 JSON Schema：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["is_buyer_message", "intent", "order_id", "missing_fields", "confidence"],
  "properties": {
    "is_buyer_message": {"type": "boolean"},
    "intent": {"type": "string", "enum": ["shipping_status", "delivered_not_received", "size_or_fit", "return_or_exchange", "damaged_item", "refund_request", "chargeback_threat", "order_change", "product_question", "other_buyer_support", "non_buyer_message"]},
    "order_id": {"type": ["string", "null"]},
    "missing_fields": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

### 2.3 Draft 分支

1. **If/Else 节点**：`task_type == "draft"`。
2. **LLM 节点**：粘贴 `draft_prompt.md` 的 System Prompt；关闭不必要的对话记忆；温度建议 0.2 左右。
3. **结构化输出**：配置 `draft_subject`、`draft_body`、`used_basis`、`uncertainties` 四个字段。
4. **End 节点**：输出 `draft_result`，原样保留模型 JSON 和运行 ID。

建议 JSON Schema：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["draft_subject", "draft_body", "used_basis", "uncertainties"],
  "properties": {
    "draft_subject": {"type": "string", "minLength": 1},
    "draft_body": {"type": "string", "minLength": 1},
    "used_basis": {"type": "array", "items": {"type": "string"}},
    "uncertainties": {"type": "array", "items": {"type": "string"}}
  }
}
```

## 3. 手工创建步骤（扣子 Coze 国内工作区）

1. 登录扣子，进入目标工作空间的工作流列表，新建工作流 `ReplyFlow POC`。不创建独立聊天 Bot，也不把它发布成用户客服入口。
2. 添加开始节点、条件分支、两个 LLM 节点和结束节点；按上表创建输入变量。
3. 在 Coze 的变量选择器中把开始节点变量映射给 LLM 节点。提示词里的 `{{...}}` 是语义占位说明，实际以工作台生成的变量引用为准。
4. 为 Analyze 和 Draft 分别设置结构化输出参数；若当前工作区只支持文本输出，则增加 JSON 解析节点，并让结束节点只输出解析后的对象。
5. 先使用一条虚构案例试运行，确认输出字段，再发布工作流并记录 `workflow_id`、发布时间和人工版本号。
6. 将 `poc_results_template.md` 复制为 `poc_results.md`，运行 8 条案例。每次记录日期、Workflow 版本、Run/Execute ID（页面或接口实际提供什么就记录什么）、原始输出、解析结果、人工评分和失败原因。
7. 如 Coze 页面支持导出或复制工作流配置，保存到 `poc/coze/ReplyFlow_POC_export.*`；不支持时记录“不支持/未导出”。导出不是阶段验收前置条件，不得手工伪造配置文件。

## 4. 后续 API 接入契约

Interactive Mode 默认使用国内开放平台：

```text
POST {COZE_API_BASE_URL}/workflow/run
Authorization: Bearer {COZE_API_TOKEN}
Content-Type: application/json
```

请求至少包含已发布的 `workflow_id` 和 `parameters`。`parameters` 中只传本任务所需的虚构邮件、已验证事实、回复依据和风险上下文。具体响应包裹字段以接入时的 Coze OpenAPI 文档和实际返回为准，`coze_client.py` 必须先提取工作流输出，再用 Pydantic 校验 Analyze/Draft Schema；不得依赖页面展示文本。

## 5. POC 与正式产品的边界

| 能力 | Coze POC | 正式本地控制层 |
|---|---|---|
| 邮件意图/实体识别 | 负责 | 校验并决定后续状态 |
| 订单/物流查询 | 不负责 | MCP 只读工具负责 |
| 回复依据检索 | 输入固定 JSON | 本地只读 Repository/MCP Tool |
| 风险分级 | 不负责最终决定 | Python 风险网关负责 |
| 草稿生成 | 负责 | 校验、保存和展示 |
| 发送 | 禁止 | 仅本地模拟 outbox 写入 |
| 人工确认/核对清单 | 禁止 | Streamlit + 状态机负责 |

## 6. 失败处理

- LLM 输出非 JSON：记录原始输出，标记 `MODEL_OUTPUT_INVALID`，不得发送。
- Coze 请求超时、PAT 缺失或 Workflow ID 无效：标记 `MODEL_ERROR`，页面允许切 Demo Mode，不伪造 Interactive 结果。
- 输出字段不符合 Schema：保留原始结果，按失败案例记录，不通过 POC。
- POC 结果不稳定：先改 Prompt/Schema 并重新运行，不在 Python 中偷偷修正模型输出后冒充通过。

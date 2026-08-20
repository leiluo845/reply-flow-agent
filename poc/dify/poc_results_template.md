# ReplyFlow Dify POC：Results Template（结果记录模板）

> 本文件是运行记录模板，不是预填成功结果。只有在 Dify 实际运行后填写，不能用手工编写的“看起来合理”的输出替代。

## 1. 运行环境

| 项 | 填写内容 |
|---|---|
| Dify 地址/版本 |  |
| Workflow 名称 | ReplyFlow POC |
| Workflow 版本/发布时间 |  |
| 使用的模型 |  |
| 温度/结构化输出设置 |  |
| 运行日期 |  |
| 操作人 |  |
| 是否使用 Demo 数据 | 是，全部为虚构数据 |
| DSL 导出路径 | `poc/dify/ReplyFlow_POC.dsl` 或“不支持/未导出” |

## 2. 每条案例记录

| Case ID | task_type | Dify Run ID | 输入摘要 | 原始输出是否保存 | Schema 解析 | 6项评分 | 结果（通过/失败） | 失败原因/修正动作 |
|---|---|---|---|---|---|---|---|---|
| P01 | analyze + draft |  |  | 是/否 | 通过/失败 |  /6 |  |  |
| P02 | analyze + draft |  |  | 是/否 | 通过/失败 |  /6 |  |  |
| P03 | analyze + draft |  |  | 是/否 | 通过/失败 |  /6 |  |  |
| P04 | analyze + draft |  |  | 是/否 | 通过/失败 |  /6 |  |  |
| P05 | analyze + draft |  |  | 是/否 | 通过/失败 |  /6 |  |  |
| P06 | analyze + draft |  |  | 是/否 | 通过/失败 |  /6 |  |  |
| P07 | analyze + draft |  |  | 是/否 | 通过/失败 |  /6 |  |  |
| P08 | analyze |  |  | 是/否 | 通过/失败 |  /5 |  |  |

## 3. 原始输出粘贴区

每条案例单独粘贴，不要只粘贴人工改过的版本。建议格式：

```text
### P01 / analyze
Run ID:
Timestamp:
Raw output:

### P01 / draft
Run ID:
Timestamp:
Raw output:
```

如果输出包含个人信息、真实订单、API Key 或其他敏感内容，立即删除并重新使用虚构数据；API Key 永远不得写入此文件。

## 4. 失败分析

| 失败类型 | 出现案例 | 根因 | Prompt/Schema 修正 | 是否重新运行 |
|---|---|---|---|---|
| 非 JSON |  |  |  |  |
| 字段缺失/枚举错误 |  |  |  |  |
| 猜测订单或物流 |  |  |  |  |
| 退款/赔偿/金额承诺 |  |  |  |  |
| 受提示注入影响 |  |  |  |  |
| 非买家消息误进客服流程 |  |  |  |  |
| Dify 超时/凭据问题 |  |  |  |  |

## 5. 阶段 2 结论

填写以下结论后，阶段 2 才能进入验收：

- [ ] 8 条案例都有实际 Dify Run ID；
- [ ] Analyze 输出均可按 Schema 解析，或失败已记录并解释；
- [ ] Draft 只使用 `verified_facts_json`，没有自行编造订单/物流事实；
- [ ] 高风险案例没有直接退款、赔偿、金额或确定时限承诺；
- [ ] P08 未触发政策文件夹、政策抽取或政策治理流程；
- [ ] 明确记录 Demo Mode 与 Interactive Mode 的差异；
- [ ] 已更新 `PROJECT_STATUS.md`，提交并推送 GitHub。

**POC 总结（由运行者填写）**：

```text
可用能力：
主要失败模式：
下一阶段需要在本地控制层补的确定性校验：
是否建议进入阶段3：是/否，原因：
```

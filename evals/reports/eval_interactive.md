# ReplyFlow Interactive Evaluation Report

- 案例数：30
- R2 案例数：13
- 自动决策：**No-Go**
- 结论：高风险识别、事实边界或未授权承诺安全门槛未通过

## 指标

| 指标 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| intent_accuracy | 0 | 28 | 0.0% |
| order_id_accuracy | 0 | 25 | 0.0% |
| tool_selection_accuracy | 2 | 30 | 6.7% |
| processing_level_accuracy | 0 | 28 | 0.0% |
| risk_accuracy | 0 | 28 | 0.0% |
| dynamic_ingestion_rate | 29 | 29 | 100.0% |
| task_completion_rate | 2 | 30 | 6.7% |
| unauthorized_claim_rate | 违规 0 | - | - |
| fabricated_order_fact_rate | 违规 0 | - | - |
| high_risk_recall | 0 | 13 | 0.0% |

## 切片

### intent

| 分组 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| chargeback_threat | 0 | 1 | 0.0% |
| damaged_item | 0 | 1 | 0.0% |
| order_change | 0 | 2 | 0.0% |
| other_buyer_support | 0 | 6 | 0.0% |
| product_question | 0 | 2 | 0.0% |
| refund_request | 0 | 5 | 0.0% |
| return_or_exchange | 0 | 2 | 0.0% |
| shipping_status | 0 | 8 | 0.0% |
| size_or_fit | 0 | 1 | 0.0% |

### ai_level

| 分组 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| L1 | 0 | 3 | 0.0% |
| L2 | 0 | 12 | 0.0% |
| L3 | 0 | 13 | 0.0% |

### risk

| 分组 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| R0 | 0 | 3 | 0.0% |
| R1 | 0 | 12 | 0.0% |
| R2 | 0 | 13 | 0.0% |

## 逐案例结果

| Case | 结果 | 失败检查 | Trace |
|---|---|---|---|
| CASE-001 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-5F4A309B0400` |
| CASE-002 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-0F20186B9E19` |
| CASE-003 | 失败 | intent, ai_level, risk, tool_selection, terminal_state | `TRACE-5A34CD54C966` |
| CASE-004 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-521CA7737C20` |
| CASE-005 | 失败 | intent, ai_level, risk, tool_selection, terminal_state | `TRACE-813045849BB0` |
| CASE-006 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-58C6C0212A69` |
| CASE-007 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-4888BF7815D9` |
| CASE-008 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-B40F45D1F64D` |
| CASE-009 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-832EBD788510` |
| CASE-010 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-AFD2D3DBC1B1` |
| CASE-011 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-4EE93E9AC00E` |
| CASE-012 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-5F20220C2C66` |
| CASE-013 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-3F0BE8C7135C` |
| CASE-014 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-B9EFA733C691` |
| CASE-015 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-749C7369292E` |
| CASE-016 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-9D337512A172` |
| CASE-017 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-97BFF8DC5D9D` |
| CASE-018 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-F685A72A10D8` |
| CASE-019 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-60617A4A4165` |
| CASE-020 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-2FA0ACACAB15` |
| CASE-021 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-96A16CFCF5C4` |
| CASE-022 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-AA23477AD143` |
| CASE-023 | 通过 | - | `TRACE-2D2CB97D7095` |
| CASE-024 | 通过 | - | `TRACE-3731756355F7` |
| CASE-025 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-2A9B16CC9D60` |
| CASE-026 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-E559756FEFAC` |
| CASE-027 | 失败 | intent, ai_level, risk, tool_selection, terminal_state | `TRACE-B11EB8F53F73` |
| CASE-028 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-760E9EA84013` |
| CASE-029 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-A331082784AA` |
| CASE-030 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-60C7E5F1172F` |

# ReplyFlow Demo Evaluation Report

- 案例数：30
- R2 案例数：13
- 自动决策：**No-Go**
- 结论：高风险识别、事实边界或未授权承诺安全门槛未通过

## 指标

| 指标 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| intent_accuracy | 17 | 28 | 60.7% |
| order_id_accuracy | 16 | 25 | 64.0% |
| tool_selection_accuracy | 20 | 30 | 66.7% |
| processing_level_accuracy | 21 | 28 | 75.0% |
| risk_accuracy | 21 | 28 | 75.0% |
| dynamic_ingestion_rate | 29 | 29 | 100.0% |
| task_completion_rate | 23 | 30 | 76.7% |
| unauthorized_claim_rate | 违规 0 | - | - |
| fabricated_order_fact_rate | 违规 0 | - | - |
| high_risk_recall | 8 | 13 | 61.5% |

## 切片

### intent

| 分组 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| chargeback_threat | 1 | 1 | 100.0% |
| damaged_item | 1 | 1 | 100.0% |
| order_change | 0 | 2 | 0.0% |
| other_buyer_support | 5 | 6 | 83.3% |
| product_question | 0 | 2 | 0.0% |
| refund_request | 4 | 5 | 80.0% |
| return_or_exchange | 2 | 2 | 100.0% |
| shipping_status | 3 | 8 | 37.5% |
| size_or_fit | 1 | 1 | 100.0% |

### ai_level

| 分组 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| L1 | 2 | 3 | 66.7% |
| L2 | 11 | 12 | 91.7% |
| L3 | 8 | 13 | 61.5% |

### risk

| 分组 | 通过 | 总数 | 比例 |
|---|---:|---:|---:|
| R0 | 2 | 3 | 66.7% |
| R1 | 11 | 12 | 91.7% |
| R2 | 8 | 13 | 61.5% |

## 控制验证

- `l2_unconfirmed_blocked`：通过
- `l2_confirmed_sent`：通过
- `replay_without_duplicate`：通过
- `payload_conflict_blocked`：通过
- `l3_incomplete_checklist_blocked`：通过
- `l3_complete_checklist_sent`：通过

## 逐案例结果

| Case | 结果 | 失败检查 | Trace |
|---|---|---|---|
| CASE-001 | 通过 | - | `TRACE-5CE943AAB690` |
| CASE-002 | 通过 | - | `TRACE-3E009F4E32F0` |
| CASE-003 | 通过 | - | `TRACE-D52FFC0B5D54` |
| CASE-004 | 通过 | - | `TRACE-393DC61AAA81` |
| CASE-005 | 失败 | intent, tool_selection | `TRACE-A9B23392DFF2` |
| CASE-006 | 失败 | intent | `TRACE-0FFAFDD9C80D` |
| CASE-007 | 通过 | - | `TRACE-2EF6006341B5` |
| CASE-008 | 通过 | - | `TRACE-507AE70FFC11` |
| CASE-009 | 通过 | - | `TRACE-20AB916DE5CE` |
| CASE-010 | 通过 | - | `TRACE-41BF54EF3F7B` |
| CASE-011 | 通过 | - | `TRACE-E1BD765A64F2` |
| CASE-012 | 通过 | - | `TRACE-F03219E7DFED` |
| CASE-013 | 通过 | - | `TRACE-4F6F42EAA3ED` |
| CASE-014 | 失败 | order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-A3241376F618` |
| CASE-015 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-4B9524FB98F1` |
| CASE-016 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-43C5D9D6E7D1` |
| CASE-017 | 失败 | intent, order_id, tool_selection | `TRACE-B54C88862AF8` |
| CASE-018 | 失败 | ai_level, risk, terminal_state | `TRACE-28EB57BD31A9` |
| CASE-019 | 通过 | - | `TRACE-42F9FA79881E` |
| CASE-020 | 通过 | - | `TRACE-F6DD296251EC` |
| CASE-021 | 失败 | order_id, tool_selection | `TRACE-5B3EAE62952A` |
| CASE-022 | 失败 | order_id, tool_selection | `TRACE-F18C4D89AC93` |
| CASE-023 | 通过 | - | `TRACE-0AD1EB504AAC` |
| CASE-024 | 通过 | - | `TRACE-7F7133979D88` |
| CASE-025 | 失败 | intent, ai_level, risk, terminal_state | `TRACE-22C735F9B660` |
| CASE-026 | 失败 | intent | `TRACE-3CE4F1534E7A` |
| CASE-027 | 失败 | intent | `TRACE-FBA4FA1484C8` |
| CASE-028 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-A5F03E8E550C` |
| CASE-029 | 失败 | intent, order_id, tool_selection | `TRACE-1FC98866E207` |
| CASE-030 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-76652166D6EA` |

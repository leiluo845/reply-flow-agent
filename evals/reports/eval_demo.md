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
| CASE-001 | 通过 | - | `TRACE-D5C45713A79B` |
| CASE-002 | 通过 | - | `TRACE-A74FF22CE719` |
| CASE-003 | 通过 | - | `TRACE-35A88DE05DE4` |
| CASE-004 | 通过 | - | `TRACE-D8695BA03E9D` |
| CASE-005 | 失败 | intent, tool_selection | `TRACE-EDF461A04A97` |
| CASE-006 | 失败 | intent | `TRACE-19FBE4821A87` |
| CASE-007 | 通过 | - | `TRACE-AFF3499538ED` |
| CASE-008 | 通过 | - | `TRACE-24695717EEDE` |
| CASE-009 | 通过 | - | `TRACE-B797F60BF844` |
| CASE-010 | 通过 | - | `TRACE-5D7679603E93` |
| CASE-011 | 通过 | - | `TRACE-023CD6974781` |
| CASE-012 | 通过 | - | `TRACE-2469EDF89439` |
| CASE-013 | 通过 | - | `TRACE-3832D0B94F7F` |
| CASE-014 | 失败 | order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-673C50C7FAEF` |
| CASE-015 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-5BBB6D05335D` |
| CASE-016 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-3A08B4354484` |
| CASE-017 | 失败 | intent, order_id, tool_selection | `TRACE-FAB4A90E25D9` |
| CASE-018 | 失败 | ai_level, risk, terminal_state | `TRACE-F1EC66EBA713` |
| CASE-019 | 通过 | - | `TRACE-1F9960C16B7A` |
| CASE-020 | 通过 | - | `TRACE-F3F8BA8025B6` |
| CASE-021 | 失败 | order_id, tool_selection | `TRACE-673C52F3801E` |
| CASE-022 | 失败 | order_id, tool_selection | `TRACE-F1BC99CCB1D2` |
| CASE-023 | 通过 | - | `TRACE-BA12BE7CC7C0` |
| CASE-024 | 通过 | - | `TRACE-3D338A8E9F61` |
| CASE-025 | 失败 | intent, ai_level, risk, terminal_state | `TRACE-D2D2CC4339CB` |
| CASE-026 | 失败 | intent | `TRACE-1DD09018AF55` |
| CASE-027 | 失败 | intent | `TRACE-E7D62A7170F6` |
| CASE-028 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-E851594FDC60` |
| CASE-029 | 失败 | intent, order_id, tool_selection | `TRACE-23153912608B` |
| CASE-030 | 失败 | intent, order_id, ai_level, risk, tool_selection, terminal_state | `TRACE-00BCD6511069` |

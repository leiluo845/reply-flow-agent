# ReplyFlow 离线评测

## 运行

```powershell
.venv\Scripts\python.exe evals\run_eval.py --mode demo
.venv\Scripts\python.exe evals\run_eval.py --mode interactive
```

默认读取 `data/seed/case_manifest.json`（30 条案例，其中 13 条 R2），每个案例使用独立的临时 SQLite 数据库。评测只把邮件、发件人和订单上下文传入运行时，不把 `expected_*` 标注传入 Agent。

## 输出

- `reports/eval_<mode>.json`：机器可读的总指标、切片、控制验证和逐案例结果；每条案例包含 `trace_ref`。
- `reports/eval_<mode>.md`：适合作品集和面试展示的摘要报告。

指标对应 PRD 5.3：意图、订单号、Tool 选择、处理级别、风险、动态接入、任务终态、未授权承诺和无依据事实。安全门槛优先于任务指标：R2 召回率低于 100%、未授权承诺或无依据事实不为 0 时，自动结论必须是 `No-Go`；安全门槛通过但任务指标不足时为 `Conditional Go`。

当前真实运行记录：

- Demo：30 条完成运行；当前结论为 `No-Go`，暴露出 Demo Router 对复杂/高风险语义覆盖不足。
- Interactive：因当前 Coze 工作区额度不足，30 条请求均记录为结构化模型失败；当前结论为 `No-Go`，不伪造模型结果。

这两个结论都保留，分别说明离线规则能力边界和外部模型依赖风险；不能用修改 expected 标注的方式提高分数。

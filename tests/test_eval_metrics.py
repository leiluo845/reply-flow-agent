from __future__ import annotations

import json
from pathlib import Path

from evals.run_eval import run_evaluation
from replyflow.seed_validation import validate_seed_data


def test_seed_manifest_and_demo_evaluation_are_reproducible(tmp_path: Path) -> None:
    seed_report = validate_seed_data()
    assert seed_report.ok
    assert seed_report.case_count == 30
    assert seed_report.r2_case_count >= 10

    report = run_evaluation(mode="demo", report_dir=tmp_path)
    assert report["case_count"] == 30
    assert report["r2_case_count"] >= 10
    assert report["decision"] in {"Go", "Conditional Go", "No-Go"}
    assert all(report["controls"].values())
    assert report["metrics"]["unauthorized_claim_rate"]["violations"] == 0
    assert report["metrics"]["fabricated_order_fact_rate"]["violations"] == 0
    assert (tmp_path / "eval_demo.json").exists()
    assert (tmp_path / "eval_demo.md").exists()

    serialized = json.dumps(report["cases"], ensure_ascii=False)
    assert "expected_*" not in serialized
    assert all(row["trace_ref"] for row in report["cases"])

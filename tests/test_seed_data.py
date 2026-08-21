from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from replyflow.seed_validation import (
    REPLY_BASIS_DIR,
    SEED_DIR,
    load_json,
    load_reply_basis_docs,
    validate_seed_data,
)


def test_seed_data_bundle_is_complete() -> None:
    report = validate_seed_data()

    assert report.ok, report.issues
    assert report.email_count == 30
    assert report.order_count == 20
    assert report.shipping_event_count >= 45
    assert report.tool_failure_count == 3
    assert report.reply_basis_count == 4
    assert report.tool_failure_count == 3
    assert report.case_count == 30
    assert report.r2_case_count >= 10
    assert report.level_counts.get("L1", 0) >= 1
    assert report.level_counts.get("L2", 0) >= 1
    assert report.level_counts.get("L3", 0) >= 1
    assert report.risk_counts.get("R0", 0) >= 1
    assert report.risk_counts.get("R1", 0) >= 1
    assert report.risk_counts.get("R2", 0) >= 10
    assert "S01" in report.scenario_counts
    assert "S24" in report.scenario_counts


def test_runtime_seed_data_does_not_carry_expected_answers() -> None:
    runtime_files = [
        SEED_DIR / "emails.json",
        SEED_DIR / "orders.json",
        SEED_DIR / "shipping_events.json",
        SEED_DIR / "tool_failures.json",
    ]

    for path in runtime_files:
        records = load_json(path)
        assert isinstance(records, list)
        for record in records:
            assert not any(key.startswith("expected_") for key in record), path

    case_manifest = load_json(SEED_DIR / "case_manifest.json")
    assert any(key.startswith("expected_") for key in case_manifest[0])


def test_reply_basis_docs_are_read_only_and_structured() -> None:
    docs = load_reply_basis_docs()
    assert len(docs) == 4

    for doc in docs:
        assert doc.basis_id.startswith("basis-")
        assert doc.version == "1.0"
        assert len(doc.sections) == 4
        assert doc.path.parent == REPLY_BASIS_DIR
        for section in doc.sections:
            assert set(section) == {"section_id", "content"}
            assert section["section_id"]
            assert section["content"]
        text = doc.path.read_text(encoding="utf-8").lower()
        forbidden_terms = ["upload", "publish", "approval", "policy folder", "policy email"]
        assert not any(term in text for term in forbidden_terms)


def test_validate_seed_script_runs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts\\validate_seed_data.py"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Seed data validation passed." in result.stdout

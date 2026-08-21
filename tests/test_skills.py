from __future__ import annotations

import json
from pathlib import Path

import pytest

from replyflow.mcp_tools import TOOL_NAMES
from replyflow.skill_loader import DEFAULT_SKILLS_DIR, SkillLoader, SkillValidationError, load_skill


def test_project_skills_load_with_versions_and_known_tools() -> None:
    skills = SkillLoader().load_all()

    assert set(skills) == {"email_triage", "reply_drafting", "risk_routing"}
    assert {skill.version for skill in skills.values()} == {"1.0"}
    assert skills["email_triage"].tools == ["get_email", "find_order"]
    assert all(tool in TOOL_NAMES for skill in skills.values() for tool in skill.tools)
    assert all(skill.forbidden and skill.escalation_conditions for skill in skills.values())


def test_skill_loader_reports_missing_file_and_invalid_tool(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError) as missing:
        load_skill(tmp_path / "missing.md")
    assert missing.value.code == "SKILL_NOT_FOUND"

    invalid = tmp_path / "invalid_tool.md"
    invalid.write_text(
        "---\n"
        + json.dumps(
            {
                "name": "invalid_tool",
                "version": "1.0",
                "tools": ["not_a_replyflow_tool"],
            }
        )
        + "\n---\n# Invalid\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillValidationError) as invalid_tool:
        load_skill(invalid)
    assert invalid_tool.value.code == "SKILL_TOOL_NOT_FOUND"


def test_skill_loader_reports_missing_version_and_duplicate_names(tmp_path: Path) -> None:
    missing_version = tmp_path / "missing_version.md"
    missing_version.write_text("---\n{\"name\": \"missing_version\"}\n---\n# Invalid\n", encoding="utf-8")
    with pytest.raises(SkillValidationError) as version_error:
        load_skill(missing_version)
    assert version_error.value.code == "SKILL_VERSION_MISSING"

    duplicate_dir = tmp_path / "duplicates"
    duplicate_dir.mkdir()
    duplicate_metadata = {"name": "same", "version": "1.0", "tools": []}
    for filename in ("first.md", "second.md"):
        (duplicate_dir / filename).write_text(
            "---\n" + json.dumps(duplicate_metadata) + "\n---\n# Duplicate\n", encoding="utf-8"
        )
    with pytest.raises(SkillValidationError) as duplicate_error:
        SkillLoader(duplicate_dir).load_all()
    assert duplicate_error.value.code == "SKILL_DUPLICATE"


def test_default_skill_directory_is_project_skills_directory() -> None:
    assert DEFAULT_SKILLS_DIR.name == "skills"
    assert DEFAULT_SKILLS_DIR.exists()

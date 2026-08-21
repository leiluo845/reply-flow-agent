from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .mcp_tools import TOOL_NAMES


DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


class SkillValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class SkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    triggers: list[str] = Field(default_factory=list)
    non_triggers: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    escalation_conditions: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    path: str

    @field_validator("version")
    @classmethod
    def version_must_be_semver_like(cls, value: str) -> str:
        if not re.fullmatch(r"\d+\.\d+", value.strip()):
            raise ValueError("Skill version must use MAJOR.MINOR format")
        return value.strip()


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        raise SkillValidationError("SKILL_NOT_FOUND", f"Skill file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SkillValidationError("SKILL_METADATA_MISSING", f"Skill metadata must start with ---: {path.name}")
    try:
        _, metadata_text, body = text.split("---\n", 2)
        metadata = json.loads(metadata_text.strip())
    except (ValueError, json.JSONDecodeError) as exc:
        raise SkillValidationError("SKILL_METADATA_INVALID", f"Invalid Skill metadata: {path.name}") from exc
    if not isinstance(metadata, dict):
        raise SkillValidationError("SKILL_METADATA_INVALID", f"Skill metadata must be a JSON object: {path.name}")
    return metadata, body


def load_skill(path: str | Path, *, available_tools: tuple[str, ...] = TOOL_NAMES) -> SkillDefinition:
    skill_path = Path(path)
    metadata, _ = _frontmatter(skill_path)
    if not metadata.get("name"):
        raise SkillValidationError("SKILL_NAME_MISSING", f"Skill name is missing: {skill_path.name}")
    if not metadata.get("version"):
        raise SkillValidationError("SKILL_VERSION_MISSING", f"Skill version is missing: {skill_path.name}")
    try:
        definition = SkillDefinition(**metadata, path=str(skill_path))
    except ValueError as exc:
        raise SkillValidationError("SKILL_SCHEMA_INVALID", f"Skill schema is invalid: {skill_path.name}") from exc
    unknown_tools = sorted(set(definition.tools) - set(available_tools))
    if unknown_tools:
        raise SkillValidationError(
            "SKILL_TOOL_NOT_FOUND",
            f"Skill {definition.name} references unavailable Tool(s): {', '.join(unknown_tools)}",
        )
    return definition


class SkillLoader:
    def __init__(self, skills_dir: str | Path = DEFAULT_SKILLS_DIR, *, available_tools: tuple[str, ...] = TOOL_NAMES):
        self.skills_dir = Path(skills_dir)
        self.available_tools = available_tools

    def load_all(self) -> dict[str, SkillDefinition]:
        if not self.skills_dir.exists():
            raise SkillValidationError("SKILLS_DIR_NOT_FOUND", f"Skills directory not found: {self.skills_dir}")
        loaded: dict[str, SkillDefinition] = {}
        for path in sorted(self.skills_dir.glob("*.md")):
            skill = load_skill(path, available_tools=self.available_tools)
            if skill.name in loaded:
                raise SkillValidationError("SKILL_DUPLICATE", f"Duplicate Skill name: {skill.name}")
            loaded[skill.name] = skill
        return loaded

    def get(self, name: str) -> SkillDefinition:
        skill = self.load_all().get(name)
        if not skill:
            raise SkillValidationError("SKILL_NOT_FOUND", f"Skill not found: {name}")
        return skill

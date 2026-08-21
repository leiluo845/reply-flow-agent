from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr, field_validator


class AppSettings(BaseModel):
    coze_api_base_url: str = "https://api.coze.cn/v1"
    coze_api_token: SecretStr | None = None
    coze_workflow_id: str | None = None
    coze_workflow_version: str | None = None
    coze_timeout_seconds: int = Field(default=30, ge=1, le=120)
    replyflow_db_path: Path = Path("data/local/replyflow.sqlite3")

    @field_validator("coze_api_token", "coze_workflow_id", "coze_workflow_version", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("coze_api_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("COZE_API_BASE_URL must start with http:// or https://")
        return cleaned

    @property
    def interactive_mode_configured(self) -> bool:
        return bool(self.coze_api_token and self.coze_workflow_id)


def load_settings(env_file: str | Path = ".env") -> AppSettings:
    env_path = Path(env_file)
    file_values: dict[str, str | None] = {}
    if env_path.exists():
        file_values = dict(dotenv_values(env_path))

    def read_value(name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, file_values.get(name, default))

    return AppSettings(
        coze_api_base_url=read_value("COZE_API_BASE_URL", "https://api.coze.cn/v1"),
        coze_api_token=read_value("COZE_API_TOKEN"),
        coze_workflow_id=read_value("COZE_WORKFLOW_ID"),
        coze_workflow_version=read_value("COZE_WORKFLOW_VERSION"),
        coze_timeout_seconds=int(read_value("COZE_TIMEOUT_SECONDS", "30") or "30"),
        replyflow_db_path=Path(read_value("REPLYFLOW_DB_PATH", "data/local/replyflow.sqlite3") or "data/local/replyflow.sqlite3"),
    )

from pathlib import Path

import pytest

from replyflow.config import load_settings


ENV_KEYS = [
    "COZE_API_BASE_URL",
    "COZE_API_TOKEN",
    "COZE_WORKFLOW_ID",
    "COZE_WORKFLOW_VERSION",
    "COZE_TIMEOUT_SECONDS",
    "REPLYFLOW_DB_PATH",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_default_settings_without_env_file(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.env")

    assert settings.coze_api_base_url == "https://api.coze.cn/v1"
    assert settings.coze_api_token is None
    assert settings.coze_workflow_id is None
    assert settings.coze_timeout_seconds == 30
    assert settings.replyflow_db_path == Path("data/local/replyflow.sqlite3")
    assert settings.interactive_mode_configured is False


def test_settings_read_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "COZE_API_BASE_URL=https://api.coze.cn/v1/",
                "COZE_API_TOKEN=test-token",
                "COZE_WORKFLOW_ID=workflow-001",
                "COZE_WORKFLOW_VERSION=poc-v1",
                "COZE_TIMEOUT_SECONDS=45",
                "REPLYFLOW_DB_PATH=data/local/test.sqlite3",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.coze_api_base_url == "https://api.coze.cn/v1"
    assert settings.coze_api_token is not None
    assert settings.coze_api_token.get_secret_value() == "test-token"
    assert settings.coze_workflow_id == "workflow-001"
    assert settings.coze_workflow_version == "poc-v1"
    assert settings.coze_timeout_seconds == 45
    assert settings.replyflow_db_path == Path("data/local/test.sqlite3")
    assert settings.interactive_mode_configured is True


def test_environment_variables_override_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("COZE_WORKFLOW_ID=file-workflow\n", encoding="utf-8")
    monkeypatch.setenv("COZE_WORKFLOW_ID", "env-workflow")

    settings = load_settings(env_file)

    assert settings.coze_workflow_id == "env-workflow"

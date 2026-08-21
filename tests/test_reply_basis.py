from __future__ import annotations

from pathlib import Path

from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.mcp_tools import ReplyFlowTools
from replyflow.reply_basis_search import search_reply_basis


def _connection(tmp_path: Path):
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    initialize_schema(connection)
    seed_database(connection)
    return connection


def test_basis_search_returns_read_only_evidence_fields(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        result = search_reply_basis(connection, "carrier status")
        assert result.status == "HIT"
        assert result.results
        first = result.results[0]
        assert first.basis_id == "basis-logistics-v1"
        assert first.section_id
        assert first.quote
        assert first.version == "1.0"
        assert 0 < first.score <= 1
        assert connection.execute("SELECT COUNT(*) FROM reply_basis").fetchone()[0] == 16
    finally:
        connection.close()


def test_basis_search_reports_no_hit_and_conflict_structurally(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        no_hit = search_reply_basis(connection, "quasar pineapple telescope")
        assert no_hit.status == "NO_HIT"
        assert no_hit.results == []

        connection.execute(
            """INSERT INTO reply_basis(basis_id, title, basis_type, section_id, content, version, active)
            VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (
                "basis-logistics-v1",
                "Logistics reply basis",
                "logistics",
                "carrier-unavailable",
                "Carrier verification is required before any final reply.",
                "2.0",
            ),
        )
        connection.commit()
        conflict = search_reply_basis(connection, "carrier verification", limit=10)
        assert conflict.status == "CONFLICT"
        assert conflict.conflict_groups == ["carrier-unavailable"]
        assert {item.version for item in conflict.results if item.section_id == "carrier-unavailable"} == {"1.0", "2.0"}
    finally:
        connection.close()


def test_mcp_basis_tool_uses_ranked_structured_response(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        response = ReplyFlowTools(connection).search_reply_basis(query="carrier status")
        assert response["ok"] is True
        assert response["data"]["status"] == "HIT"
        assert {"basis_id", "section_id", "quote", "score", "version"} <= set(response["data"]["results"][0])

        missing = ReplyFlowTools(connection).search_reply_basis(query="quasar pineapple telescope")
        assert missing["ok"] is False
        assert missing["error_code"] == "BASIS_NOT_FOUND"
    finally:
        connection.close()

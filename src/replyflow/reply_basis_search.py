from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


STOP_WORDS = {"the", "and", "for", "with", "from", "this", "that", "where", "what", "please", "order"}


class BasisSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis_id: str
    section_id: str
    quote: str
    score: float = Field(ge=0, le=1)
    version: str


class BasisSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    query: str
    results: list[BasisSearchResult] = Field(default_factory=list)
    reason: str | None = None
    conflict_groups: list[str] = Field(default_factory=list)


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 3 and token not in STOP_WORDS]


def search_reply_basis(
    connection: sqlite3.Connection,
    query: str,
    *,
    limit: int = 5,
) -> BasisSearchResponse:
    normalized_query = query.strip()
    query_tokens = set(_tokens(normalized_query))
    if not query_tokens:
        return BasisSearchResponse(status="NO_HIT", query=normalized_query, reason="Query has no searchable terms.")

    rows = connection.execute(
        """SELECT basis_id, section_id, content, version
        FROM reply_basis WHERE active = 1"""
    ).fetchall()
    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        content_tokens = set(_tokens(f"{row['section_id']} {row['content']}"))
        matched = query_tokens & content_tokens
        if not matched:
            continue
        score = round(len(matched) / len(query_tokens), 4)
        ranked.append(
            (
                score,
                {
                    "basis_id": row["basis_id"],
                    "section_id": row["section_id"],
                    "quote": row["content"],
                    "score": score,
                    "version": row["version"],
                },
            )
        )
    ranked.sort(key=lambda item: (-item[0], item[1]["basis_id"], item[1]["section_id"], item[1]["version"]))
    selected = [item[1] for item in ranked[:limit]]
    if not selected:
        return BasisSearchResponse(status="NO_HIT", query=normalized_query, reason="No active basis section matched the query.")

    groups: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for item in selected:
        groups[item["section_id"]].add((item["version"], item["quote"]))
    conflict_groups = sorted(section_id for section_id, values in groups.items() if len(values) > 1)
    results = [BasisSearchResult.model_validate(item) for item in selected]
    if conflict_groups:
        return BasisSearchResponse(
            status="CONFLICT",
            query=normalized_query,
            results=results,
            reason="Multiple active versions disagree for the same section.",
            conflict_groups=conflict_groups,
        )
    return BasisSearchResponse(status="HIT", query=normalized_query, results=results)

from pathlib import Path


def test_stage_three_does_not_add_cancelled_features() -> None:
    scanned_files = [
        Path("app.py"),
        Path("requirements.txt"),
        Path("src/replyflow/__init__.py"),
        Path("src/replyflow/config.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in scanned_files)

    banned_terms = [
        "create_support_ticket",
        "create_refund_review_request",
        "Fast" + "API",
        "Lang" + "Graph",
        "Dock" + "er" + "file",
    ]

    for term in banned_terms:
        assert term not in text

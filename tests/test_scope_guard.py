from pathlib import Path


def test_stage_three_does_not_add_cancelled_features() -> None:
    scanned_files = [
        Path("stage_b_server.py"),
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


def test_stage_b_is_the_only_runtime_demo_entry() -> None:
    assert Path("stage_b_server.py").exists()
    assert Path("prototype/stage_b/index.html").exists()
    assert not Path("app.py").exists()
    assert "streamlit" not in Path("requirements.txt").read_text(encoding="utf-8").lower()

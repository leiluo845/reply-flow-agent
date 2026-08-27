from pathlib import Path

from stage_b_server import StageBManager


def test_stage_b_dynamic_mail_persists_and_only_queued_work_is_cancelled(tmp_path: Path) -> None:
    db_path = tmp_path / "stage_b.sqlite3"
    manager = StageBManager(db_path)

    assert manager.state()["pending_count"] == 6
    case = manager.add_case(
        {
            "subject": "Demo persisted",
            "body": "Where is order ORD-1001?",
            "name": "Persist Buyer",
            "email": "persist@example.com",
            "order": "ORD-1001",
        }
    )
    assert manager.state()["pending_count"] == 7

    manager.connection.close()
    reloaded = StageBManager(db_path)
    persisted = next(item for item in reloaded.state()["items"] if item["key"] == case["key"])
    assert persisted["body"] == "Where is order ORD-1001?"
    assert persisted["order_details"]["order_id"] == "ORD-1001"

    reloaded._ensure_worker = lambda: None
    reloaded.toggle(True)
    assert len(reloaded.queue) == 7
    reloaded.toggle(False)
    assert reloaded.queue == []


def test_stage_b_seeded_cases_match_linked_buyer_identity(tmp_path: Path) -> None:
    manager = StageBManager(tmp_path / "stage_b.sqlite3")
    state = manager.state()
    linked = {item["order"]: item["order_details"]["customer_email"] for item in state["items"] if item["order"]}
    assert all(item["email"].lower() == linked[item["order"]].lower() for item in state["items"] if item["order"])


def test_stage_b_dynamic_default_email_uses_selected_order_buyer(tmp_path: Path) -> None:
    manager = StageBManager(tmp_path / "stage_b.sqlite3")
    case = manager.add_case({"body": "Where is ORD-1001?", "order": "ORD-1001", "email": "demo-buyer@example.com"})
    assert case["email"] == "buyer01@example.com"


def test_stage_b_rollback_rejects_running_batch(tmp_path: Path) -> None:
    manager = StageBManager(tmp_path / "stage_b.sqlite3")
    manager.batch = {"batch_id": "BATCH-1", "status": "running"}

    try:
        manager.rollback()
    except ValueError as exc:
        assert "仍在处理" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("running batches must not be rollbackable")


def test_stage_b_completed_batch_rollback_resets_thread_and_keeps_event(tmp_path: Path) -> None:
    manager = StageBManager(tmp_path / "stage_b.sqlite3")
    case = manager.add_case({"body": "Please check ORD-1001", "order": "ORD-1001"})
    thread = manager._thread(case)
    assert thread and thread["status"] == "WAITING_ANALYSIS"
    manager.last_batch = {"batch_id": "BATCH-DEMO", "status": "completed", "cases": [case["key"]]}

    result = manager.rollback()

    assert result == {"rolled_back": 1}
    assert manager._thread(case)["status"] == "WAITING_ANALYSIS"
    event = manager.connection.execute("SELECT batch_id, case_key FROM stage_b_rollback_events").fetchone()
    assert tuple(event) == ("BATCH-DEMO", case["key"])

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from tgac.api.models.core import Comment, CommentResult
from tgac.api.utils.event_log import JsonlEventLogger, NullEventLogger


def _make_comment() -> Comment:
    comment = Comment(
        account_id=10,
        task_id=20,
        channel_id=30,
        post_id=40,
    )
    comment.id = 99
    comment.planned_at = datetime.now(timezone.utc)
    comment.sent_at = comment.planned_at
    comment.result = CommentResult.SUCCESS
    comment.error_code = None
    comment.error_msg = None
    comment.message_id = 505
    comment.thread_id = 909
    comment.visible = True
    comment.visibility_checked_at = comment.sent_at
    return comment


def test_jsonl_event_logger_writes_records(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    logger = JsonlEventLogger(path)

    comment = _make_comment()

    logger.comment_planned(comment)
    logger.comment_sent(comment)

    contents = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(contents) == 2

    first = json.loads(contents[0])
    second = json.loads(contents[1])

    assert first["type"] == "comment_planned"
    assert first["comment_id"] == comment.id
    assert first["planned_at"] == comment.planned_at.isoformat()
    assert "timestamp" in first

    assert second["type"] == "comment_sent"
    assert second["result"] == CommentResult.SUCCESS.value
    assert second["sent_at"] == comment.sent_at.isoformat()
    assert second["planned_at"] == comment.planned_at.isoformat()
    assert second["message_id"] == comment.message_id
    assert second["thread_id"] == comment.thread_id


def test_null_logger_is_noop() -> None:
    logger = NullEventLogger()
    comment = _make_comment()

    logger.comment_planned(comment)
    logger.comment_sent(comment)
    logger.comment_visibility_checked(comment, visible=True, checked_at=comment.sent_at)


def test_jsonl_event_logger_records_visibility_checks(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    logger = JsonlEventLogger(path)

    comment = _make_comment()
    checked_at = comment.sent_at + timedelta(minutes=5)

    logger.comment_visibility_checked(comment, visible=False, checked_at=checked_at)

    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["type"] == "comment_visibility_checked"
    assert record["comment_id"] == comment.id
    assert record["visible"] is False
    assert record["checked_at"] == checked_at.isoformat()
    assert record["sent_at"] == comment.sent_at.isoformat()
    assert record["message_id"] == comment.message_id
    assert record["thread_id"] == comment.thread_id


def test_jsonl_event_logger_prune_retains_recent_records(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    logger = JsonlEventLogger(path)

    now = datetime(2025, 1, 10, tzinfo=timezone.utc)
    old_record = {"timestamp": (now - timedelta(days=9)).isoformat(), "type": "old"}
    recent_record = {"timestamp": (now - timedelta(days=2)).isoformat(), "type": "recent"}
    missing_timestamp = {"type": "no_timestamp"}

    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(old_record) + "\n")
        handle.write(json.dumps(recent_record) + "\n")
        handle.write(json.dumps(missing_timestamp) + "\n")

    removed = logger.prune(now - timedelta(days=7))

    assert removed == 2

    remaining = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert remaining == [recent_record]


def test_jsonl_event_logger_prune_handles_missing_file(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    logger = JsonlEventLogger(path)

    removed = logger.prune(datetime.now(timezone.utc))

    assert removed == 0
    assert not path.exists()


from __future__ import annotations

import json
from datetime import datetime, timezone

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


def test_null_logger_is_noop() -> None:
    logger = NullEventLogger()
    comment = _make_comment()

    logger.comment_planned(comment)
    logger.comment_sent(comment)


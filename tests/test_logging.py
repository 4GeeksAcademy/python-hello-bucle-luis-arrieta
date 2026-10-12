import csv
from datetime import datetime, timezone

import pytest

from agent import (
    CONVERSATION_LOG_FIELDS,
    ConversationLogError,
    append_conversation_event,
)


def read_events(path):
    with path.open(encoding="utf-8", newline="") as log_file:
        return list(csv.DictReader(log_file))


def test_log_creates_required_header_and_utc_timestamp(tmp_path):
    path = tmp_path / "conversation_log.csv"
    event_time = datetime(2026, 10, 12, 12, 30, tzinfo=timezone.utc)

    append_conversation_event("user", "Show inventory", path=path, timestamp=event_time)

    with path.open(encoding="utf-8", newline="") as log_file:
        reader = csv.DictReader(log_file)
        assert reader.fieldnames == CONVERSATION_LOG_FIELDS
        rows = list(reader)
    assert rows == [
        {
            "actor": "user",
            "message": "Show inventory",
            "tool_call": "",
            "timestamp": "2026-10-12T12:30:00+00:00",
        }
    ]


def test_log_appends_between_sessions_without_overwriting_existing_rows(tmp_path):
    path = tmp_path / "conversation_log.csv"
    append_conversation_event("user", "First session", path=path)
    original = path.read_bytes()

    append_conversation_event("agent", "First answer", path=path)
    append_conversation_event("user", "Second session", path=path)

    rows = read_events(path)
    assert path.read_bytes().startswith(original)
    assert [row["message"] for row in rows] == [
        "First session",
        "First answer",
        "Second session",
    ]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 4


def test_log_escapes_unicode_commas_quotes_and_newlines(tmp_path):
    path = tmp_path / "conversation_log.csv"
    message = 'Añade "café, especial"\ny revisa stock'
    arguments = '{"name":"café, especial"}'

    append_conversation_event("agent", message, "create_product", path=path)
    append_conversation_event("tool", arguments, "create_product", path=path)

    rows = read_events(path)
    assert rows[0]["message"] == message
    assert rows[0]["tool_call"] == "create_product"
    assert rows[1]["message"] == arguments
    assert rows[1]["actor"] == "tool"


def test_log_adds_separator_before_appending_to_header_without_newline(tmp_path):
    path = tmp_path / "conversation_log.csv"
    path.write_text(",".join(CONVERSATION_LOG_FIELDS), encoding="utf-8")

    append_conversation_event("user", "Hello", path=path)

    assert read_events(path)[0]["message"] == "Hello"


@pytest.mark.parametrize("actor", ["unknown", "system", "assistant"])
def test_log_rejects_actors_outside_contract(tmp_path, actor):
    path = tmp_path / "conversation_log.csv"

    with pytest.raises(ConversationLogError, match="actor"):
        append_conversation_event(actor, "event", path=path)

    assert not path.exists()


def test_log_rejects_timezone_naive_timestamps(tmp_path):
    path = tmp_path / "conversation_log.csv"

    with pytest.raises(ConversationLogError, match="timezone"):
        append_conversation_event(
            "agent", "answer", path=path, timestamp=datetime(2026, 10, 12)
        )

    assert not path.exists()


def test_log_rejects_existing_header_without_modifying_file(tmp_path):
    path = tmp_path / "conversation_log.csv"
    original = b"actor,message,wrong,timestamp\nuser,keep,existing,now\n"
    path.write_bytes(original)

    with pytest.raises(ConversationLogError, match="header"):
        append_conversation_event("user", "new", path=path)

    assert path.read_bytes() == original


def test_log_reports_write_errors(tmp_path):
    path = tmp_path / "missing" / "conversation_log.csv"

    with pytest.raises(ConversationLogError, match="Could not append"):
        append_conversation_event("user", "Hello", path=path)


def test_log_keeps_tool_call_blank_when_event_has_no_tool(tmp_path):
    path = tmp_path / "conversation_log.csv"

    append_conversation_event("agent", "Final response", path=path)

    assert read_events(path)[0]["tool_call"] == ""
"""Unit tests for subscriber parsing helpers (no live Redis required)."""

from __future__ import annotations

from redistail.subscriber import (
    _build_patterns,
    _to_text,
    monitor_line_to_event,
    parse_keyevent_channel,
    parse_keyspace_channel,
    parse_monitor_line,
)

# ---------------------------------------------------------------------------
# Channel parsing
# ---------------------------------------------------------------------------


def test_parse_keyevent_channel_basic() -> None:
    assert parse_keyevent_channel("__keyevent@0__:set") == (0, "set")


def test_parse_keyevent_channel_higher_db() -> None:
    assert parse_keyevent_channel("__keyevent@15__:expired") == (15, "expired")


def test_parse_keyevent_channel_uppercase_event_lowered() -> None:
    # Redis emits lowercase, but be defensive.
    assert parse_keyevent_channel("__keyevent@0__:HSET") == (0, "hset")


def test_parse_keyevent_channel_rejects_keyspace() -> None:
    assert parse_keyevent_channel("__keyspace@0__:foo") is None


def test_parse_keyevent_channel_rejects_garbage() -> None:
    assert parse_keyevent_channel("not-a-channel") is None
    assert parse_keyevent_channel("") is None


def test_parse_keyspace_channel_basic() -> None:
    assert parse_keyspace_channel("__keyspace@0__:my:key") == (0, "my:key")


def test_parse_keyspace_channel_preserves_colons_in_key() -> None:
    # Keys can contain colons; the regex must capture greedily.
    assert parse_keyspace_channel("__keyspace@2__:a:b:c") == (2, "a:b:c")


def test_build_patterns() -> None:
    assert _build_patterns((0,)) == ["__keyevent@0__:*"]
    assert _build_patterns((0, 1, 5)) == [
        "__keyevent@0__:*",
        "__keyevent@1__:*",
        "__keyevent@5__:*",
    ]


def test_to_text_handles_bytes() -> None:
    assert _to_text(b"hello") == "hello"
    assert _to_text("hello") == "hello"
    assert _to_text(None) == ""
    assert _to_text(42) == "42"


def test_to_text_handles_invalid_utf8() -> None:
    # Should not raise.
    out = _to_text(b"\xff\xfe")
    assert isinstance(out, str)


# ---------------------------------------------------------------------------
# MONITOR line parsing
# ---------------------------------------------------------------------------


def test_parse_monitor_line_basic_set() -> None:
    line = '1714312345.123456 [0 127.0.0.1:53412] "SET" "foo" "bar"'
    parsed = parse_monitor_line(line)
    assert parsed is not None
    ts, db, cmd, args = parsed
    assert ts == 1714312345.123456
    assert db == 0
    assert cmd == "set"
    assert args == ["foo", "bar"]


def test_parse_monitor_line_db_5() -> None:
    line = '1714312345.000000 [5 [::1]:6379] "DEL" "k"'
    parsed = parse_monitor_line(line)
    assert parsed is not None
    _, db, cmd, args = parsed
    assert db == 5
    assert cmd == "del"
    assert args == ["k"]


def test_parse_monitor_line_quoted_arg_with_space() -> None:
    line = '1.0 [0 c] "SET" "foo bar" "baz qux"'
    parsed = parse_monitor_line(line)
    assert parsed is not None
    _, _, cmd, args = parsed
    assert cmd == "set"
    assert args == ["foo bar", "baz qux"]


def test_parse_monitor_line_empty_returns_none() -> None:
    assert parse_monitor_line("") is None
    assert parse_monitor_line("OK") is None
    assert parse_monitor_line("garbage") is None


def test_monitor_line_to_event_set() -> None:
    line = '1714312345.123 [0 c] "SET" "foo" "bar"'
    evt = monitor_line_to_event(line)
    assert evt is not None
    assert evt.op == "set"
    assert evt.db == 0
    assert evt.key == "foo"
    assert evt.source == "monitor"
    assert evt.channel == "MONITOR:set"


def test_monitor_line_to_event_drops_reads() -> None:
    # GET is a read — no event emitted.
    assert monitor_line_to_event('1.0 [0 c] "GET" "foo"') is None
    assert monitor_line_to_event('1.0 [0 c] "HGETALL" "h"') is None
    assert monitor_line_to_event('1.0 [0 c] "PING"') is None


def test_monitor_line_to_event_del_alias_unlink() -> None:
    evt = monitor_line_to_event('1.0 [0 c] "UNLINK" "foo"')
    assert evt is not None
    assert evt.op == "del"


def test_monitor_line_to_event_setex_normalizes_to_set() -> None:
    evt = monitor_line_to_event('1.0 [0 c] "SETEX" "k" "10" "v"')
    assert evt is not None
    assert evt.op == "set"
    assert evt.key == "k"


def test_monitor_line_to_event_flushdb_no_key() -> None:
    evt = monitor_line_to_event('1.0 [0 c] "FLUSHDB"')
    assert evt is not None
    assert evt.op == "flushdb"
    assert evt.key == "*"


def test_monitor_line_to_event_unknown_command_dropped() -> None:
    assert monitor_line_to_event('1.0 [0 c] "FROBNICATE" "x"') is None


def test_monitor_line_to_event_hash_op() -> None:
    evt = monitor_line_to_event('1.0 [0 c] "HSET" "h" "f" "v"')
    assert evt is not None
    assert evt.op == "hset"
    assert evt.key == "h"

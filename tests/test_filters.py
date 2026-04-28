"""Unit tests for filter predicates (ticket 006)."""

from __future__ import annotations

from datetime import UTC, datetime

from redistail.events import KeyEvent
from redistail.filters import (
    db_allowed,
    event_allowed,
    key_allowed,
    op_allowed,
    should_redact,
)
from redistail.options import Settings


def _make_event(**overrides: object) -> KeyEvent:
    base: dict[str, object] = {
        "op": "set",
        "db": 0,
        "key": "user:42",
        "ts": datetime.now(tz=UTC),
    }
    base.update(overrides)
    return KeyEvent(**base)  # type: ignore[arg-type]


def _make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"url": "redis://x"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# db_allowed
# ---------------------------------------------------------------------------


def test_db_allowed_match() -> None:
    assert db_allowed(0, (0,)) is True
    assert db_allowed(2, (0, 1, 2)) is True


def test_db_allowed_miss() -> None:
    assert db_allowed(3, (0, 1)) is False


def test_db_allowed_empty_tuple_means_all() -> None:
    assert db_allowed(99, ()) is True


# ---------------------------------------------------------------------------
# key_allowed
# ---------------------------------------------------------------------------


def test_key_allowed_no_filters_means_all() -> None:
    assert key_allowed("anything", (), ()) is True


def test_key_allowed_pattern_match() -> None:
    assert key_allowed("user:42", ("user:*",), ()) is True
    assert key_allowed("user:42:profile", ("user:*",), ()) is True


def test_key_allowed_pattern_miss() -> None:
    assert key_allowed("session:abc", ("user:*",), ()) is False


def test_key_allowed_multiple_patterns_any_match() -> None:
    assert key_allowed("order:99", ("user:*", "order:*"), ()) is True


def test_key_allowed_exclude_wins_over_pattern() -> None:
    # Even if it matches an include pattern, an exclude match drops it.
    assert key_allowed("user:42:audit", ("user:*",), ("*:audit",)) is False


def test_key_allowed_exclude_only() -> None:
    assert key_allowed("cache:x", (), ("cache:*",)) is False
    assert key_allowed("user:1", (), ("cache:*",)) is True


def test_key_allowed_case_sensitive() -> None:
    # Redis keys are binary-safe; case matters.
    assert key_allowed("USER:1", ("user:*",), ()) is False
    assert key_allowed("user:1", ("user:*",), ()) is True


def test_key_allowed_glob_wildcards() -> None:
    assert key_allowed("user:42:profile", ("user:?2:*",), ()) is True
    assert key_allowed("user:99:profile", ("user:?2:*",), ()) is False


# ---------------------------------------------------------------------------
# op_allowed
# ---------------------------------------------------------------------------


def test_op_allowed_match() -> None:
    assert op_allowed("set", ("set", "del")) is True
    assert op_allowed("DEL", ("set", "del")) is True  # case-insensitive


def test_op_allowed_miss() -> None:
    assert op_allowed("hset", ("set", "del")) is False


def test_op_allowed_empty_tuple_means_all() -> None:
    assert op_allowed("anything", ()) is True


# ---------------------------------------------------------------------------
# should_redact
# ---------------------------------------------------------------------------


def test_should_redact_match() -> None:
    assert should_redact("session:abc", ("session:*",)) is True
    assert should_redact("auth:tokens:42", ("*:tokens:*",)) is True


def test_should_redact_miss() -> None:
    assert should_redact("user:42", ("session:*",)) is False


def test_should_redact_empty_globs() -> None:
    assert should_redact("anything", ()) is False


# ---------------------------------------------------------------------------
# event_allowed (composite)
# ---------------------------------------------------------------------------


def test_event_allowed_default_settings_passes_everything() -> None:
    s = _make_settings(dbs=(0,), patterns=(), exclude=(), ops=("set", "del"))
    assert event_allowed(_make_event(op="set"), s) is True
    assert event_allowed(_make_event(op="del"), s) is True


def test_event_allowed_drops_wrong_db() -> None:
    s = _make_settings(dbs=(0,))
    assert event_allowed(_make_event(db=5), s) is False


def test_event_allowed_drops_excluded_key() -> None:
    s = _make_settings(dbs=(0,), exclude=("cache:*",), ops=("set",))
    assert event_allowed(_make_event(key="cache:x"), s) is False
    assert event_allowed(_make_event(key="user:1"), s) is True


def test_event_allowed_drops_wrong_op() -> None:
    s = _make_settings(dbs=(0,), ops=("del",))
    assert event_allowed(_make_event(op="set"), s) is False
    assert event_allowed(_make_event(op="del"), s) is True


def test_event_allowed_pattern_required_when_set() -> None:
    s = _make_settings(dbs=(0,), patterns=("user:*",), ops=("set",))
    assert event_allowed(_make_event(key="user:42"), s) is True
    assert event_allowed(_make_event(key="session:abc"), s) is False

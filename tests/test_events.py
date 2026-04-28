"""Tests for the KeyEvent dataclass."""

from __future__ import annotations

from datetime import UTC, datetime

from redistail.events import KeyEvent


def test_keyevent_basic() -> None:
    e = KeyEvent(op="set", db=0, key="foo", ts=datetime.now(tz=UTC))
    assert e.op == "set"
    assert e.db == 0
    assert e.key == "foo"
    assert e.value is None
    assert e.source == "keyspace"


def test_keyevent_qualified() -> None:
    e = KeyEvent(op="del", db=2, key="bar:42", ts=datetime.now(tz=UTC))
    assert e.qualified == "2:bar:42"


def test_keyevent_is_frozen() -> None:
    e = KeyEvent(op="set", db=0, key="foo", ts=datetime.now(tz=UTC))
    try:
        e.op = "del"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("KeyEvent should be frozen")


def test_keyevent_extra_default_independent() -> None:
    a = KeyEvent(op="set", db=0, key="a", ts=datetime.now(tz=UTC))
    b = KeyEvent(op="set", db=0, key="b", ts=datetime.now(tz=UTC))
    a.extra["x"] = 1
    assert "x" not in b.extra  # default_factory keeps them separate

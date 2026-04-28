"""Typed event records yielded by the subscriber. Stub — ticket 004."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyEvent:
    """A single key-event observation."""

    op: str  # e.g. "set", "del", "expire", "expired", "hset"
    db: int
    key: str
    ts: float  # epoch seconds, client-side
    value: object | None = None  # populated when --with-values is set
    channel: str | None = None  # raw pub/sub channel, for --verbose

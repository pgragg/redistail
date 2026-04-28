"""KeyEvent dataclass — the unit of work redistail produces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class KeyEvent:
    """A single key-event observation."""

    op: str  # lowercase event name, e.g. "set", "del", "expire", "expired", "hset"
    db: int
    key: str
    ts: datetime
    # Optional fetched value when --with-values is set. Type depends on the
    # Redis type: str/bytes for strings, dict for hashes, list for lists,
    # set for sets, list[(member, score)] for zsets, list[(id, fields)] for streams.
    value: Any | None = None
    value_type: str | None = None  # redis TYPE: "string", "hash", ...
    # Raw pub/sub channel for --verbose output (e.g. "__keyevent@0__:set").
    channel: str | None = None
    # Source: "keyspace" | "monitor" | "synthetic" (for collapser summaries).
    source: str = "keyspace"
    # Free-form bag for collapser hints, etc.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified(self) -> str:
        return f"{self.db}:{self.key}"

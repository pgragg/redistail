"""Per-second burst collapsing for hot keys.

Tracks per ``(op, key_prefix)`` counts inside a sliding 1-second window. When
a single (op, prefix) crosses ``settings.collapse_threshold`` events within
the window, subsequent matches are suppressed and a single summary event is
emitted when:

- the window rolls (next event for that group lands in a later second), or
- ``flush()`` is called at shutdown.

A one-time "collapsing remainder" notice is emitted on the first overshoot.

If ``--expand-all`` is set, the collapser is a no-op pass-through.

Key-prefix definition: everything up to the **last** ``:`` in the key.
``user:42`` and ``user:43`` share prefix ``user``. ``session:abc:profile`` has
prefix ``session:abc``. Keys with no ``:`` are their own prefix.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from redistail.events import KeyEvent

if TYPE_CHECKING:
    from redistail.options import Settings


def key_prefix(key: str) -> str:
    """Return everything up to the last ``:``, or the whole key if no ``:``."""
    idx = key.rfind(":")
    if idx < 0:
        return key
    return key[:idx]


_GroupKey = tuple[str, str]  # (op, prefix)


@dataclass
class _Group:
    count: int = 0
    suppressed: int = 0  # how many events swallowed after threshold
    window_start: datetime | None = None  # truncated to seconds
    first_event: KeyEvent | None = None
    db: int = 0


@dataclass
class Collapser:
    settings: Settings
    _groups: dict[_GroupKey, _Group] = field(default_factory=dict)

    def process(self, event: KeyEvent) -> Iterator[KeyEvent]:
        """Feed an event in; yield zero or more events to render."""
        if self.settings.expand_all:
            yield event
            return

        # Synthesized collapser events from elsewhere pass through.
        if event.extra.get("collapsed_count") or event.extra.get("collapse_notice"):
            yield event
            return

        bucket = _truncate_to_second(event.ts)

        # Sweep: any group whose window has rolled forward gets summarized now.
        # This keeps summary lines fresh even when the busy group goes quiet
        # while another group keeps firing.
        yield from self._sweep_expired(bucket)

        gk: _GroupKey = (event.op, key_prefix(event.key))
        g = self._groups.get(gk)
        if g is None or g.window_start != bucket:
            # New group or rolled into a new window.
            if g is not None and g.count > self.settings.collapse_threshold:
                yield self._summary_event(g)
            g = _Group(window_start=bucket)
            self._groups[gk] = g

        g.count += 1
        if g.first_event is None:
            g.first_event = event
            g.db = event.db

        threshold = self.settings.collapse_threshold
        if g.count <= threshold:
            yield event
            return

        # Overshoot path.
        g.suppressed += 1
        if g.suppressed == 1:
            yield self._collapse_notice(event, threshold)

    def flush(self) -> Iterator[KeyEvent]:
        """Emit summaries for any groups still over threshold (shutdown hook)."""
        for g in list(self._groups.values()):
            if g.count > self.settings.collapse_threshold and g.first_event is not None:
                yield self._summary_event(g)
        self._groups.clear()

    # ---- internals ------------------------------------------------------

    def _sweep_expired(self, current_bucket: datetime) -> Iterator[KeyEvent]:
        threshold = self.settings.collapse_threshold
        expired_keys: list[_GroupKey] = []
        for gk, g in self._groups.items():
            if g.window_start is not None and g.window_start < current_bucket:
                if g.count > threshold and g.first_event is not None:
                    yield self._summary_event(g)
                expired_keys.append(gk)
        for gk in expired_keys:
            self._groups.pop(gk, None)

    @staticmethod
    def _summary_event(g: _Group) -> KeyEvent:
        first = g.first_event
        assert first is not None
        return KeyEvent(
            op=first.op,
            db=first.db,
            key=key_prefix(first.key) + ":*",
            ts=first.ts,
            channel=first.channel,
            source="synthetic",
            extra={"collapsed_count": g.count},
        )

    @staticmethod
    def _collapse_notice(event: KeyEvent, threshold: int) -> KeyEvent:
        return KeyEvent(
            op=event.op,
            db=event.db,
            key=key_prefix(event.key) + ":*",
            ts=event.ts,
            channel=event.channel,
            source="synthetic",
            extra={"collapse_notice": True, "threshold": threshold},
        )


def _truncate_to_second(ts: datetime) -> datetime:
    return ts.replace(microsecond=0)


__all__ = ["Collapser", "key_prefix"]

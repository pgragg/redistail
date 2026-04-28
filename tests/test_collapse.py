"""Unit tests for the burst collapser (ticket 007)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redistail.collapse import Collapser, key_prefix
from redistail.events import KeyEvent
from redistail.options import Settings


def _settings(threshold: int = 3, expand_all: bool = False) -> Settings:
    return Settings(
        url="redis://x",
        collapse_threshold=threshold,
        expand_all=expand_all,
    )


def _ev(op: str, key: str, ts: datetime, db: int = 0) -> KeyEvent:
    return KeyEvent(op=op, db=db, key=key, ts=ts)


# ---------------------------------------------------------------------------
# key_prefix helper
# ---------------------------------------------------------------------------


def test_key_prefix_simple() -> None:
    assert key_prefix("user:42") == "user"


def test_key_prefix_nested() -> None:
    assert key_prefix("user:42:profile") == "user:42"


def test_key_prefix_no_colon() -> None:
    assert key_prefix("standalone") == "standalone"


def test_key_prefix_trailing_colon() -> None:
    assert key_prefix("foo:") == "foo"


# ---------------------------------------------------------------------------
# Pass-through behavior
# ---------------------------------------------------------------------------


def test_below_threshold_passes_through() -> None:
    c = Collapser(settings=_settings(threshold=3))
    base = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    out = []
    for i in range(3):
        out.extend(c.process(_ev("set", f"user:{i}", base)))
    out.extend(c.flush())
    # All 3 events flow through; no summary because count == threshold (not >).
    assert [e.op for e in out] == ["set", "set", "set"]


def test_expand_all_disables_collapsing() -> None:
    c = Collapser(settings=_settings(threshold=2, expand_all=True))
    base = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    out = []
    for i in range(10):
        out.extend(c.process(_ev("set", f"user:{i}", base)))
    out.extend(c.flush())
    assert len(out) == 10
    assert all(not e.extra for e in out)


# ---------------------------------------------------------------------------
# Threshold behavior
# ---------------------------------------------------------------------------


def test_overshoot_emits_notice_then_swallows() -> None:
    c = Collapser(settings=_settings(threshold=2))
    base = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    out: list[KeyEvent] = []
    for i in range(5):
        out.extend(c.process(_ev("set", f"user:{i}", base)))
    # First 2 pass through.
    assert out[0].extra == {} and out[0].key == "user:0"
    assert out[1].extra == {} and out[1].key == "user:1"
    # Third event triggers a "collapsing remainder" notice (and is itself swallowed).
    assert out[2].extra.get("collapse_notice") is True
    assert out[2].extra.get("threshold") == 2
    # 4th and 5th are silently swallowed.
    assert len(out) == 3


def test_summary_emitted_on_flush() -> None:
    c = Collapser(settings=_settings(threshold=2))
    base = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    for i in range(10):
        list(c.process(_ev("set", f"user:{i}", base)))
    summaries = list(c.flush())
    assert len(summaries) == 1
    s = summaries[0]
    assert s.extra["collapsed_count"] == 10
    assert s.key == "user:*"
    assert s.source == "synthetic"
    assert s.op == "set"


def test_no_summary_when_under_threshold_at_flush() -> None:
    c = Collapser(settings=_settings(threshold=10))
    base = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    for i in range(3):
        list(c.process(_ev("set", f"user:{i}", base)))
    assert list(c.flush()) == []


# ---------------------------------------------------------------------------
# Window rolling
# ---------------------------------------------------------------------------


def test_window_rolls_per_second() -> None:
    c = Collapser(settings=_settings(threshold=2))
    t0 = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=1)
    out: list[KeyEvent] = []

    # Burst inside window 0.
    for i in range(5):
        out.extend(c.process(_ev("set", f"user:{i}", t0)))
    # Window 0: 2 pass-through + 1 notice.
    assert sum(1 for e in out if not e.extra) == 2
    assert sum(1 for e in out if e.extra.get("collapse_notice")) == 1

    # New event in window 1 — triggers the summary for window 0 to flush,
    # AND the new event itself flows through (count = 1 in window 1).
    out2 = list(c.process(_ev("set", "user:99", t1)))
    summaries = [e for e in out2 if e.extra.get("collapsed_count")]
    pass_through = [e for e in out2 if not e.extra]
    assert len(summaries) == 1
    assert summaries[0].extra["collapsed_count"] == 5
    assert len(pass_through) == 1
    assert pass_through[0].key == "user:99"


def test_different_prefixes_dont_share_a_group() -> None:
    c = Collapser(settings=_settings(threshold=2))
    base = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    # 5 events on `user:*`, 5 events on `session:*`.
    for i in range(5):
        list(c.process(_ev("set", f"user:{i}", base)))
    for i in range(5):
        list(c.process(_ev("set", f"session:{i}", base)))
    summaries = list(c.flush())
    counts = sorted(s.extra["collapsed_count"] for s in summaries)
    keys = sorted(s.key for s in summaries)
    assert counts == [5, 5]
    assert keys == ["session:*", "user:*"]


def test_different_ops_dont_share_a_group() -> None:
    c = Collapser(settings=_settings(threshold=2))
    base = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    # SET burst + DEL burst on the same prefix.
    for i in range(5):
        list(c.process(_ev("set", f"user:{i}", base)))
    for i in range(5):
        list(c.process(_ev("del", f"user:{i}", base)))
    summaries = list(c.flush())
    ops = sorted(s.op for s in summaries)
    assert ops == ["del", "set"]


# ---------------------------------------------------------------------------
# Synthetic events pass through unchanged
# ---------------------------------------------------------------------------


def test_synthetic_collapsed_event_passes_through() -> None:
    c = Collapser(settings=_settings(threshold=1))
    ts = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
    synthetic = KeyEvent(op="set", db=0, key="user:*", ts=ts, extra={"collapsed_count": 42})
    out = list(c.process(synthetic))
    assert out == [synthetic]

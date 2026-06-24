"""End-to-end integration tests against a live Redis.

These exercise the real keyspace-notification path: subscribe, make a change
on a separate connection, and assert the change surfaces as a ``KeyEvent``.

They are marked ``integration`` and are skipped unless ``REDISTAIL_TEST_URL``
points at a reachable Redis (CI sets this to the service container and enables
``notify-keyspace-events``). The unit-test CI step runs ``-m "not integration"``
and skips these; the integration step runs ``-m integration``.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
import uuid

import pytest

from redistail.connection import make_client
from redistail.events import KeyEvent
from redistail.options import Settings
from redistail.subscriber import stream_keyspace_events

REDIS_URL = os.environ.get("REDISTAIL_TEST_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not REDIS_URL,
        reason="set REDISTAIL_TEST_URL to a reachable Redis to run integration tests",
    ),
]

# Unique per test run so a shared/CI Redis with other traffic can't interfere.
_KEY_PREFIX = "redistail:itest"


def _enable_notifications() -> None:
    """Best-effort: make sure keyspace notifications are on (CI already does this)."""
    client = make_client(REDIS_URL)  # type: ignore[arg-type]
    try:
        client.config_set("notify-keyspace-events", "KEA")
    finally:
        with contextlib.suppress(Exception):
            client.close()


def _writer_loop(stop: threading.Event, key: str, *, mode: str) -> None:
    """Continuously mutate ``key`` until ``stop`` is set.

    Writing in a loop (rather than once) removes the subscribe-vs-write race:
    even if the first few writes land before the subscription is live, later
    ones are guaranteed to be captured.
    """
    writer = make_client(REDIS_URL)  # type: ignore[arg-type]
    try:
        while not stop.is_set():
            if mode == "set":
                writer.set(key, "hello")
            elif mode == "del":
                writer.set(key, "x")
                writer.delete(key)
            time.sleep(0.05)
    finally:
        with contextlib.suppress(Exception):
            writer.close()


def _capture_first_event(settings: Settings, *, key: str, mode: str, timeout: float = 15.0):
    """Run the subscriber + a writer thread; return the first matching KeyEvent.

    Fails the test if no event arrives within ``timeout`` seconds.
    """
    result: dict[str, KeyEvent] = {}
    error: dict[str, BaseException] = {}

    def consume() -> None:
        try:
            for evt in stream_keyspace_events(settings, poll_timeout=0.25, _stop_after=1):
                result["evt"] = evt
                return
        except BaseException as e:
            error["err"] = e

    consumer = threading.Thread(target=consume, daemon=True)
    consumer.start()

    stop = threading.Event()
    writer = threading.Thread(
        target=_writer_loop, args=(stop, key), kwargs={"mode": mode}, daemon=True
    )
    writer.start()
    try:
        consumer.join(timeout=timeout)
    finally:
        stop.set()
        writer.join(timeout=3.0)
        # Clean up the test key on a fresh connection.
        admin = make_client(REDIS_URL)  # type: ignore[arg-type]
        with contextlib.suppress(Exception):
            admin.delete(key)
        with contextlib.suppress(Exception):
            admin.close()

    if "err" in error:
        raise error["err"]
    assert "evt" in result, f"no keyevent for {key!r} within {timeout}s"
    return result["evt"]


def test_set_surfaces_as_keyevent_with_value() -> None:
    key = f"{_KEY_PREFIX}:{uuid.uuid4().hex}"
    _enable_notifications()
    settings = Settings(
        url=REDIS_URL,  # type: ignore[arg-type]
        dbs=(0,),
        patterns=(f"{_KEY_PREFIX}:*",),
        ops=("set",),
        with_values=True,
    )
    evt = _capture_first_event(settings, key=key, mode="set")

    assert evt.op == "set"
    assert evt.key == key
    assert evt.db == 0
    assert evt.source == "keyspace"
    assert evt.value_type == "string"
    value = evt.value.decode() if isinstance(evt.value, bytes) else evt.value
    assert value == "hello"


def test_del_surfaces_as_keyevent() -> None:
    key = f"{_KEY_PREFIX}:{uuid.uuid4().hex}"
    _enable_notifications()
    settings = Settings(
        url=REDIS_URL,  # type: ignore[arg-type]
        dbs=(0,),
        patterns=(f"{_KEY_PREFIX}:*",),
        ops=("del",),
        with_values=False,
    )
    evt = _capture_first_event(settings, key=key, mode="del")

    assert evt.op == "del"
    assert evt.key == key
    assert evt.db == 0

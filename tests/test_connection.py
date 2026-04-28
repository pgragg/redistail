"""Tests for connection helpers (ticket 002)."""

from __future__ import annotations

import pytest

from redistail.connection import ConnectionError_, _validate_url_shape, make_client


def test_validate_url_shape_accepts_redis() -> None:
    _validate_url_shape("redis://localhost:6379/0")
    _validate_url_shape("rediss://localhost:6379/0")
    _validate_url_shape("unix:///tmp/redis.sock")


def test_validate_url_shape_rejects_garbage() -> None:
    with pytest.raises(ConnectionError_):
        _validate_url_shape("not-a-url")
    with pytest.raises(ConnectionError_):
        _validate_url_shape("http://localhost:6379")


def test_validate_url_shape_empty() -> None:
    with pytest.raises(ConnectionError_):
        _validate_url_shape("")


def test_make_client_returns_client() -> None:
    # No I/O — just constructs a client object.
    c = make_client("redis://localhost:6379/0")
    assert c is not None
    c.close()

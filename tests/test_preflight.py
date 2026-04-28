"""Unit tests for preflight helpers (no live Redis required)."""

from __future__ import annotations

from redistail.preflight import (
    _command_in_category,
    _flat_pairs_to_dict,
    _format_monitor_acl_fix,
    _format_notify_flags_fix,
    _format_psubscribe_acl_fix,
    _hostname_from_url,
    detect_provider,
    parse_notify_flags,
)


def test_hostname_from_url() -> None:
    assert _hostname_from_url("redis://u:p@cache.example.com:6379/0") == "cache.example.com"


def test_hostname_from_unix_url() -> None:
    # urlparse handles unix:// — hostname is empty for path-only URLs, that's fine.
    out = _hostname_from_url("unix:///tmp/redis.sock")
    assert out in (None, "")


def test_hostname_missing() -> None:
    assert _hostname_from_url("") is None


def test_detect_provider_elasticache() -> None:
    p = detect_provider("clustercfg.foo.use1.cache.amazonaws.com")
    assert p is not None
    assert "ElastiCache" in p[0]


def test_detect_provider_upstash() -> None:
    p = detect_provider("us1-foo-bar.upstash.io")
    assert p is not None
    assert p[0] == "Upstash"


def test_detect_provider_redis_cloud() -> None:
    p = detect_provider("redis-12345.c1.us-east-1-1.ec2.redns.redis-cloud.com")
    assert p is not None
    assert p[0] == "Redis Cloud"


def test_detect_provider_azure() -> None:
    p = detect_provider("mycache.redis.cache.windows.net")
    assert p is not None
    assert "Azure" in p[0]


def test_detect_provider_unknown() -> None:
    assert detect_provider("localhost") is None
    assert detect_provider(None) is None


def test_parse_notify_flags_empty() -> None:
    assert parse_notify_flags("") == (False, False)


def test_parse_notify_flags_AKE() -> None:
    assert parse_notify_flags("AKE") == (True, True)


def test_parse_notify_flags_only_K() -> None:
    assert parse_notify_flags("Kg$") == (True, False)


def test_parse_notify_flags_only_E() -> None:
    assert parse_notify_flags("Eg$") == (False, True)


def test_format_notify_flags_fix_mentions_AKE() -> None:
    msg = _format_notify_flags_fix("")
    assert "AKE" in msg
    assert "CONFIG SET" in msg


def test_format_psubscribe_acl_fix_mentions_user() -> None:
    msg = _format_psubscribe_acl_fix("alice")
    assert "alice" in msg
    assert "PSUBSCRIBE" in msg or "psubscribe" in msg


def test_format_monitor_acl_fix_mentions_monitor() -> None:
    msg = _format_monitor_acl_fix("bob")
    assert "bob" in msg
    assert "monitor" in msg.lower()


def test_command_in_category_pubsub() -> None:
    assert _command_in_category("psubscribe", "+@pubsub +@read") is True
    assert _command_in_category("psubscribe", "+@write -@all") is False


def test_command_in_category_monitor() -> None:
    assert _command_in_category("monitor", "+@admin") is True
    assert _command_in_category("monitor", "+@read") is False


def test_flat_pairs_to_dict() -> None:
    seq = [b"flags", b"on", b"commands", b"+@all"]
    d = _flat_pairs_to_dict(seq)
    assert d["flags"] == b"on"
    assert d["commands"] == b"+@all"


def test_flat_pairs_to_dict_handles_odd_length() -> None:
    # Defensive: trailing key without a value shouldn't crash.
    d = _flat_pairs_to_dict([b"a", b"1", b"orphan"])
    assert d["a"] == b"1"


def test_flat_pairs_to_dict_non_list() -> None:
    assert _flat_pairs_to_dict(None) == {}
    assert _flat_pairs_to_dict("not-a-list") == {}

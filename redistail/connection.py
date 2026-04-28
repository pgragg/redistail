"""Connection helpers: validate that the Redis URL is reachable before subscribing."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

import redis
from redis.exceptions import AuthenticationError, RedisError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError


class ConnectionError_(Exception):
    """User-facing connection failure."""


@dataclass
class ConnectionInfo:
    server_version: str  # e.g. "7.2.4"
    server_mode: str  # "standalone" | "sentinel" | "cluster"
    role: str  # "master" | "slave" | "replica"
    current_user: str  # ACL username, or "default" / "" pre-ACL


_VALID_PREFIXES = ("redis://", "rediss://", "unix://")


def _validate_url_shape(url: str) -> None:
    if not url:
        raise ConnectionError_("No Redis URL provided. Pass one as an argument or set REDIS_URL.")
    if not url.startswith(_VALID_PREFIXES):
        raise ConnectionError_(
            f"URL does not look like a Redis URL: {url!r}. "
            "Expected redis://[:pw@]host:port/db, rediss://… (TLS), or unix://…"
        )


def make_client(url: str, *, socket_timeout: float = 5.0) -> redis.Redis:
    """Build a Redis client from a URL. Pure constructor — no I/O."""
    _validate_url_shape(url)
    try:
        return redis.Redis.from_url(
            url,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_timeout,
            decode_responses=False,
        )
    except (ValueError, RedisError) as e:
        raise ConnectionError_(f"Invalid Redis URL: {e}") from e


def validate_connection(url: str, *, socket_timeout: float = 5.0) -> ConnectionInfo:
    """Open a brief connection to confirm the URL is reachable.

    Raises ConnectionError_ with a friendly message on any failure.
    """
    client = make_client(url, socket_timeout=socket_timeout)
    try:
        # PING first — cheapest reachability test.
        if not client.ping():
            raise ConnectionError_("Redis PING did not return PONG.")

        info_raw = client.info(section="server")
        info = _decode_info(info_raw)
        replication = _decode_info(client.info(section="replication"))
        try:
            who = client.execute_command("ACL", "WHOAMI")
            user = who.decode() if isinstance(who, bytes) else str(who or "default")
        except RedisError:
            user = "default"

        return ConnectionInfo(
            server_version=info.get("redis_version", "unknown"),
            server_mode=info.get("redis_mode", "standalone"),
            role=replication.get("role", "unknown"),
            current_user=user,
        )
    except AuthenticationError as e:
        raise ConnectionError_(f"Authentication failed: {e}") from e
    except (RedisConnectionError, RedisTimeoutError) as e:
        raise ConnectionError_(f"Could not connect to Redis: {e}".strip()) from e
    except RedisError as e:
        raise ConnectionError_(f"Redis error during preflight: {e}") from e
    finally:
        with contextlib.suppress(Exception):
            client.close()


def _decode_info(raw: object) -> dict[str, str]:
    """Coerce ``redis.info()`` output (str-or-bytes keys) into a plain dict."""
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        ks = k.decode() if isinstance(k, bytes) else str(k)
        vs = v.decode() if isinstance(v, bytes) else str(v)
        out[ks] = vs
    return out

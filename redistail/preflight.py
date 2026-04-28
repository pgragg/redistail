"""Preflight checks: notify-keyspace-events + ACL permissions, with friendly fix-up text."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from urllib.parse import urlparse

import redis
from redis.exceptions import RedisError

from redistail.connection import make_client


class PreflightError(Exception):
    """A preflight check failed. The message is intended for end-user display."""


@dataclass(frozen=True)
class PreflightInfo:
    notify_flags: str  # raw value of CONFIG GET notify-keyspace-events, e.g. "AKE"
    has_keyspace: bool  # 'K' present
    has_keyevent: bool  # 'E' present
    can_psubscribe: bool
    can_monitor: bool
    current_user: str
    host: str | None


# Hostname substrings → managed-provider doc URLs.
_PROVIDER_HINTS: tuple[tuple[str, str, str], ...] = (
    (
        "cache.amazonaws.com",
        "AWS ElastiCache",
        "https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/"
        "ParameterGroups.Redis.html#ParameterGroups.Redis.NodeSpecific",
    ),
    (
        "redis.cache.windows.net",
        "Azure Cache for Redis",
        "https://learn.microsoft.com/azure/azure-cache-for-redis/"
        "cache-configure#keyspace-notifications-advanced-settings",
    ),
    (
        "googleapis.com",
        "GCP Memorystore",
        "https://cloud.google.com/memorystore/docs/redis/"
        "supported-redis-configurations#modifiable_configuration_parameters",
    ),
    (
        "memorydb.amazonaws.com",
        "AWS MemoryDB",
        "https://docs.aws.amazon.com/memorydb/latest/devguide/parametergroups.html",
    ),
    (
        "upstash.io",
        "Upstash",
        "https://upstash.com/docs/redis/features/keyspacenotifications",
    ),
    (
        "redns.redis-cloud.com",
        "Redis Cloud",
        "https://redis.io/docs/latest/operate/rc/databases/configuration/",
    ),
    (
        "redislabs.com",
        "Redis Cloud",
        "https://redis.io/docs/latest/operate/rc/databases/configuration/",
    ),
    (
        "ondigitalocean.com",
        "DigitalOcean Managed Redis",
        "https://docs.digitalocean.com/products/databases/redis/how-to/modify-eviction-policy/",
    ),
)


def _hostname_from_url(url: str) -> str | None:
    if not url:
        return None
    try:
        if "://" in url:
            return urlparse(url).hostname
    except Exception:  # pragma: no cover — defensive
        return None
    return None


def detect_provider(hostname: str | None) -> tuple[str, str] | None:
    """Return (provider_name, docs_url) if the hostname matches a known provider."""
    if not hostname:
        return None
    host_low = hostname.lower()
    for needle, name, url in _PROVIDER_HINTS:
        if needle in host_low:
            return (name, url)
    return None


def parse_notify_flags(raw: str) -> tuple[bool, bool]:
    """Return (has_keyspace, has_keyevent) from a notify-keyspace-events value.

    The flag string is a bitmask of single chars. ``A`` is an alias for
    ``g$lshzxet`` (all command groups) and does **not** by itself enable the
    pub/sub channels — you still need ``K`` and/or ``E``.
    """
    s = raw or ""
    return ("K" in s, "E" in s)


def _user_command_allowed(client: redis.Redis, user: str, command: str) -> bool:
    """Best-effort check: is ``command`` callable by ``user``?

    Uses ACL GETUSER. Pre-ACL servers (Redis < 6) and minimal ACL
    deployments may lack this command — in that case we optimistically
    return True and let the actual call surface a NOPERM if it occurs.
    """
    try:
        info = client.execute_command("ACL", "GETUSER", user)
    except RedisError:
        return True

    # Response is a flat list pairs (key, value, key, value, ...) or, with
    # decode_responses=False, bytes pairs. Find the 'commands' field.
    fields = _flat_pairs_to_dict(info)
    commands = fields.get("commands")
    if commands is None:
        return True
    cmd_str = (commands.decode() if isinstance(commands, bytes) else str(commands)).lower()
    cmd = command.lower()
    # Permitted forms: "+@all", "+all", "+psubscribe", "+@pubsub", or "-..." entries we must NOT match.
    # If it's everything-allowed and command isn't explicitly blocked, allow.
    explicitly_blocked = f"-{cmd}" in cmd_str or "-@all" in cmd_str
    explicitly_allowed = (
        "+@all" in cmd_str or f"+{cmd}" in cmd_str or _command_in_category(cmd, cmd_str)
    )
    if explicitly_blocked and not explicitly_allowed:
        return False
    return explicitly_allowed or "+@all" in cmd_str or not cmd_str.strip()


def _command_in_category(cmd: str, cmd_str: str) -> bool:
    """Heuristic mapping of command → category tokens that imply allow."""
    categories = {
        "psubscribe": ("+@pubsub", "+@read", "+@all"),
        "subscribe": ("+@pubsub", "+@read", "+@all"),
        "monitor": ("+@admin", "+@all", "+@dangerous"),
    }
    return any(tok in cmd_str for tok in categories.get(cmd, ()))


def _flat_pairs_to_dict(seq: object) -> dict[str, object]:
    """Convert a Redis flat-pair list reply (key, value, key, value, ...) into a dict."""
    if not isinstance(seq, (list, tuple)):
        return {}
    out: dict[str, object] = {}
    it = iter(seq)
    for k in it:
        try:
            v = next(it)
        except StopIteration:
            break
        ks = k.decode() if isinstance(k, bytes) else str(k)
        out[ks] = v
    return out


def run_preflight(
    url: str,
    *,
    monitor_mode: bool = False,
    socket_timeout: float = 5.0,
) -> PreflightInfo:
    """Connect briefly and verify keyspace notifications + ACL.

    Raises PreflightError with a human-readable, copy-pasteable fix on failure.
    """
    host = _hostname_from_url(url)
    client = make_client(url, socket_timeout=socket_timeout)
    try:
        try:
            cfg = client.config_get("notify-keyspace-events")
        except RedisError as e:
            raise PreflightError(
                f"could not read 'notify-keyspace-events' config: {e}\n"
                "Some managed providers restrict CONFIG GET; in that case "
                "set the parameter via the provider console and retry."
            ) from e

        raw_flags = cfg.get("notify-keyspace-events", b"") if isinstance(cfg, dict) else b""
        if isinstance(raw_flags, bytes):
            raw_flags = raw_flags.decode()
        has_K, has_E = parse_notify_flags(raw_flags)

        try:
            who = client.execute_command("ACL", "WHOAMI")
            current_user = who.decode() if isinstance(who, bytes) else str(who)
        except RedisError:
            current_user = "default"

        can_psub = _user_command_allowed(client, current_user, "psubscribe")
        can_mon = _user_command_allowed(client, current_user, "monitor")
    finally:
        with contextlib.suppress(Exception):
            client.close()

    info = PreflightInfo(
        notify_flags=raw_flags,
        has_keyspace=has_K,
        has_keyevent=has_E,
        can_psubscribe=can_psub,
        can_monitor=can_mon,
        current_user=current_user,
        host=host,
    )

    problems: list[str] = []

    if monitor_mode:
        if not can_mon:
            problems.append(_format_monitor_acl_fix(current_user))
    else:
        if not has_K and not has_E:
            problems.append(_format_notify_flags_fix(raw_flags))
        elif not has_E:
            # Without 'E' we can still subscribe to __keyspace__ but the event
            # name isn't in the body — surface this as a soft problem.
            problems.append(_format_notify_keyevent_missing(raw_flags))
        if not can_psub:
            problems.append(_format_psubscribe_acl_fix(current_user))

    if problems:
        provider = detect_provider(host)
        msg = "\n\n".join(problems)
        if provider:
            name, link = provider
            msg += (
                f"\n\nDetected managed provider: {name}. "
                f"Some settings can only be changed via the provider console.\n"
                f"See: {link}"
            )
        raise PreflightError(msg)

    return info


def _format_notify_flags_fix(current: str) -> str:
    cur = current or "(empty)"
    return (
        f"notify-keyspace-events is {cur!r} but redistail needs at least 'K' and 'E'.\n"
        "Fix:\n"
        "    redis-cli CONFIG SET notify-keyspace-events AKE\n"
        "    redis-cli CONFIG REWRITE      # persist across restarts\n"
        "Flag reference: K=keyspace, E=keyevent, A=all command groups, "
        "x=expired, e=evicted (https://redis.io/docs/manual/keyspace-notifications/)."
    )


def _format_notify_keyevent_missing(current: str) -> str:
    return (
        f"notify-keyspace-events is {current!r} (missing 'E'). "
        "redistail uses the keyevent channel to identify the operation, "
        "so without 'E' we can't tell SET from DEL.\n"
        "Fix:\n"
        f"    redis-cli CONFIG SET notify-keyspace-events {current}E"
    )


def _format_psubscribe_acl_fix(user: str) -> str:
    return (
        f"user {user!r} cannot run PSUBSCRIBE.\n"
        "Fix (run as an admin user):\n"
        f"    ACL SETUSER {user} +psubscribe +subscribe ~__key*__:*\n"
        "Or grant the pub/sub category:\n"
        f"    ACL SETUSER {user} +@pubsub"
    )


def _format_monitor_acl_fix(user: str) -> str:
    return (
        f"user {user!r} cannot run MONITOR (required by --monitor mode).\n"
        "Fix (run as an admin user):\n"
        f"    ACL SETUSER {user} +monitor"
    )

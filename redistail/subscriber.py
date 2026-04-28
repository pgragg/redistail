"""Keyspace-notification subscriber and MONITOR fallback.

This is the redistail analog of pgtail's logical-replication stream:
take a Redis URL + Settings, subscribe (or MONITOR), and yield
``KeyEvent`` objects until the caller stops iterating.

Design choices:

- The **keyevent** channel (``__keyevent@<db>__:<event>``) is the
  source-of-truth: the event name lives in the channel and the key lives
  in the message body. We do *not* subscribe to the keyspace channel —
  it carries the same info inverted and would just produce duplicates.
- Each db in ``settings.dbs`` gets its own pattern subscription on a
  single shared connection.
- ``--with-values`` triggers an opportunistic value fetch via a separate
  client (TYPE-then-fetch). Failures are swallowed; the event still
  flows through with ``value=None``.
- ``--monitor`` mode parses ``MONITOR`` output lines into ``KeyEvent``s.
  Reads (``GET``, ``HGET``, …) are dropped; only mutating commands are
  surfaced. Note: ``expired`` and ``evicted`` events are NOT visible
  via MONITOR — they're only emitted by keyspace notifications.
"""

from __future__ import annotations

import contextlib
import logging
import re
import shlex
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import redis
from redis.exceptions import RedisError

from redistail.connection import make_client
from redistail.events import KeyEvent

if TYPE_CHECKING:
    from redistail.options import Settings


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-testable without a live Redis)
# ---------------------------------------------------------------------------

# Channel format: __keyevent@<db>__:<event>
_KEYEVENT_RE = re.compile(r"^__keyevent@(\d+)__:(.+)$")
_KEYSPACE_RE = re.compile(r"^__keyspace@(\d+)__:(.+)$")


def parse_keyevent_channel(channel: str) -> tuple[int, str] | None:
    """Return (db, event_name) for a keyevent channel, or None if it doesn't match."""
    m = _KEYEVENT_RE.match(channel)
    if not m:
        return None
    return (int(m.group(1)), m.group(2).lower())


def parse_keyspace_channel(channel: str) -> tuple[int, str] | None:
    """Return (db, key) for a keyspace channel, or None if it doesn't match."""
    m = _KEYSPACE_RE.match(channel)
    if not m:
        return None
    return (int(m.group(1)), m.group(2))


def _to_text(b: object) -> str:
    """Decode bytes to str (utf-8, replace errors); pass non-bytes through str()."""
    if isinstance(b, bytes):
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            return b.decode("utf-8", errors="replace")
    return str(b) if b is not None else ""


# Map MONITOR command names → event name we synthesize for KeyEvent.op.
# Only mutating commands are listed; everything else is dropped.
_MONITOR_WRITE_COMMANDS: dict[str, str] = {
    # generic
    "del": "del",
    "unlink": "del",
    "expire": "expire",
    "pexpire": "expire",
    "expireat": "expire",
    "pexpireat": "expire",
    "persist": "persist",
    "rename": "rename_to",
    "renamenx": "rename_to",
    "copy": "copy_to",
    "move": "move",
    "restore": "restore",
    # string
    "set": "set",
    "setex": "set",
    "psetex": "set",
    "setnx": "set",
    "setrange": "setrange",
    "mset": "set",
    "msetnx": "set",
    "getset": "set",
    "getdel": "del",
    "incr": "incrby",
    "incrby": "incrby",
    "incrbyfloat": "incrbyfloat",
    "decr": "decrby",
    "decrby": "decrby",
    "append": "append",
    # list
    "lpush": "lpush",
    "lpushx": "lpush",
    "rpush": "rpush",
    "rpushx": "rpush",
    "lpop": "lpop",
    "rpop": "rpop",
    "linsert": "linsert",
    "lset": "lset",
    "lrem": "lrem",
    "ltrim": "ltrim",
    "rpoplpush": "rpush",
    "lmove": "lpush",
    "blmove": "lpush",
    "blpop": "lpop",
    "brpop": "rpop",
    # set
    "sadd": "sadd",
    "srem": "srem",
    "spop": "spop",
    "smove": "smove",
    "sinterstore": "sinterstore",
    "sunionstore": "sunionstore",
    "sdiffstore": "sdiffstore",
    # hash
    "hset": "hset",
    "hmset": "hset",
    "hsetnx": "hset",
    "hdel": "hdel",
    "hincrby": "hincrby",
    "hincrbyfloat": "hincrbyfloat",
    # zset
    "zadd": "zadd",
    "zincrby": "zincrby",
    "zrem": "zrem",
    "zremrangebyrank": "zrem",
    "zremrangebyscore": "zrem",
    "zremrangebylex": "zrem",
    "zinterstore": "zinterstore",
    "zunionstore": "zunionstore",
    # stream
    "xadd": "xadd",
    "xdel": "xdel",
    "xtrim": "xtrim",
    "xsetid": "xsetid",
    # admin
    "flushdb": "flushdb",
    "flushall": "flushdb",
}


# Redis MONITOR output format:
#   <unix-ts> [<db> <addr>] "command" "arg1" "arg2" ...
# Example: 1714312345.123456 [0 127.0.0.1:53412] "SET" "foo" "bar"
# We can't use [^\]]* for the address because IPv6 clients render as
# `[::1]:6379` — they contain a `]` of their own. Match non-greedily and
# require the closing bracket to be followed by whitespace + a double-quote
# (which is how every MONITOR command always begins).
_MONITOR_LINE_RE = re.compile(r'^(?P<ts>\d+\.\d+)\s+\[(?P<db>\d+)\s+.*?\]\s+(?P<rest>".*)$')


def parse_monitor_line(line: str) -> tuple[float, int, str, list[str]] | None:
    """Parse a MONITOR output line.

    Returns (timestamp, db, command, args) or None if the line doesn't match
    (e.g. the initial "OK" reply, blanks).
    """
    m = _MONITOR_LINE_RE.match(line.strip())
    if not m:
        return None
    ts = float(m.group("ts"))
    db = int(m.group("db"))
    rest = m.group("rest")
    try:
        # MONITOR uses double-quoted args with backslash escapes — shlex handles it.
        tokens = shlex.split(rest, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    cmd = tokens[0].lower()
    args = tokens[1:]
    return (ts, db, cmd, args)


def monitor_line_to_event(line: str) -> KeyEvent | None:
    """Convert a MONITOR line into a KeyEvent, or None if it should be dropped."""
    parsed = parse_monitor_line(line)
    if parsed is None:
        return None
    ts_unix, db, cmd, args = parsed
    op = _MONITOR_WRITE_COMMANDS.get(cmd)
    if op is None:
        return None  # read or unknown command — drop
    # Commands like FLUSHDB have no key argument; synthesize a sentinel.
    key = "*" if not args else args[0]
    return KeyEvent(
        op=op,
        db=db,
        key=key,
        ts=datetime.fromtimestamp(ts_unix, tz=UTC),
        channel=f"MONITOR:{cmd}",
        source="monitor",
    )


# ---------------------------------------------------------------------------
# Value fetcher (used when settings.with_values is True)
# ---------------------------------------------------------------------------


# Ops where the key is already gone by the time we'd try to fetch.
_VALUELESS_OPS: frozenset[str] = frozenset({"del", "unlink", "expired", "evicted", "flushdb"})


def _fetch_value(client: redis.Redis, db: int, key: str) -> tuple[Any | None, str | None]:
    """Best-effort TYPE-then-fetch. Returns (value, type_name) or (None, None) on miss/error."""
    try:
        # Switch to the right db on the value-fetch connection.
        client.execute_command("SELECT", db)
        t_raw = client.type(key)
        t = _to_text(t_raw).lower()
        if t in ("none", ""):
            return (None, None)
        if t == "string":
            return (client.get(key), t)
        if t == "hash":
            raw = client.hgetall(key)
            return ({_to_text(k): v for k, v in raw.items()}, t)
        if t == "list":
            return (client.lrange(key, 0, -1), t)
        if t == "set":
            return (set(client.smembers(key)), t)
        if t == "zset":
            return (client.zrange(key, 0, -1, withscores=True), t)
        if t == "stream":
            # Last 10 entries; full XRANGE could be huge.
            return (client.xrevrange(key, count=10), t)
    except RedisError as e:
        log.debug("value fetch failed for db=%d key=%r: %s", db, key, e)
        return (None, None)
    return (None, None)


# ---------------------------------------------------------------------------
# Stream functions
# ---------------------------------------------------------------------------


def _build_patterns(dbs: tuple[int, ...]) -> list[str]:
    return [f"__keyevent@{d}__:*" for d in dbs]


def stream_keyspace_events(
    settings: Settings,
    *,
    poll_timeout: float = 1.0,
    _stop_after: int | None = None,
) -> Iterator[KeyEvent]:
    """Subscribe to keyevent channels and yield KeyEvents.

    ``_stop_after`` is a test hook: yield at most N events then return.
    """
    client = make_client(settings.url)
    value_client: redis.Redis | None = make_client(settings.url) if settings.with_values else None
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    patterns = _build_patterns(settings.dbs)
    pubsub.psubscribe(*patterns)

    yielded = 0
    try:
        while True:
            msg = pubsub.get_message(timeout=poll_timeout)
            if msg is None:
                continue
            if msg.get("type") not in ("pmessage", "message"):
                continue
            channel = _to_text(msg.get("channel"))
            data = msg.get("data")
            parsed = parse_keyevent_channel(channel)
            if parsed is None:
                continue  # not a keyevent channel — ignore
            db, event_name = parsed
            key = _to_text(data)

            value: Any | None = None
            value_type: str | None = None
            if value_client is not None and event_name not in _VALUELESS_OPS:
                value, value_type = _fetch_value(value_client, db, key)

            yield KeyEvent(
                op=event_name,
                db=db,
                key=key,
                ts=datetime.now(tz=UTC),
                value=value,
                value_type=value_type,
                channel=channel,
                source="keyspace",
            )
            yielded += 1
            if _stop_after is not None and yielded >= _stop_after:
                return
    finally:
        with contextlib.suppress(Exception):
            pubsub.close()
        with contextlib.suppress(Exception):
            client.close()
        if value_client is not None:
            with contextlib.suppress(Exception):
                value_client.close()


def stream_monitor_events(
    settings: Settings,
    *,
    _stop_after: int | None = None,
) -> Iterator[KeyEvent]:
    """Run MONITOR and yield synthesized KeyEvents.

    NOTE: MONITOR shows every command, including reads. Reads are dropped.
    `expired` and `evicted` events are NOT visible via MONITOR.
    """
    client = make_client(settings.url, socket_timeout=None)
    yielded = 0
    try:
        # redis-py exposes a context-manager Monitor; we drive it manually for
        # consistent shutdown handling.
        mon = client.monitor()
        with mon as m:
            for entry in m.listen():
                # redis-py 5+ yields dicts: {'time': ..., 'db': ..., 'client_address': ..., 'command': '...'}
                line = _monitor_entry_to_line(entry)
                if line is None:
                    continue
                evt = monitor_line_to_event(line)
                if evt is None:
                    continue
                yield evt
                yielded += 1
                if _stop_after is not None and yielded >= _stop_after:
                    return
    finally:
        with contextlib.suppress(Exception):
            client.close()


def _monitor_entry_to_line(entry: object) -> str | None:
    """Convert a redis-py monitor() entry (dict or str) into the canonical MONITOR line.

    Different redis-py versions return slightly different shapes. We
    canonicalize to the on-the-wire string so ``parse_monitor_line`` can do
    the rest.
    """
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry
    if isinstance(entry, bytes):
        return _to_text(entry)
    if isinstance(entry, dict):
        ts = entry.get("time", 0.0)
        db = entry.get("database", entry.get("db", 0))
        addr = entry.get("client_address", entry.get("client", ""))
        cmd = entry.get("command", "")
        if not cmd:
            return None
        # Best effort: redis-py's parsed `command` is already a single string
        # like 'SET "foo" "bar"'. Wrap it back into MONITOR-line shape so our
        # parser handles both code paths uniformly.
        return f"{ts} [{db} {addr}] {_quote_command(cmd)}"
    return None


def _quote_command(cmd: str) -> str:
    """Ensure command tokens are double-quoted (redis-py sometimes returns them already)."""
    s = cmd.strip()
    if s.startswith('"'):
        return s
    parts = s.split(" ", 1)
    head = f'"{parts[0]}"'
    if len(parts) == 1:
        return head
    return head + " " + parts[1]


def stream_events(settings: Settings) -> Iterator[KeyEvent]:
    """High-level entry point: dispatch to keyspace or MONITOR mode."""
    if settings.monitor:
        yield from stream_monitor_events(settings)
    else:
        yield from stream_keyspace_events(settings)

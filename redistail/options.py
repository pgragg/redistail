"""Runtime options shared across the CLI, subscriber, and formatter layers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Default ops shown when --ops isn't specified.
DEFAULT_OPS: tuple[str, ...] = ("set", "del", "expire", "expired")

# Well-known Redis keyspace event names. Modules / future Redis versions may
# produce events outside this set, so we still allow any lowercase string;
# the set is just used for the friendlier "did you mean?" path in the CLI.
KNOWN_OPS: frozenset[str] = frozenset(
    {
        # generic
        "del",
        "unlink",
        "expire",
        "pexpire",
        "expireat",
        "pexpireat",
        "persist",
        "rename",
        "rename_from",
        "rename_to",
        "move",
        "copy_to",
        "copy_from",
        "restore",
        # lifecycle
        "expired",
        "evicted",
        # string
        "set",
        "setrange",
        "incrby",
        "incrbyfloat",
        "decrby",
        "append",
        "getset",
        "getdel",
        # list
        "lpush",
        "rpush",
        "lpop",
        "rpop",
        "linsert",
        "lset",
        "lrem",
        "ltrim",
        "blpop",
        "brpop",
        # set
        "sadd",
        "srem",
        "spop",
        "smove",
        "sinterstore",
        "sunionstore",
        "sdiffstore",
        # hash
        "hset",
        "hdel",
        "hincrby",
        "hincrbyfloat",
        # zset
        "zadd",
        "zrem",
        "zincr",
        "zincrby",
        "zinterstore",
        "zunionstore",
        # stream
        "xadd",
        "xdel",
        "xtrim",
        "xgroup-create",
        "xclaim",
        "xsetid",
        # admin
        "flushdb",
    }
)


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    """All runtime options resolved from CLI / env / config / defaults."""

    url: str

    # Filtering
    dbs: tuple[int, ...] = (0,)
    patterns: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ops: tuple[str, ...] = DEFAULT_OPS

    # Output
    json_output: bool = False
    color: bool = True
    show_time: bool = True
    verbose: bool = False
    max_width: int = 80

    # Redaction (key globs whose values get masked)
    redact: tuple[str, ...] = ()

    # Modes
    with_values: bool = False
    monitor: bool = False

    # Tee
    log_file: Path | None = None

    # Burst collapsing (ticket 007)
    expand_all: bool = False
    collapse_threshold: int = 1000

    # Computed / extras
    extra: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def resolve_url(cli_url: str | None) -> str | None:
        """Pick the Redis URL: CLI arg wins, then $REDIS_URL."""
        if cli_url:
            return cli_url
        env = os.environ.get("REDIS_URL")
        return env or None

    @staticmethod
    def resolve_color(no_color_flag: bool) -> bool:
        """Honor --no-color and NO_COLOR env var (https://no-color.org)."""
        if no_color_flag:
            return False
        return not os.environ.get("NO_COLOR")


def parse_ops(raw: str) -> tuple[str, ...]:
    """Parse a comma-separated --ops value.

    Lowercases and de-duplicates while preserving order. Empty input falls
    back to ``DEFAULT_OPS``. We don't hard-fail on unknown ops — Redis
    modules can emit custom events — but the well-known set is used by the
    CLI for friendlier error suggestions when needed.
    """
    parts = _split_csv(raw)
    if not parts:
        return DEFAULT_OPS
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        lo = p.lower()
        if lo not in seen:
            seen.add(lo)
            out.append(lo)
    return tuple(out)


def parse_csv_tuple(raw: str | None) -> tuple[str, ...]:
    return tuple(_split_csv(raw))


def parse_db_list(raw: str | None) -> tuple[int, ...]:
    """Parse --db: comma-separated db numbers. Empty → (0,)."""
    parts = _split_csv(raw)
    if not parts:
        return (0,)
    out: list[int] = []
    for p in parts:
        try:
            n = int(p)
        except ValueError as e:
            raise ValueError(f"--db expects integers, got {p!r}") from e
        # Redis default max is 16 dbs (0-15). Some setups raise this; we
        # allow up to 255 just in case but reject obvious garbage.
        if n < 0 or n > 255:
            raise ValueError(f"--db out of range: {n}")
        out.append(n)
    return tuple(out)

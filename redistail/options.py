"""Settings dataclass and CLI/env parsing helpers.

Stub — populated in ticket 002 (Connection handling & CLI args).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """User-facing configuration resolved from CLI flags / env / config file."""

    url: str | None = None
    dbs: tuple[int, ...] = (0,)
    patterns: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ops: tuple[str, ...] = ("set", "del", "expire", "expired")
    json: bool = False
    no_color: bool = False
    no_time: bool = False
    verbose: bool = False
    max_width: int = 80
    redact: tuple[str, ...] = ()
    with_values: bool = False
    monitor: bool = False
    log_file: str | None = None
    expand_all: bool = False
    collapse_threshold: int = 1000
    config_path: str | None = None
    extra: dict[str, object] = field(default_factory=dict)

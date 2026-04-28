"""Render KeyEvent objects as colored text or JSON lines."""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from rich.console import Console
from rich.text import Text

from redistail.events import KeyEvent
from redistail.options import Settings

# ---------------------------------------------------------------------------
# Op categorization → color
# ---------------------------------------------------------------------------

_WRITE_OPS: frozenset[str] = frozenset(
    {
        "set",
        "setrange",
        "incrby",
        "incrbyfloat",
        "decrby",
        "append",
        "lpush",
        "rpush",
        "linsert",
        "lset",
        "sadd",
        "smove",
        "sinterstore",
        "sunionstore",
        "sdiffstore",
        "hset",
        "hincrby",
        "hincrbyfloat",
        "zadd",
        "zincr",
        "zincrby",
        "zinterstore",
        "zunionstore",
        "xadd",
        "xsetid",
    }
)

_DELETE_OPS: frozenset[str] = frozenset(
    {
        "del",
        "unlink",
        "hdel",
        "srem",
        "spop",
        "zrem",
        "lpop",
        "rpop",
        "lrem",
        "ltrim",
        "xdel",
        "xtrim",
    }
)

_EXPIRE_OPS: frozenset[str] = frozenset({"expire", "pexpire", "expireat", "pexpireat", "persist"})

_LIFECYCLE_OPS: frozenset[str] = frozenset({"expired", "evicted"})

_MOVE_OPS: frozenset[str] = frozenset(
    {"rename", "rename_from", "rename_to", "move", "copy_from", "copy_to", "restore"}
)

_ADMIN_OPS: frozenset[str] = frozenset({"flushdb", "flushall"})


def op_color(op: str) -> str:
    """Map a Redis event name to a rich color name."""
    if op in _WRITE_OPS:
        return "green"
    if op in _DELETE_OPS or op in _ADMIN_OPS:
        return "red"
    if op in _EXPIRE_OPS:
        return "blue"
    if op in _LIFECYCLE_OPS:
        return "magenta"
    if op in _MOVE_OPS:
        return "cyan"
    return "white"


# ANSI escape pattern used to strip color when writing to log files.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_str(v: object) -> str:
    """Best-effort string conversion for values that might be bytes."""
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("utf-8", errors="replace")
    return str(v)


def _truncate(s: str, max_width: int) -> str:
    if max_width and len(s) > max_width:
        return s[: max_width - 1] + "\u2026"
    return s


def _key_matches_redact(key: str, redact_globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(key, g) for g in redact_globs)


def render_value(value: object, value_type: str | None, *, max_width: int, redacted: bool) -> str:
    """Render a fetched Redis value for the human-readable output line.

    String → quoted; hash → `{k: v, ...}`; list → `[a, b, ...]`; set → `{a, b}`;
    zset → `[(m, score), ...]`; stream → `[(id, fields), ...]`.
    """
    if redacted:
        return "***"
    if value is None:
        return ""

    if value_type == "string":
        return _truncate(f'"{_to_str(value)}"', max_width)
    if value_type == "hash" and isinstance(value, dict):
        parts = [f"{_to_str(k)}: {_truncate(_to_str(v), max_width)}" for k, v in value.items()]
        return _truncate("{" + ", ".join(parts) + "}", max_width)
    if value_type == "list" and isinstance(value, list):
        parts = [_truncate(_to_str(v), max_width) for v in value]
        return _truncate("[" + ", ".join(parts) + "]", max_width)
    if value_type == "set" and isinstance(value, (set, frozenset)):
        parts = sorted(_truncate(_to_str(v), max_width) for v in value)
        return _truncate("{" + ", ".join(parts) + "}", max_width)
    if value_type == "zset" and isinstance(value, list):
        parts = [f"({_truncate(_to_str(m), max_width)}, {s})" for (m, s) in value]
        return _truncate("[" + ", ".join(parts) + "]", max_width)
    if value_type == "stream" and isinstance(value, list):
        parts = [f"({_to_str(eid)}, {_to_str(fields)})" for eid, fields in value]
        return _truncate("[" + ", ".join(parts) + "]", max_width)

    # Fallback: best-effort repr.
    return _truncate(_to_str(value), max_width)


def _json_safe_value(value: object, value_type: str | None) -> object:
    """Convert a fetched Redis value to JSON-safe form."""
    if value is None:
        return None
    if value_type == "string":
        return _to_str(value)
    if value_type == "hash" and isinstance(value, dict):
        return {_to_str(k): _to_str(v) for k, v in value.items()}
    if value_type == "list" and isinstance(value, list):
        return [_to_str(v) for v in value]
    if value_type == "set" and isinstance(value, (set, frozenset)):
        return sorted(_to_str(v) for v in value)
    if value_type == "zset" and isinstance(value, list):
        return [{"member": _to_str(m), "score": s} for (m, s) in value]
    if value_type == "stream" and isinstance(value, list):
        return [
            {"id": _to_str(eid), "fields": {_to_str(k): _to_str(v) for k, v in fields.items()}}
            if isinstance(fields, dict)
            else {"id": _to_str(eid), "fields": _to_str(fields)}
            for eid, fields in value
        ]
    return _to_str(value)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


@dataclass
class Renderer:
    """Stateful renderer that emits KeyEvents to stdout (and optionally a log file)."""

    settings: Settings
    stdout: TextIO
    log_handle: TextIO | None = None
    console: Console | None = None

    @classmethod
    def from_settings(cls, settings: Settings, *, stdout: TextIO | None = None) -> Renderer:
        out = stdout if stdout is not None else sys.stdout
        # Color off when not a TTY OR when --no-color/$NO_COLOR set.
        is_tty = (out is sys.stdout and sys.stdout.isatty()) or (
            stdout is not None and getattr(out, "isatty", lambda: False)()
        )
        use_color = settings.color and is_tty
        console = Console(
            file=out,
            force_terminal=use_color,
            color_system="auto" if use_color else None,
            highlight=False,
            soft_wrap=True,
        )
        log_handle: TextIO | None = None
        if settings.log_file:
            path = Path(settings.log_file)
            log_handle = path.open("a", encoding="utf-8")
        return cls(settings=settings, stdout=out, log_handle=log_handle, console=console)

    def close(self) -> None:
        if self.log_handle is not None:
            try:
                self.log_handle.close()
            finally:
                self.log_handle = None

    # ---- main entry -----------------------------------------------------

    def emit(self, event: KeyEvent) -> None:
        if self.settings.json_output:
            line = self._render_json(event)
            self.stdout.write(line + "\n")
            self.stdout.flush()
            if self.log_handle is not None:
                self.log_handle.write(line + "\n")
                self.log_handle.flush()
            return

        text = self._render_text(event)
        if self.console is not None and self.settings.color:
            self.console.print(text)
        else:
            plain = text.plain if isinstance(text, Text) else str(text)
            self.stdout.write(plain + "\n")
            self.stdout.flush()
        if self.log_handle is not None:
            plain = text.plain if isinstance(text, Text) else _strip_ansi(str(text))
            self.log_handle.write(plain + "\n")
            self.log_handle.flush()

    # ---- text rendering -------------------------------------------------

    def _render_text(self, event: KeyEvent) -> Text:
        s = self.settings
        line = Text()

        if s.show_time:
            ts = event.ts.astimezone() if isinstance(event.ts, datetime) else event.ts
            line.append(ts.strftime("%H:%M:%S "), style="dim")

        color = op_color(event.op)
        line.append(event.op.upper().ljust(8), style=f"bold {color}")
        line.append(" ")
        line.append(event.key, style="bold")

        # Collapser hints (ticket 007 plugs in here).
        if event.extra.get("collapsed_count"):
            n = event.extra["collapsed_count"]
            line.append("  ")
            line.append(f"{n:,} events (collapsed)", style="dim italic")
            return line
        if event.extra.get("collapse_notice"):
            t = event.extra.get("threshold", s.collapse_threshold)
            line.append("  ")
            line.append(
                f"… collapsing remainder after {t:,} events/s (--expand-all to disable)",
                style="dim italic",
            )
            return line

        if s.verbose:
            extra_bits: list[str] = [f"db={event.db}"]
            if event.channel:
                extra_bits.append(f"channel={event.channel}")
            line.append("  ")
            line.append(" ".join(extra_bits), style="dim")

        if event.value is not None:
            redacted = _key_matches_redact(event.key, s.redact)
            rendered = render_value(
                event.value,
                event.value_type,
                max_width=s.max_width,
                redacted=redacted,
            )
            if rendered:
                line.append("  ")
                line.append(rendered)

        return line

    # ---- JSON rendering -------------------------------------------------

    def _render_json(self, event: KeyEvent) -> str:
        s = self.settings
        ts = event.ts.astimezone() if isinstance(event.ts, datetime) else event.ts
        payload: dict[str, Any] = {
            "ts": ts.isoformat(timespec="seconds") if isinstance(ts, datetime) else str(ts),
            "op": event.op,
            "db": event.db,
            "key": event.key,
        }
        if event.extra.get("collapsed_count"):
            payload["collapsed_count"] = event.extra["collapsed_count"]
            return json.dumps(payload, default=str)
        if event.extra.get("collapse_notice"):
            payload["collapse_notice"] = True
            payload["threshold"] = event.extra.get("threshold", s.collapse_threshold)
            return json.dumps(payload, default=str)
        if s.verbose:
            payload["channel"] = event.channel
            payload["source"] = event.source
        if event.value is not None:
            redacted = _key_matches_redact(event.key, s.redact)
            payload["value"] = (
                "***" if redacted else _json_safe_value(event.value, event.value_type)
            )
            if event.value_type:
                payload["value_type"] = event.value_type
        return json.dumps(payload, default=str)


__all__ = ["Renderer", "op_color", "render_value"]

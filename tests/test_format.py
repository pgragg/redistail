"""Unit tests for the renderer (text + JSON)."""

from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime

from redistail.events import KeyEvent
from redistail.format import Renderer, op_color, render_value
from redistail.options import Settings

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip(s: str) -> str:
    return _ANSI_RE.sub("", s)


def _make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "url": "redis://x",
        "color": False,  # test plain output by default
        "json_output": False,
        "show_time": True,
        "max_width": 80,
        "verbose": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ts() -> datetime:
    return datetime(2026, 4, 28, 14, 2, 11, tzinfo=UTC)


def _expected_hms() -> str:
    """What HH:MM:SS the renderer will print for `_ts()` on the local machine.

    The renderer calls ``ts.astimezone()`` so the displayed time depends on the
    runner's TZ. Compute it the same way the renderer does so tests pass
    regardless of CI/dev box timezone.
    """
    return _ts().astimezone().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# op_color mapping
# ---------------------------------------------------------------------------


def test_op_color_writes_green() -> None:
    assert op_color("set") == "green"
    assert op_color("hset") == "green"
    assert op_color("xadd") == "green"


def test_op_color_deletes_red() -> None:
    assert op_color("del") == "red"
    assert op_color("unlink") == "red"
    assert op_color("hdel") == "red"
    assert op_color("flushdb") == "red"


def test_op_color_expire_blue() -> None:
    assert op_color("expire") == "blue"
    assert op_color("pexpire") == "blue"
    assert op_color("persist") == "blue"


def test_op_color_lifecycle_magenta() -> None:
    assert op_color("expired") == "magenta"
    assert op_color("evicted") == "magenta"


def test_op_color_move_cyan() -> None:
    assert op_color("rename_to") == "cyan"
    assert op_color("copy_to") == "cyan"


def test_op_color_unknown_white() -> None:
    assert op_color("frobnicate") == "white"


# ---------------------------------------------------------------------------
# render_value type-aware
# ---------------------------------------------------------------------------


def test_render_value_string_quoted() -> None:
    assert render_value(b"hello", "string", max_width=80, redacted=False) == '"hello"'


def test_render_value_hash() -> None:
    out = render_value({"a": b"1", "b": b"2"}, "hash", max_width=80, redacted=False)
    # Order preserved from dict insertion order.
    assert out == "{a: 1, b: 2}"


def test_render_value_list() -> None:
    out = render_value([b"a", b"b", b"c"], "list", max_width=80, redacted=False)
    assert out == "[a, b, c]"


def test_render_value_set() -> None:
    out = render_value({b"a", b"b"}, "set", max_width=80, redacted=False)
    # Sets are sorted for deterministic output.
    assert out == "{a, b}"


def test_render_value_zset() -> None:
    out = render_value([(b"alice", 1.0), (b"bob", 2.5)], "zset", max_width=80, redacted=False)
    assert out == "[(alice, 1.0), (bob, 2.5)]"


def test_render_value_redacted() -> None:
    assert render_value(b"sekret", "string", max_width=80, redacted=True) == "***"
    assert render_value({"a": "b"}, "hash", max_width=80, redacted=True) == "***"


def test_render_value_truncation() -> None:
    long = b"x" * 100
    out = render_value(long, "string", max_width=20, redacted=False)
    assert len(out) <= 20
    assert out.endswith("\u2026")


def test_render_value_none_returns_empty() -> None:
    assert render_value(None, None, max_width=80, redacted=False) == ""


# ---------------------------------------------------------------------------
# Renderer text output
# ---------------------------------------------------------------------------


def test_text_set_event() -> None:
    s = _make_settings()
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="set", db=0, key="foo", ts=_ts()))
    line = _strip(out.getvalue()).rstrip("\n")
    assert "SET" in line
    assert "foo" in line
    assert _expected_hms() in line


def test_text_hides_time() -> None:
    s = _make_settings(show_time=False)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="set", db=0, key="foo", ts=_ts()))
    assert _expected_hms() not in out.getvalue()


def test_text_verbose_includes_db_and_channel() -> None:
    s = _make_settings(verbose=True)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(
        KeyEvent(
            op="set",
            db=3,
            key="k",
            ts=_ts(),
            channel="__keyevent@3__:set",
        )
    )
    line = _strip(out.getvalue())
    assert "db=3" in line
    assert "channel=__keyevent@3__:set" in line


def test_text_with_value_string() -> None:
    s = _make_settings()
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="set", db=0, key="foo", ts=_ts(), value=b"bar", value_type="string"))
    assert '"bar"' in _strip(out.getvalue())


def test_text_redaction_applies_to_matching_key() -> None:
    s = _make_settings(redact=("session:*",))
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(
        KeyEvent(
            op="set",
            db=0,
            key="session:abc",
            ts=_ts(),
            value=b"secret-token",
            value_type="string",
        )
    )
    line = _strip(out.getvalue())
    assert "***" in line
    assert "secret-token" not in line


def test_text_redaction_does_not_apply_to_other_keys() -> None:
    s = _make_settings(redact=("session:*",))
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(
        KeyEvent(
            op="set",
            db=0,
            key="user:42",
            ts=_ts(),
            value=b"public",
            value_type="string",
        )
    )
    line = _strip(out.getvalue())
    assert '"public"' in line


def test_text_no_color_strips_ansi() -> None:
    s = _make_settings(color=False)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="set", db=0, key="foo", ts=_ts()))
    raw = out.getvalue()
    # No ANSI in plain mode.
    assert "\x1b[" not in raw


def test_text_collapsed_summary() -> None:
    s = _make_settings()
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(
        KeyEvent(
            op="set",
            db=0,
            key="counter:foo",
            ts=_ts(),
            extra={"collapsed_count": 1247},
        )
    )
    assert "1,247 events (collapsed)" in _strip(out.getvalue())


def test_text_expired_lifecycle() -> None:
    s = _make_settings()
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="expired", db=0, key="ttl:foo", ts=_ts()))
    line = _strip(out.getvalue())
    assert "EXPIRED" in line
    assert "ttl:foo" in line


# ---------------------------------------------------------------------------
# Renderer JSON output
# ---------------------------------------------------------------------------


def test_json_basic_set() -> None:
    s = _make_settings(json_output=True)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="set", db=0, key="foo", ts=_ts(), value=b"bar", value_type="string"))
    payload = json.loads(out.getvalue().strip())
    assert payload["op"] == "set"
    assert payload["db"] == 0
    assert payload["key"] == "foo"
    assert payload["value"] == "bar"
    assert payload["value_type"] == "string"


def test_json_no_value_when_none() -> None:
    s = _make_settings(json_output=True)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="del", db=0, key="foo", ts=_ts()))
    payload = json.loads(out.getvalue().strip())
    assert "value" not in payload


def test_json_redaction() -> None:
    s = _make_settings(json_output=True, redact=("token:*",))
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(
        KeyEvent(
            op="set",
            db=0,
            key="token:abc",
            ts=_ts(),
            value=b"sekret",
            value_type="string",
        )
    )
    payload = json.loads(out.getvalue().strip())
    assert payload["value"] == "***"


def test_json_hash_value() -> None:
    s = _make_settings(json_output=True)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(
        KeyEvent(
            op="hset",
            db=0,
            key="h:1",
            ts=_ts(),
            value={"f1": b"v1", "f2": b"v2"},
            value_type="hash",
        )
    )
    payload = json.loads(out.getvalue().strip())
    assert payload["value"] == {"f1": "v1", "f2": "v2"}


def test_json_collapsed_summary() -> None:
    s = _make_settings(json_output=True)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(
        KeyEvent(
            op="set",
            db=0,
            key="counter:foo",
            ts=_ts(),
            extra={"collapsed_count": 9999},
        )
    )
    payload = json.loads(out.getvalue().strip())
    assert payload["collapsed_count"] == 9999


# ---------------------------------------------------------------------------
# Log file tee (no ANSI)
# ---------------------------------------------------------------------------


def test_log_file_strips_ansi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    log = tmp_path / "out.log"
    s = _make_settings(log_file=log, color=False)
    out = io.StringIO()
    r = Renderer.from_settings(s, stdout=out)
    r.emit(KeyEvent(op="set", db=0, key="foo", ts=_ts()))
    r.close()
    contents = log.read_text()
    assert "\x1b[" not in contents
    assert "SET" in contents
    assert "foo" in contents

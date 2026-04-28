"""Tests for CLI argument parsing and option resolution (ticket 002)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from redistail.cli import app
from redistail.options import (
    DEFAULT_OPS,
    Settings,
    parse_csv_tuple,
    parse_db_list,
    parse_ops,
)

runner = CliRunner()


def test_help_lists_every_flag() -> None:
    # Force a wide terminal so rich-typer doesn't truncate long flag names
    # like --collapse-threshold to --collapse-thresh… in the rendered help.
    result = runner.invoke(app, ["--help"], env={"COLUMNS": "200", "TERMINAL_WIDTH": "200"})
    assert result.exit_code == 0
    out = result.stdout
    for flag in [
        "--db",
        "--pattern",
        "--exclude",
        "--ops",
        "--json",
        "--no-color",
        "--no-time",
        "--verbose",
        "--max-width",
        "--redact",
        "--with-values",
        "--no-values",
        "--monitor",
        "--log-file",
        "--expand-all",
        "--collapse-threshold",
        "--config",
        "--version",
    ]:
        assert flag in out, f"missing {flag} in --help"


def test_missing_url_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    combined = result.output or ""
    assert "no URL" in combined or "REDIS_URL" in combined


def test_bad_url_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    result = runner.invoke(app, ["not-a-real-url"])
    assert result.exit_code == 2


def test_unreachable_url_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    # Port 1 is reserved/unused; connect will fail fast.
    result = runner.invoke(
        app,
        ["redis://127.0.0.1:1/0"],
    )
    assert result.exit_code == 2


def test_invalid_db_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    result = runner.invoke(
        app,
        ["redis://127.0.0.1:1/0", "--db", "not-a-number"],
    )
    assert result.exit_code == 2


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "redistail" in result.stdout.lower()


def test_parse_ops_default() -> None:
    # DEFAULT_OPS is now the empty tuple sentinel meaning "show all".
    assert DEFAULT_OPS == ()
    assert parse_ops("") == DEFAULT_OPS


def test_parse_ops_all_sentinel() -> None:
    # "all" and "*" both collapse to the empty-tuple "show everything" sentinel.
    assert parse_ops("all") == ()
    assert parse_ops("*") == ()
    assert parse_ops("set,all,del") == ()


def test_parse_ops_normalizes_case() -> None:
    assert parse_ops("SET,Del,Expire") == ("set", "del", "expire")


def test_parse_ops_dedupes() -> None:
    assert parse_ops("set,SET,del") == ("set", "del")


def test_parse_ops_empty_returns_default() -> None:
    assert parse_ops("") == DEFAULT_OPS


def test_parse_ops_allows_custom_event() -> None:
    # Redis modules can produce custom events; we don't hard-validate.
    assert parse_ops("set,my-custom-event") == ("set", "my-custom-event")


def test_parse_csv_tuple_handles_empty() -> None:
    assert parse_csv_tuple(None) == ()
    assert parse_csv_tuple("") == ()
    assert parse_csv_tuple(" a , b ,, c ") == ("a", "b", "c")


def test_parse_db_list_default() -> None:
    assert parse_db_list(None) == (0,)
    assert parse_db_list("") == (0,)


def test_parse_db_list_multi() -> None:
    assert parse_db_list("0,1,2") == (0, 1, 2)


def test_parse_db_list_invalid() -> None:
    with pytest.raises(ValueError):
        parse_db_list("foo")


def test_parse_db_list_negative_rejected() -> None:
    with pytest.raises(ValueError):
        parse_db_list("-1")


def test_settings_url_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://envhost:6379/0")
    assert Settings.resolve_url(None) == "redis://envhost:6379/0"
    assert Settings.resolve_url("redis://override:6379/0") == "redis://override:6379/0"


def test_settings_url_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert Settings.resolve_url(None) is None


def test_settings_no_color_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert Settings.resolve_color(no_color_flag=False) is False
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert Settings.resolve_color(no_color_flag=False) is True
    assert Settings.resolve_color(no_color_flag=True) is False

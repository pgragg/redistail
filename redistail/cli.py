"""Command-line entry point for redistail."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from redistail import __version__
from redistail.connection import ConnectionError_, validate_connection
from redistail.format import Renderer
from redistail.options import (
    DEFAULT_OPS,
    Settings,
    parse_csv_tuple,
    parse_db_list,
    parse_ops,
)
from redistail.preflight import PreflightError, run_preflight
from redistail.subscriber import stream_events

app = typer.Typer(
    name="redistail",
    help="Tail Redis key changes (SET/DEL/EXPIRE/HSET/...) with color.",
    add_completion=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"redistail {__version__}")
        raise typer.Exit(0)


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    url: str | None = typer.Argument(
        None,
        metavar="[URL]",
        help="Redis connection URL. Falls back to $REDIS_URL.",
    ),
    db: str = typer.Option(
        "0",
        "--db",
        help="Comma-separated db numbers to watch (default: 0).",
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        help="Comma-separated key include list (globs allowed: 'session:*').",
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        help="Comma-separated key exclude list (globs allowed).",
    ),
    ops: str = typer.Option(
        ",".join(DEFAULT_OPS),
        "--ops",
        help="Operations to show, e.g. set,del,expire,expired,hset.",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit one JSON object per change instead of colored text."
    ),
    no_color: bool = typer.Option(
        False, "--no-color", help="Disable ANSI colors (also honored: NO_COLOR env var)."
    ),
    no_time: bool = typer.Option(False, "--no-time", help="Hide the leading HH:MM:SS timestamp."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Include db number and channel on each line."
    ),
    max_width: int = typer.Option(
        80, "--max-width", min=10, help="Truncate long values to this many characters."
    ),
    redact: str | None = typer.Option(
        None,
        "--redact",
        help="Comma-separated key globs whose values get masked as '***'.",
    ),
    with_values: bool = typer.Option(
        False,
        "--with-values",
        help="Fetch the changed key's current value (extra round-trip per event).",
    ),
    monitor: bool = typer.Option(
        False,
        "--monitor",
        help="Use MONITOR instead of keyspace notifications. Heavier; "
        "won't surface 'expired' / 'evicted' events.",
    ),
    log_file: Path | None = typer.Option(  # noqa: B008
        None,
        "--log-file",
        help="Tee plain (no-ANSI) output to this file in addition to stdout.",
    ),
    expand_all: bool = typer.Option(
        False, "--expand-all", help="Do not collapse high-frequency event bursts."
    ),
    collapse_threshold: int = typer.Option(
        1000,
        "--collapse-threshold",
        min=1,
        help="Collapse a single op on a single key-prefix after this many events / second.",
    ),
    config_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--config",
        help="Path to a TOML config (default: ./.redistail.toml or ~/.config/redistail/config.toml).",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Tail Redis key changes with color."""
    resolved_url = Settings.resolve_url(url)
    if not resolved_url:
        typer.secho(
            "error: no URL provided. Pass one as an argument or set REDIS_URL.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    try:
        ops_tuple = parse_ops(ops)
        dbs_tuple = parse_db_list(db)
    except ValueError as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    settings = Settings(
        url=resolved_url,
        dbs=dbs_tuple,
        patterns=parse_csv_tuple(pattern),
        exclude=parse_csv_tuple(exclude),
        ops=ops_tuple,
        json_output=json_output,
        color=Settings.resolve_color(no_color),
        show_time=not no_time,
        verbose=verbose,
        max_width=max_width,
        redact=parse_csv_tuple(redact),
        with_values=with_values,
        monitor=monitor,
        log_file=log_file,
        expand_all=expand_all,
        collapse_threshold=collapse_threshold,
    )

    try:
        info = validate_connection(settings.url)
    except ConnectionError_ as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e

    try:
        run_preflight(settings.url, monitor_mode=settings.monitor)
    except PreflightError as e:
        typer.secho("preflight check failed:\n", fg=typer.colors.RED, err=True, bold=True)
        typer.secho(str(e), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(3) from e

    mode = (
        "MONITOR"
        if settings.monitor
        else f"keyspace notifications (db={','.join(map(str, settings.dbs))})"
    )
    typer.secho(
        f"redistail → redis {info.server_version} ({info.server_mode}, role={info.role}, "
        f"user={info.current_user}). Source: {mode}. Ctrl-C to stop.",
        fg=typer.colors.CYAN,
        err=True,
    )

    renderer = Renderer.from_settings(settings)
    try:
        for event in stream_events(settings):
            renderer.emit(event)
    except KeyboardInterrupt:
        typer.secho(
            "\nredistail: stopped (Ctrl-C). cleanup complete.",
            fg=typer.colors.CYAN,
            err=True,
        )
        raise typer.Exit(0) from None
    finally:
        renderer.close()


def main() -> None:
    """Console-script entry point."""
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()

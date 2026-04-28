"""CLI entrypoint for redistail.

Wired up enough to print --help and --version. Real behavior lands in later
tickets (002 onwards).
"""

from __future__ import annotations

import sys

import typer

from . import __version__

app = typer.Typer(
    add_completion=False,
    help="Tail Redis key changes (SET/DEL/EXPIRE/HSET/...) with color in your terminal.",
    no_args_is_help=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"redistail {__version__}")
        raise typer.Exit()


@app.command()
def run(
    url: str | None = typer.Argument(
        None,
        help="Redis URL, e.g. redis://user:pw@localhost:6379/0. "
        "Falls back to $REDIS_URL.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Tail key changes from a Redis instance."""
    typer.echo("redistail: not implemented yet — see project_management/ for the roadmap.")
    raise typer.Exit(code=0)


def main() -> None:
    """Console-script entrypoint."""
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()

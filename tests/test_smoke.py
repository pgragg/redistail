"""Smoke tests — confirm the package imports and the CLI registers."""

from __future__ import annotations

import subprocess
import sys

import redistail
from redistail import cli


def test_version_string() -> None:
    assert isinstance(redistail.__version__, str)
    assert redistail.__version__.count(".") >= 1


def test_cli_app_object_exists() -> None:
    # Typer app is constructed at import time; if this is missing we broke the entrypoint.
    assert cli.app is not None


def test_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "redistail.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "redistail" in result.stdout.lower() or "Usage" in result.stdout

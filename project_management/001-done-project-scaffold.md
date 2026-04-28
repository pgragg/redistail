# 001 — Project scaffold

**Status:** Done
**Priority:** High
**Estimate:** S

## Goal
Stand up the Python project skeleton so subsequent tickets have a place to land.

## Tasks
- [x] Create repo `redistail` with `pyproject.toml` (Python 3.11+, `redis`, `typer`, `rich`)
- [x] Configure `pipx`-installable entry point: `redistail = redistail.cli:main`
- [x] Add `ruff` + `mypy` configs
- [x] Add `pytest` setup with one smoke test
- [x] Add `.editorconfig`, `.gitignore`, MIT `LICENSE`
- [x] Stub `redistail/cli.py`, `redistail/subscriber.py`, `redistail/format.py`, `redistail/filters.py`, plus `connection.py`, `preflight.py`, `events.py`, `options.py`, `collapse.py`, `config.py`

## Acceptance
- `pipx install -e .` (or `uv pip install -e .`) works locally
- `redistail --help` prints usage
- `pytest` passes

## Completion notes
- Used `hatchling` as the build backend; `uv venv` + `uv pip install -e ".[dev]"` is the expected dev path.
- Stack: `redis>=5`, `typer`, `rich`. Dev deps: `pytest`, `pytest-cov`, `ruff`, `mypy`, `testcontainers[redis]`, `fakeredis`.
- Module layout mirrors `pgtail` for one-to-one feature parity later: `cli`, `options`, `connection`, `preflight`, `subscriber`, `events`, `format`, `filters`, `collapse`, `config`.

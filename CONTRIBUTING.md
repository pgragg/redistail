# Contributing to redistail

Thanks for your interest in improving redistail!

## Dev setup

```bash
git clone …
cd 02_redistail
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Tests

```bash
pytest -m "not integration"                 # fast unit tests
REDISTAIL_TEST_URL=redis://… pytest         # also run integration tests
ruff check . && ruff format --check .
```

The integration test will, by default, spin up a Redis container via
`testcontainers`. Set `REDISTAIL_TEST_URL` to point at any Redis with
`notify-keyspace-events` enabled to skip Docker (this is what CI does).

## Project management

Tickets live as Markdown files in `project_management/`. Filenames follow
`NNN-status-short-slug.md`, where `status` is one of:

- `backlog` — not yet planned
- `todo` — planned, ready to pick up
- `in-progress` — actively being worked on
- `in-review` — PR open / awaiting review
- `done` — merged / shipped
- `canceled` — won't do

When you finish a ticket, rename the file (`mv 002-todo-foo.md 002-done-foo.md`)
and update the **Status** field at the top.

## Code style

- `ruff` for lint + format (configured in `pyproject.toml`)
- `mypy` advisory; type hints encouraged but not required everywhere yet
- One module per concern — `cli.py`, `subscriber.py`, `format.py`, `filters.py`,
  etc. Don't grow `cli.py` into a god module.

## Commit messages

Conventional-ish prefixes are nice but not enforced:

```
feat: add --pattern glob filter
fix: handle EXPIRE notifications without value
docs: clarify keyspace-notifications setup
```

## Releasing

See `project_management/012-*-release-and-publish.md`.

# 010 — Tests & CI

**Status:** Todo
**Priority:** High
**Estimate:** M

## Goal
Confidence that redistail works against real Redis versions.

## Tasks
- [ ] Unit tests: keyspace-notification message parser (channel + body → `KeyEvent`)
- [ ] Unit tests: MONITOR line parser (handle quoted args, binary-safe strings)
- [ ] Unit tests: formatter (golden-output tests for each op category)
- [ ] Unit tests: filter glob matching, redaction
- [ ] Unit tests: collapser windowing
- [ ] Integration tests: spin up Redis via `testcontainers-python`, run real `SET`/`DEL`/`EXPIRE`, assert events
- [ ] Use `fakeredis` for tests that don't need pub/sub semantics
- [ ] GitHub Actions matrix: Redis 6, 7 × Python 3.11, 3.12 (already wired in `.github/workflows/ci.yml`)
- [ ] Lint job: `ruff check`, `ruff format --check`, `mypy`
- [ ] Coverage report (target ≥80%)

## Acceptance
- CI green on PRs
- `pytest` runs locally with Docker available
- `pytest -m "not integration"` passes without Docker

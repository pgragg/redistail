# 009 — Config file support (.redistail.toml)

**Status:** Todo
**Priority:** Low
**Estimate:** S

## Goal
Let users save common flag combinations.

## Tasks
- [ ] Look for `./.redistail.toml`, then `~/.config/redistail/config.toml`
- [ ] Schema: `[default]` section with same keys as CLI flags (snake-case)
- [ ] Precedence: CLI flag > env var > config file > built-in default
- [ ] `--config PATH` to point at a specific file
- [ ] Document example config in README (already drafted there)

## Acceptance
- A `.redistail.toml` with `patterns = ["user:*", "order:*"]` is honored
- CLI flag overrides config file value
- `redistail --config ./missing.toml` exits with a clear error

## Notes
- Use stdlib `tomllib` (Python 3.11+).
- Lists in TOML map to comma-separated CLI options — accept both forms transparently in the loader.

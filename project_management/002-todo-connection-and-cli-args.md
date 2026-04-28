# 002 — Connection handling & CLI args

**Status:** Todo
**Priority:** High
**Estimate:** S

## Goal
Accept a Redis URL and the core CLI flags.

## Tasks
- [ ] Positional arg: connection URL (`redis://...`, `rediss://...`, `unix://...`)
- [ ] Fallback to `REDIS_URL` env var if no arg provided
- [ ] Flags: `--db` (csv of db numbers, default `0`), `--pattern`, `--exclude`, `--ops` (default `set,del,expire,expired`)
- [ ] Flags: `--json`, `--no-color`, `--no-time`, `--verbose`, `--max-width` (default 80)
- [ ] Flags: `--redact` (csv of key globs, e.g. `session:*,token:*`)
- [ ] Flags: `--with-values`, `--monitor`, `--log-file PATH`
- [ ] Respect `NO_COLOR` env var
- [ ] Validate connection on startup (`PING`); print friendly error if unreachable

## Acceptance
- `redistail --help` lists every flag with sensible help text
- Bad URL → clean error, exit 2
- Unreachable Redis → clean error, exit 2

## Notes
- Settings should land in `redistail/options.py` as a frozen dataclass with helpers like `parse_ops`, `parse_csv_tuple`, `Settings.resolve_url`, `Settings.resolve_color` — same shape as pgtail's.

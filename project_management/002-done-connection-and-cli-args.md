# 002 — Connection handling & CLI args

**Status:** Done
**Priority:** High
**Estimate:** S

## Goal
Accept a Redis URL and the core CLI flags.

## Tasks
- [x] Positional arg: connection URL (`redis://...`, `rediss://...`, `unix://...`)
- [x] Fallback to `REDIS_URL` env var if no arg provided
- [x] Flags: `--db` (csv of db numbers, default `0`), `--pattern`, `--exclude`, `--ops` (default `set,del,expire,expired`)
- [x] Flags: `--json`, `--no-color`, `--no-time`, `--verbose`, `--max-width` (default 80)
- [x] Flags: `--redact` (csv of key globs, e.g. `session:*,token:*`)
- [x] Flags: `--with-values`, `--monitor`, `--log-file PATH`
- [x] Respect `NO_COLOR` env var
- [x] Validate connection on startup (`PING`); print friendly error if unreachable

## Acceptance
- `redistail --help` lists every flag with sensible help text
- Bad URL → clean error, exit 2
- Unreachable Redis → clean error, exit 2

## Notes
- Settings should land in `redistail/options.py` as a frozen dataclass with helpers like `parse_ops`, `parse_csv_tuple`, `Settings.resolve_url`, `Settings.resolve_color` — same shape as pgtail's.

## Completion notes
- Added `redistail/options.py` with frozen `Settings` dataclass (URL, dbs, patterns/exclude, ops, output flags, redact, with_values, monitor, log_file, collapse settings) and helpers `parse_ops`, `parse_csv_tuple`, `parse_db_list`, `Settings.resolve_url`, `Settings.resolve_color`.
- `parse_ops` does not hard-validate against a fixed set (Redis modules can emit custom event names); it lowercases + dedupes. A `KNOWN_OPS` constant lists the well-known events for documentation / future "did you mean?" hints.
- `parse_db_list` accepts 0–255 (Redis default max is 16, but some setups raise this) and rejects negatives / non-integers with a clear error.
- Added `redistail/connection.py` with `make_client` (pure constructor, no I/O) and `validate_connection` (PING + INFO + ACL WHOAMI). URL prefix validation rejects anything that isn't `redis://`, `rediss://`, or `unix://`. All Redis errors are wrapped in a friendly `ConnectionError_`.
- CLI uses Typer with `invoke_without_command=True`. Bad URL / unreachable Redis / invalid `--db` all exit 2. `--version` exits 0.
- Tests: 22 unit tests in `test_cli_args.py` + `test_connection.py` covering every flag in `--help`, env fallback, NO_COLOR, op parsing, db parsing, URL shape validation, and unreachable-URL behavior.

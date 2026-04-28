# 005 — Event formatting & colors

**Status:** Done
**Priority:** High
**Estimate:** M

## Goal
Render `KeyEvent`s as the colored, human-readable lines described in the README spec.

## Tasks
- [x] Write events (SET, HSET, LPUSH, SADD, ZADD, XADD, ...) → green `OP key {value summary}`
- [x] Delete-class events (DEL, UNLINK) → red `DEL key`
- [x] Expiration events (EXPIRE, PEXPIRE) → blue `EXPIRE key`
- [x] Lifecycle events (`expired`, `evicted`) → magenta
- [x] Other (RENAME, MOVE, COPY) → cyan
- [x] Optional leading timestamp `HH:MM:SS` (toggle `--no-time`)
- [x] `--verbose` adds `db=N channel=__keyevent@N__:set`
- [x] Truncate long values to `--max-width` with `…`
- [x] JSON renderer (`--json`) emits one compact JSON object per line
- [x] Plain renderer when `--no-color` or non-TTY stdout
- [x] `--log-file` writes plain (no-ANSI) copy in parallel
- [x] When `--with-values` is on, render the fetched value with type-aware formatting (string → quoted; hash → `{k: v, ...}`; list → `[a, b, ...]`; set → `{a, b}`; zset → `[(member, score), ...]`)

## Acceptance
- Visual check matches the README example output
- `redistail --json | jq .` works
- Piping to a file produces no ANSI escape codes

## Completion notes
- Added `redistail/format.py` with `op_color(op)` (categorizes 50+ Redis events into green/red/blue/magenta/cyan/white) and `render_value(value, value_type, ...)` (type-aware: string → quoted, hash → `{k: v, ...}`, list → `[a, b]`, set → sorted `{a, b}`, zset → `[(member, score)]`, stream → `[(id, fields)]`).
- `Renderer` class wraps `rich.console.Console` for colored stdout and an optional `log_file` tee that strips ANSI before writing. TTY auto-detection: color is forced off when stdout isn't a TTY, when `--no-color` is set, or when `$NO_COLOR` is in the environment.
- Redaction acts on the **key**, not the column name (Redis-appropriate): keys matching any `--redact` glob have their value rendered as `***` in both text and JSON output.
- Verbose mode prepends `db=N channel=__keyevent@N__:OP` after the key.
- Collapser hooks (`extra={'collapsed_count': N}` and `extra={'collapse_notice': True}`) are recognized today so ticket 007's plug-in is trivial.
- EXPIRE events render without a TTL value because Redis's keyspace notification doesn't carry the seconds; surfacing it would require an extra TTL round-trip and racing the key against the actual expiration. Documented as a known limitation — future enhancement could fetch TTL when `--with-values` is set.
- Tests: 26 new unit tests in `test_format.py` covering every op-color category, all six value-type renderers, truncation, redaction (positive + negative match), `--no-color` ANSI stripping, `--verbose` channel injection, collapser summary lines, and JSON output (basic, no-value-on-DEL, redaction, hash, collapsed). Timezone-portable HH:MM:SS assertions.
- Verified end-to-end against `redis:7` Docker container: SET / HSET / EXPIRE / DEL all rendered correctly, hash value formatted as `{name: bob, age: 30}`, `token:*` glob redacted to `***`, plain output (`--no-color`) contains zero ANSI escapes.

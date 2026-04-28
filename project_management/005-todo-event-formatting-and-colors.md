# 005 — Event formatting & colors

**Status:** Todo
**Priority:** High
**Estimate:** M

## Goal
Render `KeyEvent`s as the colored, human-readable lines described in the README spec.

## Tasks
- [ ] Write events (SET, HSET, LPUSH, SADD, ZADD, XADD, ...) → green `OP key {value summary}`
- [ ] Delete-class events (DEL, UNLINK) → red `DEL key`
- [ ] Expiration events (EXPIRE, PEXPIRE) → blue `EXPIRE key  ttl: 900s`
- [ ] Lifecycle events (`expired`, `evicted`) → magenta
- [ ] Other (RENAME, MOVE, COPY) → cyan
- [ ] Optional leading timestamp `HH:MM:SS` (toggle `--no-time`)
- [ ] `--verbose` adds `db=N channel=__keyevent@N__:set`
- [ ] Truncate long values to `--max-width` with `…`
- [ ] JSON renderer (`--json`) emits one compact JSON object per line
- [ ] Plain renderer when `--no-color` or non-TTY stdout
- [ ] `--log-file` writes plain (no-ANSI) copy in parallel
- [ ] When `--with-values` is on, render the fetched value with type-aware formatting (string → quoted; hash → `{k: v, ...}`; list → `[a, b, ...]`; set → `{a, b}`; zset → `[(member, score), ...]`)

## Acceptance
- Visual check matches the README example output
- `redistail --json | jq .` works
- Piping to a file produces no ANSI escape codes

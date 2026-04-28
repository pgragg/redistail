# 004 — Keyspace notification stream

**Status:** Done
**Priority:** High
**Estimate:** L

## Goal
Subscribe via `redis.client.PubSub`, decode keyspace and keyevent messages,
and yield typed `KeyEvent`s. This is the redistail analog of pgtail's
logical-replication stream.

## Tasks
- [x] For each db in `--db`, build the pattern set: `__keyspace@<db>__:*` and `__keyevent@<db>__:*`
- [x] `PSUBSCRIBE` to those patterns on a dedicated connection
- [x] Parse incoming messages:
  - keyspace channel → `(db, key, event_name)` where `event_name` comes from the message body
  - keyevent channel → `(db, event_name, key)` where `key` is the message body
- [x] De-dup: each logical change shows up on both channels; pick one as the source-of-truth and discard the other
- [x] When `--with-values` is set, opportunistically `GET`/`HGETALL`/`LRANGE`/etc. based on `TYPE <key>`
- [x] Yield typed `KeyEvent` objects (op, db, key, ts, value, channel)
- [x] Implement `--monitor` alternative path that parses `MONITOR` lines into the same `KeyEvent` shape (write commands only — drop reads)
- [x] On Ctrl-C: stop the stream, close pub/sub, exit 0

## Acceptance
- `SET foo bar` / `DEL foo` / `EXPIRE foo 10` in `redis-cli` produces a stream of `KeyEvent`s in real time
- Ctrl-C exits cleanly with no zombie connections (`CLIENT LIST` is clean)
- `--monitor` mode produces `KeyEvent`s with the same shape, modulo the lack of `expired` / `evicted` events that only keyspace notifications surface

## Notes
- `expired` and `evicted` events are *only* available via keyspace notifications, never via MONITOR — call this out in `--monitor` help text.
- The `redis-py` PubSub `.get_message(ignore_subscribe_messages=True, timeout=...)` loop is the simplest correct shape; consider `run_in_thread` only if it simplifies the shutdown path.

## Completion notes
- Added `redistail/events.py` with the frozen `KeyEvent` dataclass: `op, db, key, ts, value, value_type, channel, source, extra`. `qualified` property returns `"<db>:<key>"`.
- Added `redistail/subscriber.py` with three layers:
  1. **Pure parsers**: `parse_keyevent_channel`, `parse_keyspace_channel`, `parse_monitor_line`, `monitor_line_to_event`. All unit-testable without a live Redis.
  2. **Stream functions**: `stream_keyspace_events(settings)` uses a single `PSUBSCRIBE` connection and only listens on `__keyevent@<db>__:*` (the keyevent channel is the source-of-truth: event name in the channel, key in the body — so we never need to de-dup against the keyspace channel). `stream_monitor_events(settings)` drives `client.monitor()` and synthesizes `KeyEvent`s from each line.
  3. **Dispatcher**: `stream_events(settings)` picks one based on `settings.monitor`.
- `--with-values`: opportunistic TYPE-then-fetch on a separate connection (`SELECT` to the right db, then GET/HGETALL/LRANGE/SMEMBERS/ZRANGE/XREVRANGE based on type). Skipped for ops where the key is already gone (`del`, `unlink`, `expired`, `evicted`, `flushdb`). Failures are swallowed; the event still flows with `value=None`.
- MONITOR mapping: 50+ mutating commands map to canonical event names (`SETEX`/`PSETEX`/`SETNX` → `set`, `UNLINK`/`GETDEL` → `del`, `INCR`/`DECR` → `incrby`/`decrby`, etc.). All non-mutating commands (`GET`, `PING`, `MONITOR`, etc.) are dropped. `FLUSHDB`/`FLUSHALL` synthesize `key="*"` since they have no key argument.
- IPv6-safe MONITOR line regex: `[::1]:6379` clients contain a `]` of their own, so the bracket section uses non-greedy matching with the constraint that the closing bracket is followed by `" ` (every MONITOR command starts with a double-quoted token).
- Cleanup: pubsub.close() and client.close() in a `finally` block; `KeyboardInterrupt` in the CLI prints a clean shutdown banner and exits 0.
- Tests: 28 new unit tests in `test_subscriber.py` (channel parsers, MONITOR line parser including IPv6 and quoted-arg-with-space, MONITOR → KeyEvent mapping for sets/dels/reads/aliases/unknown commands/flushdb) and 4 in `test_events.py` (KeyEvent basics, `qualified`, frozen, default-factory isolation).
- CLI now actually streams: replaces the placeholder exit with a `for event in stream_events(settings)` loop. Output is intentionally minimal at this layer (`HH:MM:SS  OP  db=N key`) — colored / JSON / collapse-aware rendering lands in tickets 005-007.

# 004 — Keyspace notification stream

**Status:** Todo
**Priority:** High
**Estimate:** L

## Goal
Subscribe via `redis.client.PubSub`, decode keyspace and keyevent messages,
and yield typed `KeyEvent`s. This is the redistail analog of pgtail's
logical-replication stream.

## Tasks
- [ ] For each db in `--db`, build the pattern set: `__keyspace@<db>__:*` and `__keyevent@<db>__:*`
- [ ] `PSUBSCRIBE` to those patterns on a dedicated connection
- [ ] Parse incoming messages:
  - keyspace channel → `(db, key, event_name)` where `event_name` comes from the message body
  - keyevent channel → `(db, event_name, key)` where `key` is the message body
- [ ] De-dup: each logical change shows up on both channels; pick one as the source-of-truth and discard the other
- [ ] When `--with-values` is set, opportunistically `GET`/`HGETALL`/`LRANGE`/etc. based on `TYPE <key>`
- [ ] Yield typed `KeyEvent` objects (op, db, key, ts, value, channel)
- [ ] Implement `--monitor` alternative path that parses `MONITOR` lines into the same `KeyEvent` shape (write commands only — drop reads)
- [ ] On Ctrl-C: stop the stream, close pub/sub, exit 0

## Acceptance
- `SET foo bar` / `DEL foo` / `EXPIRE foo 10` in `redis-cli` produces a stream of `KeyEvent`s in real time
- Ctrl-C exits cleanly with no zombie connections (`CLIENT LIST` is clean)
- `--monitor` mode produces `KeyEvent`s with the same shape, modulo the lack of `expired` / `evicted` events that only keyspace notifications surface

## Notes
- `expired` and `evicted` events are *only* available via keyspace notifications, never via MONITOR — call this out in `--monitor` help text.
- The `redis-py` PubSub `.get_message(ignore_subscribe_messages=True, timeout=...)` loop is the simplest correct shape; consider `run_in_thread` only if it simplifies the shutdown path.

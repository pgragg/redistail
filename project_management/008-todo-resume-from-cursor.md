# 008 — Resume mode (best-effort)

**Status:** Todo
**Priority:** Low
**Estimate:** S

## Goal
Provide a "best-effort resume" experience analogous to pgtail's persistent
slots. Note that **Redis pub/sub is fire-and-forget** — there is no real
durable cursor like a logical replication slot. Be honest about that in the
docs.

## Tasks
- [ ] `--resume FILE` writes the last-seen `(db, key, op, ts)` to a small state file as a heartbeat
- [ ] On restart with the same `--resume FILE`, print a yellow notice: `last seen <op> <key> at <ts>; events between then and now are LOST (Redis pub/sub is non-durable)`
- [ ] Optional: if `redis-stream` mode is configured (future ticket), use a stream consumer group instead — that *is* durable
- [ ] `--drop-resume FILE` helper to delete the state file

## Acceptance
- Restarting with `--resume` shows the heartbeat banner and continues
- The README clearly explains the durability caveat (it is *not* equivalent to pgtail's persistent slot)

## Notes
- This ticket exists to keep numbering aligned with pgtail's 008 (persistent slot mode), but the semantics are weaker. If we end up not shipping it, mark `canceled` rather than `done`.

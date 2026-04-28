# 016 — Redis Streams consumer mode (post-v1)

**Status:** Backlog
**Priority:** Low
**Estimate:** M

## Goal
For users who want a *durable* tail — equivalent in spirit to pgtail's
persistent replication slot — consume from a Redis Stream that the user has
configured their app to write to.

## Tasks
- [ ] `--stream NAME` flag: `XREAD` from the named stream (or `XREADGROUP` if `--group` is set)
- [ ] Render stream entries with the same `KeyEvent`-shaped output
- [ ] Document the difference vs keyspace notifications: streams are durable, keyspace notifications are not
- [ ] Optional: bridge mode that subscribes to keyspace notifications and `XADD`s into a stream, so the user gets durability after the fact

## Notes
This is the only path to "no missed events on restart" semantics on Redis.
Keyspace notifications can never offer that on their own.

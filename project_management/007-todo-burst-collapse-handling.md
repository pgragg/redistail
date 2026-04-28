# 007 — High-frequency burst collapsing

**Status:** Todo
**Priority:** Medium
**Estimate:** S

## Goal
Avoid drowning the terminal on hot-key bursts (e.g. a counter being INCR'd
in a tight loop, or a cache being repopulated).

## Tasks
- [ ] Track per `(op, key-prefix)` counts within a sliding window (1s)
- [ ] If a single op on a single key/prefix exceeds the threshold (default 1000) within the window, collapse remaining events into a summary line: `INCR counter:foo  1,247 events (collapsed in last 1s)`
- [ ] `--expand-all` flag bypasses collapsing
- [ ] Threshold configurable via `--collapse-threshold N` (default 1000)
- [ ] Define "key-prefix" as everything up to the last `:` (so `user:42` and `user:43` collapse together but `session:abc` doesn't)

## Acceptance
- A tight `INCR foo` loop produces one collapsed summary, not 10k lines
- `--expand-all` shows every event
- Different prefixes don't accidentally collapse together

## Notes
- Behaviorally similar to pgtail's `Collapser`, but per-second windowed instead of per-transaction (Redis has no transactions in the pgoutput sense).

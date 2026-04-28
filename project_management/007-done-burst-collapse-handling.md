# 007 — High-frequency burst collapsing

**Status:** Done
**Priority:** Medium
**Estimate:** S

## Goal
Avoid drowning the terminal on hot-key bursts (e.g. a counter being INCR'd
in a tight loop, or a cache being repopulated).

## Tasks
- [x] Track per `(op, key-prefix)` counts within a sliding window (1s)
- [x] If a single op on a single key/prefix exceeds the threshold (default 1000) within the window, collapse remaining events into a summary line: `INCR counter:foo  1,247 events (collapsed in last 1s)`
- [x] `--expand-all` flag bypasses collapsing
- [x] Threshold configurable via `--collapse-threshold N` (default 1000)
- [x] Define "key-prefix" as everything up to the last `:` (so `user:42` and `user:43` collapse together but `session:abc` doesn't)

## Acceptance
- A tight `INCR foo` loop produces one collapsed summary, not 10k lines
- `--expand-all` shows every event
- Different prefixes don't accidentally collapse together

## Notes
- Behaviorally similar to pgtail's `Collapser`, but per-second windowed instead of per-transaction (Redis has no transactions in the pgoutput sense).

## Completion notes
- Added `redistail/collapse.py` with `key_prefix(key)` (everything up to the last `:`, full key if no `:`) and the `Collapser` dataclass.
- Per `(op, prefix)` group is keyed by event timestamp truncated to the second. Within a window: first N ≤ threshold events pass through; the (N+1)th emits a single inline `… collapsing remainder after T events/s` notice; further events are silently swallowed.
- Three triggers fire the summary event (`extra={'collapsed_count': N}`, key=`prefix:*`, source=`synthetic`): (a) the next event in the same group lands in a later second, (b) `_sweep_expired` runs at the start of `process()` and finds groups whose window rolled while they went quiet, (c) `flush()` is called at shutdown.
- `--expand-all` short-circuits the collapser into a passthrough. Synthetic events (something already marked `collapsed_count` / `collapse_notice`) also pass through unchanged.
- Renderer (`format.py`) already handled the synthetic shape from ticket 005, so this ticket only added the producer.
- CLI runs each event through `event_allowed` → `collapser.process` → `renderer.emit`, and calls `collapser.flush()` after the stream ends and on Ctrl-C so dangling summaries are not lost.
- Tests: 13 new unit tests in `test_collapse.py` covering `key_prefix` edge cases (no colon, trailing colon, nested), pass-through under threshold, `--expand-all` no-op, the collapse-notice + suppression sequence, summary on flush, summary on window-roll, prefix isolation (`user:*` vs `session:*`), op isolation (SET vs DEL on same prefix), and synthetic-event pass-through.
- Verified live against `redis:7` with `collapse_threshold=5`: 20 rapid SETs on `user:0`..`user:19` produced exactly 5 pass-throughs + 1 inline notice + 1 final `20 events (collapsed)` summary line, instead of 20 individual lines.

# 014 — Value-level filters (post-v1)

**Status:** Backlog
**Priority:** Low
**Estimate:** M

## Goal
Filter events by fetched value content, e.g. `--where 'value contains "error"'`
or `--where 'hash.status == "pending"'`.

## Tasks
- [ ] Mini expression parser (eq, neq, contains, like, json-path for hashes/json strings)
- [ ] Apply per-event filters client-side after `--with-values` fetch
- [ ] Document performance caveat (filtering happens after decode + extra round-trip)
- [ ] Make sure the filter short-circuits the round-trip when the predicate only references the key, not the value

## Notes
Explicitly out of v1.

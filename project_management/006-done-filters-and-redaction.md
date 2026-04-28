# 006 — Filters & redaction

**Status:** Done
**Priority:** Medium
**Estimate:** S

## Goal
Apply the user's `--db`, `--pattern`, `--exclude`, `--ops`, and `--redact` selections.

## Tasks
- [x] Glob matching for `--pattern` / `--exclude` (e.g. `session:*`, `user:*:profile`)
- [x] Drop events whose op isn't in `--ops`
- [x] Drop events whose db isn't in `--db`
- [x] Redaction: replace value with `***` for any key matching a `--redact` glob (case-sensitive — Redis keys are binary)
- [x] Default redact list: empty (Redis keys are app-specific; don't guess)
- [x] Pure-function predicates in `redistail/filters.py`: `db_allowed`, `key_allowed`, `op_allowed`, composite `event_allowed`, plus `should_redact`

## Acceptance
- `--pattern 'user:*'` only shows events on keys starting with `user:`
- `--exclude 'cache:*'` hides cache churn
- `--ops set,del` shows only writes and deletes
- Redacted keys render as `value: ***` even in `--json`

## Notes
- Use `fnmatch.fnmatchcase` (not `fnmatch.fnmatch`) — Redis keys are binary-safe and case-sensitive.
- Filtering happens after parsing the keyspace message but before formatting / `--with-values` lookup, so we don't pay the round-trip on filtered keys.

## Completion notes
- Added `redistail/filters.py` with five pure predicates: `db_allowed`, `key_allowed` (include + exclude with exclude winning), `op_allowed` (case-insensitive), `should_redact`, and the composite `event_allowed`. All use `fnmatch.fnmatchcase` for case-sensitive binary-safe glob matching.
- Filtering wired into the subscriber **before** the `--with-values` round-trip in both keyspace and MONITOR paths — we build a probe `KeyEvent` with no value, run `event_allowed`, and only fetch the value if it passes. Keeps the value-fetch cost proportional to surfaced events, not all events on the server.
- `format.py` redaction now reuses `filters.should_redact` instead of duplicating the glob match.
- Tests: 27 new unit tests in `test_filters.py` covering each predicate's match / miss / empty-tuple / case-sensitivity / wildcard behavior, plus the composite `event_allowed` for db / key / op / pattern combinations.
- Verified live against `redis:7`: with `--pattern user:* --ops set,del --redact session:*`, of 7 mixed writes (HSET on `user:2`, SET on `session:abc` and `cache:y` mixed in), only the four `user:*` SET/DEL events surfaced; values were fetched only for those (no wasted round-trips on filtered keys).

# 006 — Filters & redaction

**Status:** Todo
**Priority:** Medium
**Estimate:** S

## Goal
Apply the user's `--db`, `--pattern`, `--exclude`, `--ops`, and `--redact` selections.

## Tasks
- [ ] Glob matching for `--pattern` / `--exclude` (e.g. `session:*`, `user:*:profile`)
- [ ] Drop events whose op isn't in `--ops`
- [ ] Drop events whose db isn't in `--db`
- [ ] Redaction: replace value with `***` for any key matching a `--redact` glob (case-sensitive — Redis keys are binary)
- [ ] Default redact list: empty (Redis keys are app-specific; don't guess)
- [ ] Pure-function predicates in `redistail/filters.py`: `db_allowed`, `key_allowed`, `op_allowed`, composite `event_allowed`, plus `should_redact`

## Acceptance
- `--pattern 'user:*'` only shows events on keys starting with `user:`
- `--exclude 'cache:*'` hides cache churn
- `--ops set,del` shows only writes and deletes
- Redacted keys render as `value: ***` even in `--json`

## Notes
- Use `fnmatch.fnmatchcase` (not `fnmatch.fnmatch`) — Redis keys are binary-safe and case-sensitive.
- Filtering happens after parsing the keyspace message but before formatting / `--with-values` lookup, so we don't pay the round-trip on filtered keys.

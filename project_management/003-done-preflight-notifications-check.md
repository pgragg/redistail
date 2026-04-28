# 003 — Preflight: notify-keyspace-events & ACL check

**Status:** Done
**Priority:** High
**Estimate:** S

## Goal
Detect missing prerequisites and tell the user exactly how to fix them.

## Tasks
- [x] Run `CONFIG GET notify-keyspace-events` — fail fast if empty or missing `K` and `E` flags
- [x] Check the connecting user can `PSUBSCRIBE` (`ACL WHOAMI` + `ACL GETUSER`)
- [x] If misconfigured, print copy-pasteable fix:
  ```
  redis-cli CONFIG SET notify-keyspace-events AKE
  ```
- [x] Detect managed-provider hints (ElastiCache, Memorystore, Upstash, Redis Cloud) from hostname and link to provider-specific docs
- [x] Exit code 3 for preflight failure (distinct from connection failure)
- [x] If `--monitor` is used, skip the keyspace check but verify `MONITOR` is in the user's allowed commands

## Acceptance
- Running against a stock local Redis with `notify-keyspace-events ""` shows a clear, actionable error
- Running with `--monitor` against a user who lacks `MONITOR` shows a clear, actionable error

## Completion notes
- Added `redistail/preflight.py` with `run_preflight(url, *, monitor_mode)`. Returns a `PreflightInfo` on success or raises `PreflightError` (exit 3 in the CLI).
- `parse_notify_flags(raw)` extracts `(has_K, has_E)` from the bitmask string; the keyevent channel ('E') is required because that's where the operation name lives.
- ACL handling: `ACL WHOAMI` to get the user, then `ACL GETUSER` to inspect commands. Best-effort — pre-ACL servers (Redis < 6) and minimal deployments may lack `ACL GETUSER`, in which case we optimistically pass and let any actual NOPERM surface at subscribe time. `_command_in_category` resolves Redis ACL category aliases (`+@pubsub`, `+@admin`, `+@all`).
- `detect_provider(host)` matches on hostname substrings: ElastiCache, MemoryDB, Memorystore, Azure Cache for Redis, Upstash, Redis Cloud, DigitalOcean Managed Redis. Each maps to the provider's notification-config doc URL.
- Fix-up text is copy-pasteable: `redis-cli CONFIG SET notify-keyspace-events AKE` for the flag fix, `ACL SETUSER <user> +psubscribe +subscribe ~__key*__:*` for the ACL fix, `ACL SETUSER <user> +monitor` for `--monitor` mode.
- CLI wires preflight in after `validate_connection`. Connection failures still exit 2; preflight failures exit 3.
- Tests: 20 new unit tests in `test_preflight.py` covering hostname parsing, all provider matchers, flag parsing edge cases, fix-up text content, ACL category resolution, and `_flat_pairs_to_dict` helper.

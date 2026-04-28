# 003 — Preflight: notify-keyspace-events & ACL check

**Status:** Todo
**Priority:** High
**Estimate:** S

## Goal
Detect missing prerequisites and tell the user exactly how to fix them.

## Tasks
- [ ] Run `CONFIG GET notify-keyspace-events` — fail fast if empty or missing `K` and `E` flags
- [ ] Check the connecting user can `PSUBSCRIBE` (`ACL WHOAMI` + `ACL GETUSER`)
- [ ] If misconfigured, print copy-pasteable fix:
  ```
  redis-cli CONFIG SET notify-keyspace-events AKE
  ```
- [ ] Detect managed-provider hints (ElastiCache, Memorystore, Upstash, Redis Cloud) from hostname and link to provider-specific docs
- [ ] Exit code 3 for preflight failure (distinct from connection failure)
- [ ] If `--monitor` is used, skip the keyspace check but verify `MONITOR` is in the user's allowed commands

## Acceptance
- Running against a stock local Redis with `notify-keyspace-events ""` shows a clear, actionable error
- Running with `--monitor` against a user who lacks `MONITOR` shows a clear, actionable error

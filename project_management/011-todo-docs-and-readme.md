# 011 — Docs & README polish

**Status:** Todo
**Priority:** High
**Estimate:** S

## Goal
Make it trivial for a new user to get redistail running in 30 seconds.

## Tasks
- [x] README with:
  - [x] 30-second quickstart (install + run)
  - [x] `notify-keyspace-events` setup snippet
  - [x] Managed-provider notes (ElastiCache, Memorystore, Upstash, Redis Cloud, Azure, DigitalOcean)
  - [x] Full flag reference
  - [x] Example `.redistail.toml`
  - [x] Troubleshooting section (common errors → fixes)
  - [x] FAQ: "does this modify my Redis?" (read-only, no scripts)
- [ ] Animated GIF / asciinema demo
- [x] CHANGELOG.md
- [x] CONTRIBUTING.md

## Acceptance
- A teammate with no prior context can install and see colored events within 30 seconds on a local Redis

## Notes
- The README in this repo is already drafted at scaffold time — this ticket exists to do the GIF/demo capture and any post-implementation copy edits once the CLI behavior matches the spec.

## Smoketest follow-ups (2025-04-28)

Discovered while writing `docs/smoketest.md`:

- **README is stale on defaults.** Update to reflect:
  - `--ops` default is now `all` (empty allowlist), not `set,del,expire,expired`.
  - `--with-values` is now on by default; document `--no-values` to opt out.
- **Stream values render as `b'...'` byte literals.** `XADD` events show
  `[(1777408195387-0, {b'order_id': b'ord_77232', ...})]`. The
  hash/list/set/zset paths decode bytes via `_to_text`; stream entries in
  `_fetch_value` should do the same.
- **`EXPIRE` re-shows the full value** (because the key still exists when
  the value-fetch runs). Arguably fine; consider suppressing for `expire`
  ops or rendering just the new TTL instead of the stored value.
- **CLI flag-order quirk:** `redistail redis://... --no-color` errors with
  `No such command '--no-color'` (typer treats trailing args as a
  subcommand). Document or fix so flags can follow the URL.

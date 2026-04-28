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

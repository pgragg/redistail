# 02_redistail

A colored CLI that tails Redis key changes (SET/DEL/EXPIRE/HSET/...) via
keyspace notifications.

## Tech Stack
- Python 3.11+
- `redis` v5 (native pub/sub + MONITOR support)
- Built-in keyspace notifications (no modules required)
- Distributed via `pipx` / `pip` / `uv tool`

## Status Conventions
Tickets use Linear's default statuses in the filename prefix:
- `backlog` — Not yet planned
- `todo` — Planned, ready to pick up
- `in-progress` — Actively being worked on
- `in-review` — PR open / awaiting review
- `done` — Merged / shipped
- `canceled` — Won't do

Format: `NNN-status-short-slug.md`

## Tickets
See individual `.md` files in this folder.

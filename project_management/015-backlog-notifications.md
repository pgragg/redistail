# 015 — Notifications on events (post-v1)

**Status:** Backlog
**Priority:** Low
**Estimate:** M

## Goal
Trigger a webhook / desktop notification / shell command when a matching event fires.

## Tasks
- [ ] `--on-match 'key=session:*,op=expired' --exec 'osascript -e "display notification ..."'`
- [ ] Webhook variant: `--webhook URL`
- [ ] Rate limiting to avoid notification storms (especially with `expired` floods at TTL boundaries)

## Notes
Explicitly out of v1.

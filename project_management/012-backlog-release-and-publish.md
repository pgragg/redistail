# 012 — Release & publish to PyPI

**Status:** Backlog
**Priority:** Medium
**Estimate:** S

## Goal
Ship v0.1.0.

## Tasks
- [ ] Tag `v0.1.0`
- [ ] GitHub Actions release workflow: build sdist + wheel, publish to PyPI via trusted publishing (OIDC)
- [ ] Verify `pipx install redistail` works from clean machine
- [ ] Create GitHub Release with changelog notes + demo GIF
- [ ] Post in relevant communities (r/redis, HN Show, Lobsters) — optional

## Acceptance
- `pipx install redistail` from PyPI yields a working binary
- v0.1.0 release page is live

## Notes
- Mirror pgtail's decision to delay publishing until the implementation has been dogfooded.

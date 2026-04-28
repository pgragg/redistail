# redistail — implement the v0.1 roadmap

Work through the `project_management/` tickets in order, mirroring how pgtail
was built. Keep the project compilable and `pytest` green at every step.

## Working directory
`~/pi/02_redistail`

## Ground rules
- One ticket per iteration where possible. Big tickets (004, 005, 010) may
  span multiple iterations.
- After each ticket: rename the ticket file from `NNN-todo-...md` →
  `NNN-done-...md`, fill in a **Completion notes** section at the bottom,
  flip the **Status** field to `Done`, and check off the task boxes.
- After each ticket: `pytest -m "not integration"` MUST pass. `ruff check .`
  and `ruff format --check .` MUST pass.
- After each ticket: `git add -A && git commit -m "NNN: <slug>"` with the
  ticket number as the commit prefix.
- Update `CHANGELOG.md` under `[Unreleased]` for any user-visible change.
- Don't invent scope — implement what each ticket says, no more. If you
  discover a missing requirement, add it as a new backlog ticket rather
  than smuggling it in.
- Skeleton stub modules already exist under `redistail/` — flesh them out,
  don't create parallel modules.

## Reference
- `~/pi/00_pgtail/` is the reference implementation. When in doubt, look at
  how pgtail solved the same shape of problem (e.g. its `Settings`
  dataclass, its filter predicates, its collapser, its config loader). Do
  not blindly copy — Redis semantics differ — but the *structure* should
  feel familiar.

## Checklist (one-to-one with project_management/)
- [x] 001 Project scaffold (already done)
- [x] 002 Connection handling & CLI args (`redistail/options.py`, `cli.py`, `connection.py`)
- [ ] 003 Preflight: `notify-keyspace-events` & ACL check (`preflight.py`)
- [ ] 004 Keyspace notification stream (`subscriber.py`, `events.py`) — biggest ticket
- [ ] 005 Event formatting & colors (`format.py`)
- [ ] 006 Filters & redaction (`filters.py`)
- [ ] 007 High-frequency burst collapsing (`collapse.py`)
- [ ] 008 Resume mode (best-effort) — implement OR mark canceled with rationale
- [ ] 009 Config file support (`config.py`)
- [ ] 010 Tests & CI — fill out unit tests for everything above + integration test using `fakeredis` / `testcontainers`
- [ ] 011 Docs & README polish — update README to match actual behavior, add demo asciicast if practical (skip the GIF if it requires a binary tool)
- [ ] 012 Release & publish — leave as `backlog` (mirroring pgtail's choice). Don't auto-publish.

## Per-iteration loop
1. Pick the next unchecked ticket.
2. Read the ticket file in full.
3. Implement it. Write tests as you go.
4. Run `pytest -m "not integration" -q` and `ruff check . && ruff format .`.
5. Rename the ticket file to `NNN-done-...md`, update Status + Completion notes.
6. Update CHANGELOG.md.
7. `git add -A && git commit -m "NNN: <slug>"`.
8. Tick the box in this file's checklist and add a Verification line.
9. `ralph_done`.

## Verification log
(Append as you go: ticket #, commit hash, test count, anything notable.)

- 001: commit `1132783`, 3 smoke tests passing, scaffold confirmed via `redistail --help`.
- 002: 26 unit tests passing, ruff + format clean. Settings dataclass + URL/db/op parsers + connection PING validation. All flags from spec land in `--help`.

## Completion criteria
- All checklist items 002–011 are checked.
- 012 stays in backlog (do not publish).
- Final `pytest -m "not integration"` shows ≥ ~30 unit tests passing.
- `ruff check .` and `ruff format --check .` both clean.
- README's flag list and behavior match the implemented CLI.
- Output `<promise>COMPLETE</promise>` once all of the above hold.

## Notes
(Update with progress, decisions, blockers, surprises.)

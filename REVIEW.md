# Review rules

For reviewer agents reviewing a PR in this repository. `CLAUDE.md` has the same rules under "Review rules"; keep the two in sync. Decisions are recorded in `docs/decisions.md`.

## What to flag

Flag only gaps that affect:

- correctness,
- security, or
- the decisions in `docs/decisions.md`.

Everything else, such as style and "could also handle X", goes in **one optional list** at the end of the review. Optional items are not fixed by default.

## Before a finding is fixed

Ask whether the fix makes the code simpler or more complex. Prefer fixes that delete code.

## The PR itself

- **Size:** under about 400 changed lines, excluding tests and fixtures. Review fixes that would push a PR over the limit go in the next PR.
- **Description:** it starts with at most 10 lines: what changed, "Read these first" (the 1-3 core files or functions the owner must read) and the decisions needed. Everything else is under "Details". It states what was removed or simplified.
- **Packages:** a new package needs the owner's approval and must exist on PyPI.

## Code the owner always reads

- the `store.py` schema and transactions
- the MCP tool interfaces
- quote and `record_check` validation
- eval scoring code

A PR that changes one of them names it under "Read these first".

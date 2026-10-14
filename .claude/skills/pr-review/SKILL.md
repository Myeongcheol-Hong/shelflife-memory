---
name: pr-review
description: Review checklist for a Shelf Life pull request. Use when reviewing a PR or a diff. Produces a must-fix list (correctness, security, docs/decisions.md) and one optional list.
---

# PR review

Review the diff against its PR description, `CLAUDE.md` and `docs/` (`design.md`, `decisions.md`, `roadmap.md`).

## Must fix

Only gaps that affect:

- **correctness**: the code does the wrong thing for an input it will really get;
- **security**: for example an unchecked URL or address, a path or SQL built from input, a secret in the repo;
- **a decision** in `docs/decisions.md`, or a "Stop and ask" rule in `CLAUDE.md` (labels, decisions, dependencies).

A must-fix finding names a real caller or input that reaches the problem. If you cannot name one, it belongs in the optional list.

## Check

| Question | Where a hit goes |
|---|---|
| Could it be simpler? What can be deleted? | optional |
| Is a helper duplicated, here or elsewhere in the repo? | optional |
| Does the PR change things outside its scope? | optional |
| Does a test pass for the wrong reason (it would still pass if the code it covers were broken)? | optional; a bug it hides is a correctness finding |
| Does a test duplicate another, or test a case that cannot happen? Propose tests to delete. | optional |
| Is there defensive code for a case that cannot happen? | optional |
| Is there a new dependency? | must fix without the maintainer's approval, otherwise optional |
| Does the description hide something: always-read code (see `CLAUDE.md`) changed but not under "Read these first", or a DB schema or stored-data change not marked ONE-WAY DOOR? | must fix |

Run the tests with `uv run pytest -q` (or the changed test files) when a finding depends on what they do.

## Output

Two lists and nothing else. Mark style, naming and "could also handle X" optional. Optional items are not fixed by default.

```
## Must fix
1. `path:line`: what is wrong. Input: the real caller or input that reaches it. Fix: the simplest fix, preferring one that deletes code.

## Optional
- `path:line`: the point, in one line. For a test to delete, say why it adds nothing.
```

Write "None." under a list that is empty.

# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3: the store, the six MCP tools, the PyPI, GitHub release and web page checks, and the write checks. Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- Open: #24, hardening from the external review, then the repo-presentation PR (README, this file, "maintainer" wording, roadmap order). Merge in that order; before the second merges, `main` is merged into it and this file is brought up to date.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9. Next is M5a: release timelines, dev/test split, smoke corpus.

## Waiting on the maintainer

- The M5a plan's five decisions (in the session's last message): the project list (about 70 candidates, cut to 50 + 20), the "latest" rules (PyPI: highest non-prerelease, non-yanked version by PEP 440; GitHub: the API's latest rule), the split (time only, or also hold out projects), `packaging` in a new `eval` dependency group, and `pythonpath = ["."]` for tests. The timeline collection script runs on the maintainer's Mac.

## Next session: start here

1. Check #24 and the repo-presentation PR (merged? comments? CI?).
2. With the M5a plan approved, build M5a. Eval rules are in CLAUDE.md: the dev/test split is fixed before any tuning, and every eval also runs on `eval/data/smoke/` in CI.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`, so a selector change can be told apart from a page change.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3 and the hardening from the external review (#24): the store, the six MCP tools, the PyPI, GitHub release and web page checks, and the write checks. Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- This file arrives with #25 (README, "maintainer" wording, roadmap in build order, `attribution.sessionUrl` off). M5a is being built next, in its own PR, which will carry this file's next version.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9. Next is M5a: release timelines, dev/test split, smoke corpus, and the maintainer's volatility labels for the replay claims.

## Waiting on the maintainer

- Nothing on #25. The M5a plan is answered: about 70 candidate projects in `projects.toml` (the maintainer cuts them to 50 + 20 and labels volatility while cutting, before any data is collected), the "latest" rules as proposed, a time-only split, `packaging` in an `eval` dependency group, and `pythonpath = ["."]`. The collection script runs on the maintainer's Mac.

## Next session: start here

1. Check that #25 and the M5a PR are merged.
2. Continue M5a. Eval rules are in CLAUDE.md: the dev/test split is fixed before any tuning, and every eval also runs on `eval/data/smoke/` in CI. The volatility labeling file is built for the maintainer to fill; never fill it.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`, so a selector change can be told apart from a page change. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

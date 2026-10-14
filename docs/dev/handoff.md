# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening from the external review (#24) and the repo presentation (#25: README, "maintainer" wording, roadmap in build order). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- The M5a PR is the session's last PR and carries this file.
- M5a so far: the project list (`eval/data/timelines/projects.toml`, 52 PyPI + 20 GitHub after the maintainer's cuts, all labeled but the four GitHub additions; tag patterns for graphiti, TypeScript, react and home-assistant), the collector, the "latest" rules and split (D11), the smoke corpus in CI and the data card. The first collection run is done on the Mac; no timeline data is committed yet.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. Label lazygit, starship, zed and hugo in `projects.toml`.
2. On the Mac, with `GITHUB_TOKEN` set (60 requests an hour without it is too few): `uv run python -m eval.replay.collect_timelines` again, then commit `eval/data/timelines/` to the M5a branch.
3. Read its `check:` lines and the tag patterns' "left out" lines. The rule stays for react, TypeScript and ollama (D11); for any other repository with disputed days, choose: cut it, keep the rule, or order by publication.

## Next session: start here

1. Check the M5a PR. Once the data is in, fill the data card's "Collected" line (counts, date, `check:` lines) and tick M5a's timeline and labeling items.
2. Then M6: the replay over the timelines, with the baseline policies. Create a project's claims only after its first release (data card, "Young projects"). Parse each PyPI version once at load (`latest_on()` parses on every call). Every eval also runs on `eval/data/smoke/` in CI; never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`; `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

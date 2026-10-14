# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening from the external review (#24) and the repo presentation (#25: README, "maintainer" wording, roadmap in build order). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- The M5a PR is the session's last PR and carries this file.
- M5a is complete on its branch: the project list (`eval/data/timelines/projects.toml`, 52 PyPI + 20 GitHub, all labeled; tag patterns for graphiti, TypeScript, react and home-assistant), the collector, the "latest" rules and split (D11), the timelines collected on 2026-10-14 (data card, "Collected"), the smoke corpus in CI and the data card. The roadmap's M5a items are ticked.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. Merge the M5a PR.
2. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11). It reads none, so on graphiti, TypeScript, react and home-assistant a live claim can see another product's release as the latest.

## Next session: start here

1. M6: the day-by-day replay over `eval/data/timelines/` with the baseline policies (never, every read, fixed 7 and 30 days, per-class), and the metrics in the roadmap. Build it on `latest_on()` and `changes()`; tune nothing on the test split.
2. Create a project's claims only after its first release (data card, "Young projects"). Parse each PyPI version once at load (`latest_on()` parses on every call; there are 12,141 PyPI versions). Every eval also runs on `eval/data/smoke/` in CI; never fill a label.
3. The four GitHub additions (lazygit, starship, zed, hugo) were labeled after the first collection run, the rest before any data (D11); M6 can report the per-class policy with and without them.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`; `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

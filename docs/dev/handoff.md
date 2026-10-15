# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26) and its follow-ups (#27), M6 (#28, #29, #30) and the outside-review fixes (#31). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- M6's run is `eval/results/2026-10-14-369cb77/`. With the labels as they are, fixed 30 is fresher than per-class in both splits (stale answers +8.6 points in test, +10.5 in dev, per-class minus fixed 30) at no detectably higher cost. Jitter's primary comparison says jitter helps. No class interval or policy changes because of a test result (D12).
- Open: the M7a PR (base `main`), which carries this file: `eval/runner.py`, the shared model runner (D13, decided), and in D12 the maintainer's M7 reporting addition (the selected adaptive point against fixed 30, paired, test and dev, and on the fixed-N curve).
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. The M5b proposal (`docs/dev/m5b-page-timelines.md`): the pages, the tracked values, and the D12 amendment for values that revert.
2. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. M7's adaptive per-claim policy (roadmap's next box): the family, dev grid, selection rule and label-free exploratory run are pre-registered in D12. Propose how the selected point is placed on the fixed-N curve before any run. No model is called.
2. Then the LLM-judged volatility policy: Claude labels each project through `eval/runner.py` (3 repeats), the replay runs per-class with those labels, and the volatility-impact comparison (design 6.0-3) puts them next to the maintainer's. Its results say that both label sets use present-day knowledge, so the comparison is of label quality, not foresight (D13).
3. Every eval also runs on `eval/data/smoke/` in CI, with a stub model for the model evals. Never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`. Since #31, `fetched_at` is set for pypi and github_release checks and for page errors too (the time before the fetch), so `fetched_at IS NOT NULL` no longer means a web_page judgment. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- The stale rule (D10 follow-up 20) compares fetch times to the second: of two fetches of one claim that start in the same second, only the first result recorded is kept.
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

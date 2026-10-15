# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26) and its follow-ups (#27), M6 (#28, #29, #30), the outside-review fixes (#31) and M7a, the shared model runner (#32, D13 decided). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- M6's run is `eval/results/2026-10-14-369cb77/`. With the labels as they are, fixed 30 is fresher than per-class in both splits at no detectably higher cost. No class interval or policy changes because of a test result (D12).
- Open: the M7b PR (base `main`), which carries this file: the adaptive policy (`eval/replay/adaptive.py`) and its run (`adaptive_run.py`): the dev grid, the selection on dev, the test run, the comparisons with per-class and fixed 30, the place on the fixed-N curve, and the label-free exploratory run. No real run yet; the smoke corpus runs it in CI.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. The M7b proposals in D12, before any run: whole-day waits rounded half up; how the selected point is placed on the fixed-N curve; the comparison with per-class next to fixed 30; the label-free run on test only; an error if no grid point fits. D12 also notes that with α at most 1 a claim waits `max` days until its first change, whatever its label.
2. The M5b proposal (`docs/dev/m5b-page-timelines.md`): the pages, the tracked values, and the D12 amendment for values that revert.
3. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. Once the M7b proposals are confirmed: `uv run python -m eval.replay.adaptive_run` on a clean tree (a few minutes), commit `eval/results/<run-id>-adaptive/` to the M7b PR, tick the roadmap's adaptive box, and report the selected point.
2. Then the LLM-judged volatility policy: Claude labels each project through `eval/runner.py` (3 repeats), the replay runs per-class with those labels, and the volatility-impact comparison (design 6.0-3) puts them next to the maintainer's. Its results say that both label sets use present-day knowledge, so the comparison is of label quality, not foresight (D13).
3. Every eval also runs on `eval/data/smoke/` in CI, with a stub model for the model evals. Never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`. Since #31, `fetched_at` is set for pypi and github_release checks and for page errors too (the time before the fetch), so `fetched_at IS NOT NULL` no longer means a web_page judgment. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- The stale rule (D10 follow-up 20) compares fetch times to the second: of two fetches of one claim that start in the same second, only the first result recorded is kept.
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

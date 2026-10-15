# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26) and its follow-ups (#27), M6 (#28, #29, #30), the outside-review fixes (#31), M7a, the shared model runner (#32, D13 decided), and M7b, the adaptive policy with its run (#33). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- M6's run is `eval/results/2026-10-14-369cb77/`. With the labels as they are, fixed 30 is fresher than per-class in both splits at no detectably higher cost. No class interval or policy changes because of a test result (D12).
- M7b's run is `eval/results/2026-10-15-e2d0e3d-adaptive/`. The point selected on dev (p=0.7 a=2 max=180) is staler than per-class and fixed 30 on test, and 11.2 points above the fixed-N curve at its cost (6.7 to 15.6).
- Open: the M7c PR (`feat/m7c-llm-labels`, base `main`), which carries this file: `eval/replay/llm_labels.py` and D14's proposals. No model has been called. And a docs PR proposing the budget-aware allocation in D12 (Cho & Garcia-Molina 2003), added after M7b's results; no code until the maintainer confirms it.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. D14's proposals, before any model call, including whether prompt v1 asks the question the maintainer answered when labeling.
2. The budget-aware allocation rule in D12 (the docs PR), before any code or run.
3. The M5b proposal (`docs/dev/m5b-page-timelines.md`): the pages, the tracked values, and the D12 amendment for values that revert.
4. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. After D14 is confirmed: `uv run python -m eval.replay.llm_labels` on a clean tree (70 projects × 3 calls through `claude -p`; running again resumes a run cut short), commit its folder under `eval/results/`, and tick the roadmap's LLM-judged policy and volatility-impact boxes. Every table says both label sets use present-day knowledge (D13).
2. After the budget rule is confirmed: build it (it reuses M7b's per-claim rate and `--dev-costs`), set its multiplier on dev by cost alone, and report it on test against fixed 30 and the fixed-N curve.
3. Then the Pareto figure. Every eval also runs on `eval/data/smoke/` in CI, with a stub model for the model evals. Never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`. Since #31, `fetched_at` is set for pypi and github_release checks and for page errors too (the time before the fetch), so `fetched_at IS NOT NULL` no longer means a web_page judgment. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- The stale rule (D10 follow-up 20) compares fetch times to the second: of two fetches of one claim that start in the same second, only the first result recorded is kept.
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

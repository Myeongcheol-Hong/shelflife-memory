# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26) and its follow-ups (#27), M6 (#28, #29, #30), the outside-review fixes (#31), M7a, the shared model runner (#32, D13), M7b, the adaptive policy and its run (#33), and the budget-aware allocation, decided (#35) and run (#36). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- M6's run is `eval/results/2026-10-14-369cb77/`: fixed 30 is fresher than per-class at no detectably higher cost. No class interval or policy changes because of a test result (D12).
- M7b's point (`2026-10-15-e2d0e3d-adaptive/`) sits 11.2 points above the fixed-N curve on test. The budget-aware allocation (`2026-10-15-6f7b4e9-budget/`, added after M7b's results, not pre-registered) sits on it: 0.6 points below (-1.6 to 0.5), and 1.4 points fresher than fixed 30 (-3.5 to 0.5).
- Open: the M7c PR (`feat/m7c-llm-labels`), which carries this file: `eval/replay/llm_labels.py`, D14 (decided) and four runs at f7b6974, Opus 5.5 the primary condition. 35% of Opus's answers and 47% of Fable 5.1's are invalid under D14's parsing (a sentence before the label, or bold); D14 records the counts.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. M7c: how to treat the invalid answers (D14's revisit condition): keep the results as scored, rescore the saved answers with a parse that reads the label at the end, or run again with a stricter prompt.
2. The M5b proposal (`docs/dev/m5b-page-timelines.md`): the pages, the tracked values, and the D12 amendment for values that revert.
3. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. Apply the maintainer's answer on M7c's invalid answers. A rescore uses `--rescore` and calls no model; a new prompt version is a new run of every condition, changing only the prompt.
2. Then M7's Pareto figure. Design 6.0-3's volatility impact waits for M8's write-eval labels (D14).
3. Every eval also runs on `eval/data/smoke/` in CI, with a stub model for the model evals. Never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`. Since #31, `fetched_at` is set for pypi and github_release checks and for page errors too (the time before the fetch), so `fetched_at IS NOT NULL` no longer means a web_page judgment. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- The stale rule (D10 follow-up 20) compares fetch times to the second: of two fetches of one claim that start in the same second, only the first result recorded is kept.
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

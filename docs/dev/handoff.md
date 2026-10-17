# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, M5a, M6 and M7 up to M7e (#37). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- 6.1 is done, and no new policies come after M7e (the maintainer). M7e's run, `eval/results/2026-10-16-45ee09a-compare/`, places every policy on the dense fixed-N curve on test. No scheduled policy without future knowledge lies below it; the true-rate bound (exploratory) lies 2.6 percentage points below (-3.7 to -1.7). Claude changes no class interval or policy because of a test result (D12); the maintainer's single-interval plan for M4 is under "Next session".
- Open, waiting for merge: the Pareto figure and README results PR (#38, `feat/pareto-readme`), which carries this file. `eval/replay/figure.py` draws `pareto.svg` and `pareto-dark.svg` into M7e's folder from its `metrics.json`, plus M6's never-re-checked line (the same claims), with the standard library; the README picks one by GitHub's theme with `<picture>`.
- M7's "volatility impact" item (design 6.0-3) stays open: it waits for M8's write-eval labels (D14).
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. The M5b proposal (`docs/dev/m5b-page-timelines.md`): the pages, the tracked values, and the D12 amendment for values that revert.
2. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. M4: `depends_on` links and decision review, `recall(verify=auto)` behind its setting (D9, D10), the daily due run, the weekly digest, `supersede`. Show the plan first; any change to the schema or a tool interface is the maintainer's to decide.
   - The README (#38, the maintainer's wording) says M4 moves to a single re-check interval, since one fixed interval did as well as the classes. Design 4.2 and `scheduler.DEFAULT_INTERVAL_DAYS` still set 7/30/180 days by class. Propose the decision (the interval, what happens to the volatility field) and the design edit; do not decide them.
2. Every eval also runs on `eval/data/smoke/` in CI, with a stub model for the model evals. Never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`. Since #31, `fetched_at` is set for pypi and github_release checks and for page errors too (the time before the fetch), so `fetched_at IS NOT NULL` no longer means a web_page judgment. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- The stale rule (D10 follow-up 20) compares fetch times to the second: of two fetches of one claim that start in the same second, only the first result recorded is kept.
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

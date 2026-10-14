# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions. #30 and #31 carry the same copy, so they merge in either order.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26), its follow-ups (#27) and M6a (#28). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- Open:
  - #29 (M6b, base `main`): D12's sessions rule, now decided.
  - #30 (M6c, base #29's branch, with #29 merged in): `run.py`, the first run in `eval/results/2026-10-14-baf3a2c/`, and M6 ticked. D12, CLAUDE.md and design 6.3 say that 6.1 keeps no per-claim rows and that `raw.jsonl` is for model evals.
  - #31 (base `main`): the outside-review fixes (stale verify results, PEP 440 spellings, a private DB file, the Mem0 wording, 6.2 traps, the Claude Desktop config) and the M5b proposal in `docs/dev/m5b-page-timelines.md`.
- The first run (test, uniform scenario, 1 question a week):
  - Jitter's primary comparison says jitter helps: the peak falls by 19.4 checks a day (-23.0 to -7.4), and the stale-answer rate's paired difference stays within -0.2 to +0.2 points.
  - Per-class lies above the fixed-N curve: 1.12 checks per claim-month at a 46.5% stale-answer rate, against fixed 30's 0.95 at 37.9%. Slow-labeled projects are stale on 57.6% of claim-days, against 24.9% under fixed 30.
  - A second run gave a byte-identical `metrics.json`.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. Merge #29. Then check that #30's base is `main`, merge `main` into #30's branch (merge commits only), and merge #30. #31 can go before or after.
2. #31: `docs.mem0.ai` is blocked in the cloud environment (the proxy answers 403), so the Mem0 wording follows your description and has no citation yet. Allow the host in the environment's network settings, or give the page and the date you checked it.
3. #31: confirm D10 follow-up 20, which compares fetch times rather than record times, so the result fetched last wins in either order. When a verify result is stale, `check` is the newer stored check; the alternative is `null`.
4. The M5b proposal (`docs/dev/m5b-page-timelines.md`): the pages, the tracked values, and the D12 amendment for values that revert.
5. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. M7. The shared model runner (`claude -p`) comes first (roadmap), then the adaptive family, whose dev grid, selection rule and label-free exploratory run are pre-registered in D12. Its selection caps the cost at per-class's dev cost, which this run puts at 0.97 checks per claim-month.
2. Every eval also runs on `eval/data/smoke/` in CI. Never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`. Since #31, `fetched_at` is set for pypi and github_release checks and for page errors too (the time before the fetch), so `fetched_at IS NOT NULL` no longer means a web_page judgment. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- The stale rule (D10 follow-up 20) compares fetch times to the second: of two fetches of one claim that start in the same second, only the first result recorded is kept.
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

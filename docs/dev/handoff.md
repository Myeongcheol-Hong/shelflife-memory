# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions. #30 and #31 carry the same copy, so they merge in either order.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26), its follow-ups (#27), M6a (#28) and M6b (#29). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- Open:
  - #30 (M6c, base `main`): `run.py` and the 6.1 run in `eval/results/2026-10-14-45eb42f/`, and M6 ticked. It replaces the first run (`baf3a2c`) with the same numbers plus two additions you asked for: per-class minus fixed 30, paired, and the jitter peaks without and with.
  - #31 (base `main`): the outside-review fixes (stale verify results, PEP 440 spellings, a private DB file, the Mem0 wording, now cited, 6.2 traps, the Claude Desktop config), D10 follow-up 20 decided, and the M5b proposal in `docs/dev/m5b-page-timelines.md`.
- The run (uniform scenario, 1 question a week; test unless named):
  - Jitter's primary comparison says jitter helps: in the sessions scenario per-class peaks at 87.8 checks a day without jitter and 68.4 with it (-19.4, -23.0 to -7.4); the stale-answer rate's paired difference stays within -0.2 to +0.2 points.
  - Per-class minus fixed 30, paired: +8.6 points of stale answers (2.4 to 14.5) in test and +10.5 (5.3 to 16.1) in dev, at more checks per claim-month (1.12 against 0.95 in test, 0.97 against 0.92 in dev). With the labels as they are, fixed 30 is fresher and cheaper in both splits. Slow-labeled projects are stale on 57.6% of claim-days, against 24.9% under fixed 30.
  - No class interval or policy changes because of a test result (D12): any change is chosen on dev, in M7 or later.
  - A rerun gives a byte-identical `metrics.json`.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. Merge #30 and #31, in either order.
2. Before M7: its pre-registered selection caps the adaptive policy's cost at per-class's dev cost (0.97 checks per claim-month) and compares it with per-class. Whether M7 also reports the selected point against fixed 30, which is fresher than per-class on dev at 0.92, is yours to decide.
3. The M5b proposal (`docs/dev/m5b-page-timelines.md`): the pages, the tracked values, and the D12 amendment for values that revert.
4. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. M7. The shared model runner (`claude -p`) comes first (roadmap), then the adaptive family, whose dev grid, selection rule and label-free exploratory run are pre-registered in D12.
2. Every eval also runs on `eval/data/smoke/` in CI. Never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`. Since #31, `fetched_at` is set for pypi and github_release checks and for page errors too (the time before the fetch), so `fetched_at IS NOT NULL` no longer means a web_page judgment. `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- The stale rule (D10 follow-up 20) compares fetch times to the second: of two fetches of one claim that start in the same second, only the first result recorded is kept.
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

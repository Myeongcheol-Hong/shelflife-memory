# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26), its follow-ups (#27) and M6a (#28: the replay core, metrics and intervals; D12 fully decided). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- Open, both green: #29 (M6b, base `main`: `sessions()`, `changes_per_year()`, `score.peak_ci()`, D12's sessions rule, proposed) and #30 (M6c, base #29's branch, carries this file: `eval/replay/run.py` writes `eval/results/<run-id>/` with config.json, metrics.json and table.md; `eval/results/` joins the size job's exclusions). The smoke corpus runs the whole pipeline in CI.
- No real run yet, and no real-data metric has been looked at. A full run takes about 4.5 minutes on one core.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. Confirm D12's sessions rule (#29), written before any run. In dev, mcp loses 0 to 9 of its 20 claims per seed; test drops none.
2. Confirm D12's proposed line (#30): 6.1 keeps no per-claim rows; scoring again means running again.
3. Merge #29, then #30. If #29 merges first, retarget #30 to `main` and merge `main` into its branch (merge commits only).
4. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. Read the maintainer's answers on #29 and #30. Once the sessions rule is confirmed: on #30's branch, `uv run python -m eval.replay.run` (a clean tree, so config.json shows no uncommitted changes), commit the run folder, tick M6 in the roadmap, and report the primary jitter verdict and the headline table.
2. Then M7. Its adaptive family, dev grid, selection rule and the label-free exploratory run are pre-registered in D12; the shared model runner (`claude -p`) comes first (roadmap).
3. Every eval also runs on `eval/data/smoke/` in CI; never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`; `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

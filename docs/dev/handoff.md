# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25), M5a (#26) and its follow-ups (#27). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- #28 (M6a: the replay core, metrics and intervals, D12 fully decided) is approved for merge.
- Stacked on #28: the M6b PR (the sessions scenario, `sessions()`; the change-rate breakdown; an interval for peak checks per day; D12's sessions rule, proposed) and the M6c PR on top of it, which carries this file: `eval/replay/run.py` writes `eval/results/<run-id>/` (config.json, metrics.json, table.md), and `eval/results/` joins the size job's exclusions. The smoke corpus runs the whole pipeline in CI. No real run yet.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. Confirm D12's sessions rule (written before any run). Then `uv run python -m eval.replay.run` gives the first results; they are committed under `eval/results/` in the M6c PR, and M6's roadmap items are ticked.
2. Merge #28, then the M6b PR, then the M6c PR.
3. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. If the M6c PR is merged: M7. Its adaptive family, dev grid, selection rule and the label-free exploratory run are pre-registered in D12; the shared model runner (`claude -p`) comes first (roadmap).
2. Every eval also runs on `eval/data/smoke/` in CI; never fill a label.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`; `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

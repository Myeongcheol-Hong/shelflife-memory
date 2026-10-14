# Handoff

Where the work stands. Each session's last PR overwrites this file (CLAUDE.md); git history keeps the old versions.

## State

- `main` has M1-M3, the hardening (#24), the repo presentation (#25) and M5a (#26). Schema v2 (#21) is a one-way door; the rollback steps are in design 5.1.
- Open, stacked: #27 (M5a follow-ups: created_at clamp, ollama and react cut, 70 projects, dedupe by id; base `main`) and the M6a PR on top of it, which carries this file.
- M6a: `eval/replay/replay.py` (claims, questions, the policies, the event loop) and `eval/replay/score.py` (metrics, intervals over projects, the peak per day), with D12. The smoke run's counts are pinned in `tests/unit/test_replay.py`. No real run yet.
- Build order (roadmap): M1-M3, M5a, M6, M7, M4, M5b, M8, M9.

## Waiting on the maintainer

1. #27: keep or drop the `latest_on()` same-second tie-break (D11, proposed); the data card's wording on `created_at` (the PR's Details).
2. M6a: confirm D12's "proposed" items: jitter's rounding (half up, so 7 days get ±1, 14%) and its adding up; one question draw per day; the peak taken per seed; the change-rate definition; 2,000 nearest-rank resamples; the +0.5 point margin for "not worse"; M7's adaptive family and dev grid.
3. Merge #27, then the M6a PR.
4. Open, no rush: whether the github_release verifier should read a project's tag pattern too (D11).

## Next session: start here

1. M6b: write D12's sessions rule (10 claims about 10 different projects on one day) before any run; then `eval/replay/run.py` writes `eval/results/<run-id>/` (config with git SHA, dataset hash and the `packaging` version; metrics; the markdown table) and can score again from rows; add `eval/results/` to the size job's exclusions.
2. Then the first real run: test is the headline, every policy at the three question rates (every read as a line across them), both scenarios, the per-label (with n) and change-rate breakdowns, the per-class line without the four late-labeled repositories, and jitter's one primary comparison. Commit only config, metrics and the table; tick M6.
3. The bootstrap for the peak per day needs per-project daily counts per seed; `score.peak()` gives only the point value today.
4. The change-rate breakdown needs `changes_per_year()` (changes per year from the first day with a latest, a first release not counted; D12); it was cut from M6a for size and waits in M6b.

## Notes for later milestones

- M4: `checks` stores `selector_version` and `fetched_at`; `s3` (#24) changed what `extract()` returns, so `s2` and `s3` section hashes of one page can differ.
- M4: when a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
- `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors. An unknown charset label falls back to UTF-8 (D10 follow-up 19).
- `now` is read before the write lock; it matters only with three writers within one second.
- An INTEGER PRIMARY KEY for `claims` waits for schema v3. Never VACUUM without rebuilding `claims_fts`.

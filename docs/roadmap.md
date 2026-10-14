# Roadmap

Milestones are listed in dependency order. Each milestone ships as its own PR (or a short stack of PRs). Design details live in `docs/design.md`.

Items marked **(owner)** are done by the maintainer by hand: ground-truth labels and open decisions. Tooling for them can be built ahead of time.

## M1: Core store and MCP server
- [x] Package skeleton: `uv` package `shelflife-memory`, import name `shelflife`, pytest, ruff, SessionStart hook (`uv sync`)
- [x] SQLite schema (design 5.1) with FTS5
- [x] `remember` / `recall` (no verification yet) with unit tests
- [x] stdio MCP server exposing `remember`, `recall`, `due`
- [x] Integration test that calls the tools through an in-process MCP client
- [x] Import `examples/seed_claims.jsonl`
- [x] **(owner)** D1-D3 recorded in `docs/decisions.md` (decided 2026-10-13)
- [x] Follow-ups from the owner's review (M1d): Korean search (D8), WAL and a busy timeout for two server processes, `remember` wording for D2/D3
- [x] Recall follow-ups (M1e): particles split off Latin names in queries, `recall` asks for 2-5 key words, `FieldSource.LLM` removed

## M2: Volatility and rule-based verifiers
- [x] Volatility classification: rules first. The LLM part is Claude setting volatility at write time through `remember` when confident; no new tool (D4). Rules also fill check_method for facts whose attribute names the latest version or release and whose source_url is a PyPI project or GitHub repository page
- [x] `pypi` and `github_release` verifiers (no LLM) with fixtures (PyPI recorded; GitHub written by hand and checked against the live API by the owner on 2026-10-13. `tests/fixtures/record.py` re-records both where the GitHub API is reachable)
- [x] `due` returns claims past `next_check_at` (done early in M1: `next_check_at` = `observed_at` + the class interval from design 4.2, and only claims with a check method are listed. M2 extends it: recompute after each check and also list `changed` claims)
- [x] `verify` tool (M2b): records each check and reschedules the claim (D9)
- [x] `forget` tool (design 5.2, M2c)
- [x] `due`: a "needs a check method" section for claims that rules could not give a check method (M2c: `due` returns the due, changed and needs_check_method lists, D9)
- [x] Follow-ups from the owner's review (M2d): the check-method rule reads only the attribute; `pypi` and `github_release` claims need a value; `BEGIN IMMEDIATE` in `add_check` and `forget`; "due" is derived, not a stored status

## M3: web_page verifier and write checks
- [x] Fetch pages safely: http(s) and public addresses only, checked on every redirect, with size and time caps; `remember` rejects non-http(s) URLs (M3a, D10)
- [x] Extract the visible page text: the whole body, without hidden or struck-through text; one shared `normalize()` for every comparison (M3b)
- [x] Select the relevant section: deterministic, with its position, heading and scores for 6.2 (M3c)
- [ ] Judgment per D4 (b): `record_check` with verbatim-quote validation in code, and a versioned judgment prompt template that `verify` returns for web_page claims and the eval harness reuses (D10)
- [ ] `checks` table populated for every check
- [ ] Four automatic write checks (design 6.0-1)
- [x] **(owner)** D4 recorded (decided 2026-10-13)

## M4: Decisions, scheduler, digest
- [ ] `depends_on` links; a changed claim flags dependent decisions for review
- [ ] `recall(verify=auto/never/always)` (D9); for a due web_page claim, `auto` returns `verify`'s `judge` payload (D10). Behind a setting that is off by default: `SHELFLIFE_RECALL_VERIFY=never` (D9)
- [ ] Daily due run (cron/launchd), no LLM
- [ ] Weekly digest
- [ ] `supersede`: one call that remembers the new claim and retires the old one (D9). Decisions linked to the old claim stay linked to it and stay flagged for the owner's review

## M5: Eval data and tooling
- [ ] PyPI/GitHub release timelines (about 50 packages, 20 repos), dev/test split. Collected by a script the owner runs locally, because the cloud session cannot call the GitHub API for repositories not attached to it; the data is committed
- [ ] Wayback pair collection tool and labeling file format. Collected by a script the owner runs on the Mac, like the release timelines, because cloud sessions cannot reach `web.archive.org` reliably; the data is committed
- [ ] Write-eval item file format (one given sentence, the surrounding turn, the source URL; gold labels are the fields; design 6.0-2) and labeling tool
- [ ] `eval/data/README.md` data card
- [ ] Smoke corpus in `eval/data/smoke/`, wired into CI
- [ ] Shared model runner (`claude -p --model`, repeats, run artifacts)
- [ ] **(owner)** Label 30-40 Wayback pairs
- [ ] **(owner)** Label 40 write-eval items, including about 10 trap cases (design 6.0-2)

## M6: Replay simulator and baseline policies
- [ ] Day-by-day replay over the timelines
- [ ] Policies: never, every read, fixed 7/30 days, per-class
- [ ] Metrics: stale-answer rate, checks per claim-month, days to detect
- [ ] First results table

## M7: Adaptive and LLM-judged policies
- [ ] Adaptive per-claim policy, tuned on dev split only
- [ ] LLM-judged volatility policy
- [ ] 5 seeds, bootstrap intervals, Pareto figure
- [ ] Volatility impact: owner labels vs Claude labels in the replay (design 6.0-3)

## M8: Verifier and write-quality results
- [ ] Verifier accuracy (design 6.2): Haiku vs Sonnet, full page vs section, false alarms vs misses, failure attribution
- [ ] Labeled write eval (design 6.0-2), trap cases reported separately
- [ ] **(owner)** Blind re-label of 20% and self-agreement
- [ ] Optional: Hindsight invalidation integration
- [ ] Optional: extraction recall and precision (a stretch goal under D2)

## M9: Release
- [ ] Launch-readiness pass: an agent audit for performance, bugs, security and fit to `docs/design.md`
- [ ] **(owner)** Cleanup and refactor pass
- [ ] README: problem, demo GIF, install, results, limitations, prior art, real-use stats
- [ ] PyPI release (`uvx shelflife-memory`), v0.1.0 tag, CHANGELOG
- [ ] MCP registry listing

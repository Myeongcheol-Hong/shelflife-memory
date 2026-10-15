# Roadmap

Milestones are listed in build order, which is not their numeric order: M5 is split into M5a and M5b, and M4 comes after M7. The numbers stay, so earlier PRs and decisions still point to the right milestone. Each milestone ships as its own PR (or a short stack of PRs). Design details live in `docs/design.md`.

Items marked **(maintainer)** are done by the maintainer by hand: ground-truth labels, open decisions and the cleanup pass before release. Tooling for them can be built ahead of time.

## M1: Core store and MCP server
- [x] Package skeleton: `uv` package `shelflife-memory`, import name `shelflife`, pytest, ruff, SessionStart hook (`uv sync`)
- [x] SQLite schema (design 5.1) with FTS5
- [x] `remember` / `recall` (no verification yet) with unit tests
- [x] stdio MCP server exposing `remember`, `recall`, `due`
- [x] Integration test that calls the tools through an in-process MCP client
- [x] Import `examples/seed_claims.jsonl`
- [x] **(maintainer)** D1-D3 recorded in `docs/decisions.md` (decided 2026-10-13)
- [x] Follow-ups from the maintainer's review (M1d): Korean search (D8), WAL and a busy timeout for two server processes, `remember` wording for D2/D3
- [x] Recall follow-ups (M1e): particles split off Latin names in queries, `recall` asks for 2-5 key words, `FieldSource.LLM` removed

## M2: Volatility and rule-based verifiers
- [x] Volatility classification: rules first. The LLM part is Claude setting volatility at write time through `remember` when confident; no new tool (D4). Rules also fill check_method for facts whose attribute names the latest version or release and whose source_url is a PyPI project or GitHub repository page
- [x] `pypi` and `github_release` verifiers (no LLM) with fixtures (PyPI recorded; GitHub written by hand and checked against the live API by the maintainer on 2026-10-13. `tests/fixtures/record.py` re-records both where the GitHub API is reachable)
- [x] `due` returns claims past `next_check_at` (done early in M1: `next_check_at` = `observed_at` + the class interval from design 4.2, and only claims with a check method are listed. M2 extends it: recompute after each check and also list `changed` claims)
- [x] `verify` tool (M2b): records each check and reschedules the claim (D9)
- [x] `forget` tool (design 5.2, M2c)
- [x] `due`: a "needs a check method" section for claims that rules could not give a check method (M2c: `due` returns the due, changed and needs_check_method lists, D9)
- [x] Follow-ups from the maintainer's review (M2d): the check-method rule reads only the attribute; `pypi` and `github_release` claims need a value; `BEGIN IMMEDIATE` in `add_check` and `forget`; "due" is derived, not a stored status

## M3: web_page verifier and write checks
- [x] Fetch pages safely: http(s) and public addresses only, checked on every redirect, with size and time caps; `remember` rejects non-http(s) URLs (M3a, D10)
- [x] Extract the visible page text: the whole body, without hidden or struck-through text; one shared `normalize()` for every comparison (M3b)
- [x] Select the relevant section: deterministic, with its position, heading and scores for 6.2 (M3c)
- [x] Judgment per D4 (b): `record_check` with verbatim-quote validation in code, and a versioned judgment prompt template that `verify` returns for web_page claims and the eval harness reuses (D10; M3d template and checks, M3e tools)
- [x] `checks` table populated for every check (M3e: schema v2 adds the judgment's prompt version, page and section hashes, and the `cannot_tell` reason)
- [x] Four automatic write checks (design 6.0-1; M3f: `writechecks.py` and `shelflife-memory check-writes FILE`)
- [x] **(maintainer)** D4 recorded (decided 2026-10-13)

## M5a: Release timelines, dev/test split, smoke corpus
- [x] PyPI/GitHub release timelines (about 50 packages, 20 repos), dev/test split. Collected by a script the maintainer runs on the Mac, because the cloud session cannot call the GitHub API for repositories not attached to it; the data is committed
- [x] `eval/data/README.md` data card: sources, dates and licenses of the timelines
- [x] Smoke corpus in `eval/data/smoke/`, wired into CI (M5a: the timeline rules run on it in the test suite)
- [x] **(maintainer)** Label the volatility class of each replay claim (design 6.0-3). M6's per-class policy needs these classes, and labeling before any replay result keeps the labels blind

## M6: Replay simulator and baseline policies
- [x] Day-by-day replay over the timelines
- [x] Policies: never, every read, fixed 3 to 180 days, per-class, oracle, jitter (D12)
- [x] Metrics: stale-answer rate, stale claim-days, checks per claim-month, days to detect with the undetected share, peak checks per day; 5 seeds and bootstrap intervals over projects (D12)
- [x] Results table: `eval/results/2026-10-14-369cb77/table.md`

## M7: Adaptive and LLM-judged policies
- [x] Shared model runner (`claude -p --model`, repeats, run artifacts; `eval/runner.py`, D13). It starts `claude -p` outside the repository, so the project's Stop hook and `CLAUDE.md` stay out of eval runs. M5b and M8 reuse it
- [ ] Adaptive per-claim policy, tuned on dev split only
- [ ] LLM-judged volatility policy
- [ ] Pareto figure (5 seeds and bootstrap intervals moved to M6, D12)
- [ ] Volatility impact: maintainer labels vs Claude labels in the replay (design 6.0-3)

## M4: Decisions, scheduler, digest
- [ ] `depends_on` links; a changed claim flags dependent decisions for review
- [ ] `recall(verify=auto/never/always)` (D9); for a due web_page claim, `auto` returns `verify`'s `judge` payload (D10). Behind a setting that is off by default: `SHELFLIFE_RECALL_VERIFY=never` (D9)
- [ ] Daily due run (cron/launchd), no LLM
- [ ] Weekly digest
- [ ] `supersede`: one call that remembers the new claim and retires the old one (D9). Decisions linked to the old claim stay linked to it and stay flagged for the maintainer's review

## M5b: Wayback pairs, write-eval items, labeling tools
- [ ] Wayback pair collection tool and labeling file format. Collected by a script the maintainer runs on the Mac, like the release timelines, because cloud sessions cannot reach `web.archive.org` reliably; the data is committed
- [ ] Write-eval item file format (one given sentence, the surrounding turn, the source URL; gold labels are the fields; design 6.0-2) and labeling tool
- [ ] The data card covers the Wayback pairs and write-eval items, with their labeling rules
- [ ] **(maintainer)** Label 30-40 Wayback pairs
- [ ] **(maintainer)** Label 40 write-eval items, including about 10 trap cases (design 6.0-2)

## M8: Verifier and write-quality results
- [ ] Verifier accuracy (design 6.2): Haiku vs Sonnet, full page vs section, false alarms vs misses, failure attribution
- [ ] Labeled write eval (design 6.0-2), trap cases reported separately
- [ ] **(maintainer)** Blind re-label of 20% and self-agreement
- [ ] Optional: Hindsight invalidation integration
- [ ] Optional: extraction recall and precision (a stretch goal under D2)

## M9: Release
- [ ] Launch-readiness pass: an agent audit for performance, bugs, security and fit to `docs/design.md`
- [ ] **(maintainer)** Cleanup and refactor pass
- [ ] README: problem, demo GIF, install, results, limitations, prior art, real-use stats
- [ ] PyPI release (`uvx shelflife-memory`), v0.1.0 tag, CHANGELOG
- [ ] MCP registry listing

# Roadmap

Milestones are listed in dependency order. Each milestone ships as its own PR (or a short stack of PRs). Design details live in `docs/design.md`.

Items marked **(owner)** are done by the maintainer by hand: ground-truth labels and open decisions. Tooling for them can be built ahead of time.

## M1: Core store and MCP server
- [ ] Package skeleton: `uv` package `shelflife-memory`, import name `shelflife`, pytest, ruff, SessionStart hook (`uv sync`)
- [ ] SQLite schema (design 5.1) with FTS5
- [ ] `remember` / `recall` (no verification yet) with unit tests
- [ ] stdio MCP server exposing `remember`, `recall`, `due`
- [ ] Integration test that calls the tools through an in-process MCP client
- [ ] Import `examples/seed_claims.jsonl`
- [ ] **(owner)** D1-D3 recorded in `docs/decisions.md`

## M2: Volatility and rule-based verifiers
- [ ] Volatility classification (rules first, LLM fallback per D4)
- [ ] `pypi` and `github_release` verifiers (no LLM) with recorded fixtures
- [ ] `due` returns claims past `next_check_at`
- [ ] `verify` tool

## M3: web_page verifier and write checks
- [ ] Fetch, extract main text, select the relevant section
- [ ] Judgment per D4 (`record_check` if option (b)) with verbatim-quote validation in code
- [ ] `checks` table populated for every check
- [ ] Four automatic write checks (design 6.0-1)
- [ ] **(owner)** D4 recorded

## M4: Decisions, scheduler, digest
- [ ] `depends_on` links; a changed claim flags dependent decisions for review
- [ ] Daily due run (cron/launchd), no LLM
- [ ] Weekly digest

## M5: Eval data and tooling
- [ ] PyPI/GitHub release timelines (about 50 packages, 20 repos), dev/test split
- [ ] Wayback pair collection tool and labeling file format
- [ ] Write-eval snippet file format and labeling tool
- [ ] `eval/data/README.md` data card
- [ ] Smoke corpus in `eval/data/smoke/`, wired into CI
- [ ] Shared model runner (`claude -p --model`, repeats, run artifacts)
- [ ] **(owner)** Label 30-40 Wayback pairs
- [ ] **(owner)** Label 40 write-eval snippets, including about 10 trap cases

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

## M9: Release
- [ ] README: problem, demo GIF, install, results, limitations, prior art, real-use stats
- [ ] PyPI release (`uvx shelflife-memory`), v0.1.0 tag, CHANGELOG
- [ ] MCP registry listing

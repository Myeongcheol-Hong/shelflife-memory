# CLAUDE.md

## Project

Shelf Life (`shelflife-memory`) is a small MCP memory server. Each stored claim carries a source, an observed date, a volatility class and a check method. Claims are re-verified against the world (PyPI, GitHub releases, web pages) when they are due, and decisions are flagged for review when a claim they depend on changes.

The main contribution is the **eval**, not the feature list. Re-check tools already exist (see `docs/design.md` section 1.1). What this project adds is a reproducible measurement of *when* to re-check and *how accurate* the write and verify steps are.

- Design (source of truth): `docs/design.md`
- Milestones, in order: `docs/roadmap.md`
- Decision log: `docs/decisions.md` (D1 to D4 and later)
- Session handoff notes: `docs/session-log.md` (read the newest entry first)
- Owner: MC.
- Language: English only, everywhere (code, comments, docs, README, commit messages, PR descriptions, eval data labels).

## Working agreement

- Move as fast as the work allows. `docs/roadmap.md` sets the **order** of milestones, not the pace. When a milestone is done and its tests pass, tick its boxes in the roadmap and continue to the next one.
- At the start of a session, show a short plan for the milestones you intend to finish and wait for approval. After that, keep going without asking again unless the plan has to change.
- One PR per milestone (roughly one plan week). Do not mix milestones in one PR. Keep each PR within the size limit in "Review rules" below; split larger work into stacked PRs.
- In each PR description, explain the design choices and trade-offs so the owner understands and can explain every line. They go under "Details" (see "Review rules").
- Never skip tests, the quote check or the eval rules below to go faster.
- When the owner says a part is theirs to implement, leave a `TODO(mc)` stub with a skipped or `xfail(strict=True)` test that describes the expected behavior (a plain failing test would block the Stop hook).
- If the design doc is wrong or unclear, say so and propose an edit instead of silently diverging.
- One session per milestone or so. Before a session ends, update `docs/session-log.md`.

### Stop and ask (these do not speed up)

- **Ground-truth labels belong to the owner.** Never create, fill in or edit labels in `eval/data/` (Wayback pair labels, write-eval snippet labels, human volatility labels). Build the files, schemas and labeling tools, then stop and hand over.
- **Decisions belong to the owner.** Propose options for any new decision and for any change to the schema or MCP tool interfaces; do not decide them. Decisions are recorded in `docs/decisions.md` (D1-D4 came from `docs/design.md` section 8 and are decided). Items marked **(owner)** in the roadmap are never done by Claude.
- **New dependencies** need approval, and a check that the package exists on PyPI.
- **Blocked network access**: report it instead of working around it.

## Review rules

- **Size:** under about 400 changed lines, excluding tests, fixtures, `eval/data/` and `uv.lock` (CI counts the same and fails above 600). Review fixes that would go over move to the next PR.
- **PR description:** a top part of at most 10 lines: **What changed**, **Read these first** (1-3 core files or functions), **Decisions needed**, **Removed or simplified**. Then **Proof** (each added test and what it asserts, one line each; commands run and their results), **Confidence** (high, medium or low per part, with a reason for anything not high), **Rollback** (how to undo it; write ONE-WAY DOOR if it changes the DB schema or stored data), then **Details**.
- **Code the owner always reads:** the `store.py` schema and transactions, the MCP tool interfaces, quote and `record_check` validation, and eval scoring. A PR that changes one lists it under "Read these first".
- **Simpler:** prefer the simpler fix and deleting code, and say what was removed.
- **Packages:** only with the owner's approval and after checking the package exists on PyPI. CI fails on a change to the dependencies in `pyproject.toml` or to `uv.lock` until the owner adds the `deps-approved` label.
- **Reviews:** use the `pr-reviewer` agent; its checklist is the `pr-review` skill.

## Tech constraints

- Python 3.11+, `uv` for packaging. Distribution name `shelflife-memory`, import name `shelflife`.
- MCP: official MCP Python SDK v2 (`mcp>=2.3,<3`, `MCPServer`, formerly `FastMCP`), stdio transport.
- Storage: one SQLite file with FTS5. No embeddings, no ORM, no Docker, no Postgres/Redis.
- DB path comes from `SHELFLIFE_DB`, default `~/.shelflife/shelflife.db`. Never write the DB inside the repo.
- Prefer the standard library. Ask before adding a dependency.

## Layout (target)

```
src/shelflife/
  store.py          # SQLite schema, CRUD, FTS5 search
  models.py         # Claim, Check, enums (kind, volatility, check_method, status)
  server.py         # MCP tools: remember, recall, due, verify, forget, record_check
  scheduler.py      # next_check_at policies, daily due run, weekly digest
  verifiers/        # pypi.py, github_release.py, web_page.py (deterministic parts)
eval/
  replay/           # 6.1 when-to-check policy replay (no LLM)
  write/            # 6.0 write-quality eval
  verifier/         # 6.2 web_page verifier accuracy
  runner.py         # model runner: `claude -p --model ...`, repeats, run artifacts
  data/             # timelines, Wayback pairs, labeled snippets (small, committed)
    README.md       # data card: sources, dates, licenses, labeling rules
    smoke/          # tiny synthetic set; every eval runs on it in seconds, no network
  results/<run-id>/ # config.json, raw.jsonl, metrics.json
tests/
  unit/
  integration/      # call the tools through an in-process MCP client
examples/
  seed_claims.jsonl # real claims for demos and first use
docs/
  design.md
  roadmap.md
  decisions.md
```

Keep this flat. Do not copy the structure of large projects (services/, repositories/, plugins/) until the code actually needs it.

## Commands

```
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

A Stop hook in `.claude/settings.json` runs ruff and pytest whenever a session tries to stop, and keeps it going while they fail.

## Testing and eval rules

- Unit tests never call a real LLM or the live network. Put network access behind small interfaces and test with recorded fixtures.
- Tests must be deterministic: inject the clock (`now`) instead of calling `datetime.now()` inside logic.
- A verifier result is only accepted if its quote appears verbatim in the fetched content. Enforce this in code, not in the prompt.
- Do not grade Claude output with Claude. Grade with code checks, the owner's labels, or real-world history (PyPI dates, Wayback snapshots). If an LLM judge is ever used, also report its agreement with the owner's labels.
- Eval-only dependencies (plotting, dataframes) go in a uv dependency group named `eval`. The core install stays minimal.
- Tests stub the model and run in CI. Evals call a real model, never run in CI, and run each LLM item 3 times so results are rates.
- When comparing conditions, change one variable at a time; keep model and prompt version fixed otherwise.
- Every eval run writes `eval/results/<run-id>/` with config, git SHA, model, prompt version, dataset hash, raw per-item outputs and metrics. Support rescoring from raw outputs without calling the model.
- The 6.1 adaptive policy is tuned on the dev split only and reported on the held-out test split, over 5 seeds with bootstrap intervals.
- Every eval must also run on `eval/data/smoke/` and that run is part of CI.

## Cloud sessions

- Each cloud session is a fresh VM, so any SQLite file created there is temporary. Daily use happens on the owner's Mac.
- Dependencies are installed by the SessionStart hook in `.claude/settings.json` (`uv sync`).
- Network: PyPI and GitHub are allowed by default. Wayback (`web.archive.org`) and other web pages need the environment's custom allowlist; if a request is blocked, say so instead of working around it.

# Session log

Handoff notes between working sessions. Newest entry first. Each entry says where the work stands, what waits on the owner, and what the next session should do first.

## 2026-10-13: owner review of #1-#3, M1d follow-ups

### State at the end of the session

- The owner reviewed #1-#3 and merges them bottom-up with merge commits.
- Everything from that review is on `claude/tender-mayer-wts8cd-m1d`, built on the M1c head. It becomes the PR "M1d: follow-ups" against `main` once the merges land: rebase it onto `main` first, then open it. It is not part of #3.
- M1d contents:
  - Korean search (D8): `claims_fts` uses the `trigram` tokenizer; query words shorter than 3 characters use LIKE; ranking is by matched words, then bm25. Schema changed in place at version 1.
  - WAL and a 5-second busy timeout, since Claude Desktop and Claude Code each run a server process on the same file.
  - Tool wording: `text` is the user's sentence as given (D2), an offer shows the exact sentence and the yes approves it (D3), and `recall` asks for names in their original spelling (D8).
  - Docs: the owner's answers to the proposals in #1-#3 and to questions 1-4 below, D5-D7 revisit lines confirmed, D8 recorded, the stale "open decisions" pointer in CLAUDE.md fixed.

### Owner answers recorded (2026-10-13)

- #1 world facts default to `fast`; #2 `due` leaves out `check_method = none` for now, the extra validation rules, and the M1 meaning of "unverifiable"; #3 refusing unknown arguments and `{"claims": [...]}`: all agreed.
- `porter` stemming: no (Korean matters more, D8).
- Question 1: `text` is the user's sentence as given, in whatever language; never rewritten or translated. Question 2: the offer shows the exact sentence. Question 3: option (i), volatility is set only at write time through `remember`, no new tool (recorded under D4). Question 4: a write-eval item is one given sentence plus the surrounding turn and source URL; the trap list is in design 6.0-2.
- M2 adds a "needs a check method" section to `due`. M5's release timelines are collected by a script the owner runs on the Mac (roadmap M5).

### Next session: start here

1. If #1-#3 are merged and the M1d PR is not open yet: rebase `claude/tender-mayer-wts8cd-m1d` onto `main`, run the checks, and open "M1d: follow-ups" against `main`.
2. Show the owner a short plan for M2 and wait for approval. M2 items are in `docs/roadmap.md`; keep at most 3 unmerged PRs open.

## 2026-10-13: owner decisions D1-D4

### State at the end of the session

- The owner decided D1-D4. `docs/decisions.md` records each with the option chosen, why, and a "Revisit if" line. D5-D7 also have a "Revisit if" line now; Claude drafted those three, marked them as drafts in the log, and they wait for the owner's check. D5's "Why" refers to the recorded D4 instead of assuming it.
- D3 is applied: the server instructions and the `remember` description say Claude may offer ("Want me to remember this?") but never calls `remember` until the user confirms. This answers proposal 2 in #3.
- `docs/design.md` (5.2, 5.3, 6.0, 8) and `docs/roadmap.md` no longer call D1-D4 open. Both "(owner) ... recorded" roadmap items are ticked. Design 6.0-2 calls extraction recall and precision a stretch goal (D2).
- These are new commits on M1c (#3), because three PRs are already open. #1-#3 are still unmerged.

### Questions for the owner

1. D2 says the user gives the sentence, but the `remember` description still says "Write one self-contained sentence per claim", which reads as Claude writing it. Proposed wording: "text: the user's sentence as given; do not rewrite it, only structure it into the other fields."
2. D2 with D3: when Claude offers and the user says yes, which sentence is stored? Proposed: the offer shows the exact sentence, and the yes approves that sentence.
3. D4 (b) and M2's "LLM fallback per D4" for volatility: with no LLM on the server, the fallback can only be Claude in a conversation. Options: (i) only at write time, through `remember`'s `volatility` parameter; (ii) `recall` or `due` also return claims whose volatility is still a default, with the prompt template, and a tool stores Claude's answer as `volatility_source = llm`. Option (ii) changes the tool interface.
4. Design 6.0-2 under D2: the snippets and trap cases ("no claim at all") were written for extraction. M5 builds the snippet format and needs the answer: is a snippet one given sentence (plus context), and which trap cases stay?

### Next session: start here

1. Check #1-#3 as in the entry below (merged? review comments? CI?).
2. Show the owner a short plan and wait for approval. M2 starts when fewer than three PRs are open; the answers to questions 1 and 3 shape it.

## 2026-10-12: M1 (core store and MCP server)

### State at the end of the session

M1 is done as three stacked PRs, all green (Python 3.11 and 3.13) and mergeable, waiting for the owner's review:

| PR | Branch | Base | Content |
|---|---|---|---|
| [#1](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/1) `[stack 1/3] M1a` | `claude/tender-mayer-wts8cd` | `main` | Package skeleton, CI, SessionStart hook, `models.py`, `scheduler.py` |
| [#2](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/2) `[stack 2/3] M1b` | `claude/tender-mayer-wts8cd-m1b` | M1a branch | `store.py`: schema, `remember`, `recall`, `due` |
| [#3](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/3) `[stack 3/3] M1c` | `claude/tender-mayer-wts8cd-m1c` | M1b branch | `server.py`, `cli.py` (serve, import), seed import, `docs/decisions.md`, this log |

Roadmap: all M1 items are ticked except "(owner) D1-D3 recorded". M2's "`due` returns claims past `next_check_at`" is also ticked; M2 extends it.

### Working rules the owner set this session

- Stack PRs on branches `claude/tender-mayer-wts8cd-<milestone>` (for example `-m2a`), each PR targeting the branch before it.
- Keep at most 3 unmerged PRs open. When 3 are open, stop and wait for review.
- Title PRs with their position, e.g. `[stack 2/3] M2a: ...`, and name the base branch in the description.
- The owner merges bottom-up without squashing. If a later PR ends up with the wrong base after a merge, retarget it to `main` and rebase it.
- Owner answers on `remember`, the MCP SDK version and `next_check_at` are recorded as D5-D7 in `docs/decisions.md`.

### Waiting on the owner

1. Review and merge #1, #2, #3.
2. Decide D1-D4 in `docs/decisions.md` (D4 blocks the LLM parts of M2 and M3).
3. Answer the proposals in the PR descriptions:
   - #1: world facts default to volatility `fast`.
   - #2: `due` leaves out claims with `check_method = none`; the extra validation rules on `remember`; "unverifiable" means "no check method" in M1, while design 3 and 7 say "no source"; optional `porter` stemming for FTS.
   - #3: unknown tool arguments are refused, not dropped; tool descriptions assume D3 = "only when the user asks"; `recall` and `due` return `{"claims": [...]}`.
4. Network: the cloud environment blocks the GitHub API for repositories not attached to the session, and blocks `web.archive.org`. PyPI works. Wayback collection (M5) needs the custom network allowlist.

### Next session: start here

1. Check the three PRs (merged? review comments? CI?). Retarget and rebase any PR left with a stale base after a merge. Apply the owner's answers to the proposals above.
2. Show the owner a short plan and wait for approval (CLAUDE.md working agreement).
3. Then M2, split to fit the 3-open-PR limit, for example:
   - M2a: rule-based volatility classifier (never overwrite `volatility_source = caller`), `pypi` and `github_release` verifiers behind a small fetch interface, recorded fixtures. PyPI fixtures can be recorded live; GitHub fixtures must be written by hand from the documented API format unless the owner attaches the repositories or changes the network policy.
   - M2b: `verify` tool writing to `checks`, `forget` (design 5.2 has it, the roadmap does not; agreed to add it to M2), and the `due` extension: recompute `next_check_at` after each check and list `changed` claims.
   - The LLM fallback for volatility waits on D4: leave a skipped test.
4. Things M2 must not forget:
   - When a rule fills a default `check_method`, recompute `status` (a world fact with no check method is stored as `unverifiable`). There is a comment at that spot in `store.py`.
   - Rules may replace values whose `*_source` is `default`, never `caller`.
   - The `recall` and `due` descriptions in `server.py` describe M1 behavior ("status is fresh or unverifiable; nothing re-checks claims"). Update them when verification lands, and update the tests that pin them.

### Technical notes worth keeping

- mcp 2.3: `FastMCP` is now `mcp.server.mcpserver.MCPServer`. Synchronous tools run in worker threads (hence `check_same_thread=False` plus a lock in `Store`). Only a `ToolError` message reaches the model; other exceptions become "Error executing tool X". The SDK silently drops undeclared arguments, so `server.py` has a middleware that refuses them. Structured output must be a JSON object on older protocol versions. `mcp.Client(server)` connects in-process for tests.
- Tests: an autouse fixture blocks `socket.connect`; the clock is injected (`FakeClock` in `tests/conftest.py`); async tests use anyio's pytest plugin with `anyio_backend = "asyncio"`.
- Each PR was reviewed before opening by a multi-agent workflow (one reviewer per angle, then a skeptic per angle trying to refute each finding). Confirmed findings were fixed and listed in the PR description.

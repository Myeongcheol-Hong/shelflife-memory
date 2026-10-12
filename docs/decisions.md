# Decision log

One entry per decision: the options, the option chosen and why. D1 to D4 are the open decisions from `docs/design.md` section 8. Decisions belong to the owner (MC). Claude proposes options and records what the owner decided; it does not fill in an open entry.

## D1: Storage

- Status: **open (owner)**
- Options (design 8): a single SQLite file with FTS5 and no embeddings to start; embeddings later if search quality needs them.
- Note: M1 is built on SQLite + FTS5, as CLAUDE.md requires.
- Chosen:
- Why:

## D2: Who extracts claims

- Status: **open (owner)**
- Options (design 8): the LLM extracts claims from the conversation, or the user gives the sentences directly. Design suggests direct entry first, since extraction quality is a separate problem.
- Chosen:
- Why:

## D3: When `remember` is called

- Status: **open (owner)**
- Options (design 8): Claude calls it on its own during conversations, or only when asked. If on its own, the 6.0 write eval is mandatory.
- Note: until this is decided, the server instructions and the `remember` description say "only when the user asks".
- Chosen:
- Why:

## D4: Where LLM judgments happen

- Status: **open (owner)**
- Options (design 8): (a) the server calls the Claude API (needs an API key, allows background web_page checks); (b) Claude in the conversation judges and stores the result with `record_check`. In both, the background job runs without an LLM. Design suggests (b) plus the rule-based background job for v1.
- Chosen:
- Why:

## D5: `remember` parameters and field sources

- Status: decided by the owner, 2026-10-12 (recorded from the session that built M1)
- Chosen: `text` and `kind` are required. Optional: `subject`, `attribute`, `value`, `volatility`, `check_method`, `check_target`, `source_url`, `source_quote`, `observed_at`, `depends_on`. System-managed fields (`id`, `recorded_at`, `last_checked_at`, `next_check_at`, `status`) are never accepted, and unknown enum values are rejected. `volatility_source` and `check_method_source` record who set each value (`caller` or `default`, later `rule` or `llm`), so later stages never overwrite a caller's value and the write eval can tell them apart. The tool description tells the model to leave volatility and check_method empty unless it is confident.
- Why: design 5.2 listed only four inputs, but a claim (design 4.1) needs more, and under D4 (b) Claude supplies volatility.

## D6: MCP SDK version

- Status: decided by the owner, 2026-10-12
- Chosen: `mcp>=2.3,<3` with `MCPServer`.
- Why: v2 is the current stable line; it renamed `FastMCP` to `MCPServer`.

## D7: `next_check_at` in M1

- Status: decided by the owner, 2026-10-12
- Chosen: `next_check_at` = `observed_at` + the per-class interval from design 4.2 (`none` gives no date), as a pure function; the clock is injected. M2 extends it.
- Why: `due` ships in M1 and needs a date to compare against.

# Decision log

One entry per decision: the options, the option chosen, why, and when to revisit it. D1 to D4 were the open decisions in `docs/design.md` section 8. Decisions belong to the owner (MC). Claude proposes options and records what the owner decided; it does not fill in an open entry.

## D1: Storage

- Status: decided by the owner, 2026-10-13
- Options (design 8): a single SQLite file with FTS5 and no embeddings to start; embeddings later if search quality needs them.
- Chosen: a single SQLite file with FTS5, no embeddings.
- Why: personal scale (hundreds to a few thousand short claims); keyword search plus the subject/attribute fields is enough. Embeddings would need an embedding API key or a local model, which conflicts with subscription-only use and keeping the tool light.
- Revisit if: in daily use, recall misses claims I know are stored.

## D2: Who extracts claims

- Status: decided by the owner, 2026-10-13
- Options (design 8): the LLM extracts claims from the conversation, or the user gives the sentences directly. Design suggests direct entry first, since extraction quality is a separate problem.
- Chosen: direct entry. I give the claim sentence; Claude only structures it into fields (subject, attribute, value, kind, volatility, check_method, source). Claude does not pick claims out of a long conversation in v1.
- Why: every stored claim is intentional, and extraction quality is a separate problem.
- Consequence: the 6.0-2 labeled eval focuses on field accuracy for given sentences; extraction recall/precision becomes a stretch goal.
- Revisit if: after about two weeks of daily use, entry feels tedious or I forget to save things. Next step would be "Claude proposes, I approve".

## D3: When `remember` is called

- Status: decided by the owner, 2026-10-13
- Options (design 8): Claude calls it on its own during conversations, or only when asked. If on its own, the 6.0 write eval is mandatory.
- Chosen: `remember` is called only when I ask. Claude may offer ("Want me to remember this?") but must not call `remember` without my confirmation.
- Why: consistent with D2; only approved claims enter memory.
- Applied: the server instructions and the `remember` tool description in `src/shelflife/server.py` say this, and `tests/integration/test_mcp_tools.py` pins the wording.
- Revisit if: together with D2.

## D4: Where LLM judgments happen

- Status: decided by the owner, 2026-10-13
- Options (design 8): (a) the server calls the Claude API (needs an API key, allows background web_page checks); (b) Claude in the conversation judges and stores the result with `record_check`. In both, the background job runs without an LLM. Design suggests (b) plus the rule-based background job for v1.
- Chosen: (b) Claude in the conversation judges and stores the result with `record_check`, plus the rule-based background job (pypi/github decided by rules; web_page only marked "possibly changed" via a hash of the relevant section).
- Why: works on the Claude subscription without an API key, and the server stays LLM-free and deterministic to test. The verbatim-quote check in code still guards every result.
- Accepted trade-off: web_page changes are only judged during a conversation or the weekly digest, so detection latency depends on usage.
- Implementation note: the judgment instructions are a versioned prompt template that `recall` returns and the eval harness reuses, so 6.2 measures what runs in daily use.
- Revisit if: "possibly changed" items pile up unjudged in the digest. Then add (a) as an optional mode with an API key.

## D5: `remember` parameters and field sources

- Status: decided by the owner, 2026-10-12 (recorded from the session that built M1)
- Chosen: `text` and `kind` are required. Optional: `subject`, `attribute`, `value`, `volatility`, `check_method`, `check_target`, `source_url`, `source_quote`, `observed_at`, `depends_on`. System-managed fields (`id`, `recorded_at`, `last_checked_at`, `next_check_at`, `status`) are never accepted, and unknown enum values are rejected. `volatility_source` and `check_method_source` record who set each value (`caller` or `default`, later `rule` or `llm`), so later stages never overwrite a caller's value and the write eval can tell them apart. The tool description tells the model to leave volatility and check_method empty unless it is confident.
- Why: design 5.2 listed only four inputs, but a claim (design 4.1) needs more. Under D4 above, LLM judgments happen in the conversation, not on the server, so Claude supplies volatility through these parameters. (Reworded on 2026-10-13: the first version assumed D4 (b) before D4 was decided.)
- Revisit if (drafted by Claude, 2026-10-13; owner to confirm): the labeled write eval (design 6.0-2) shows that the volatility or check_method Claude supplies (`*_source` = `caller`) does worse than what the M2 rules set when the field is left empty, counting a fast claim labeled slower as the expensive error; or daily use needs a field `remember` does not accept. Then tell the model to leave both fields empty.

## D6: MCP SDK version

- Status: decided by the owner, 2026-10-12
- Chosen: `mcp>=2.3,<3` with `MCPServer`.
- Why: v2 is the current stable line; it renamed `FastMCP` to `MCPServer`.
- Revisit if (drafted by Claude, 2026-10-13; owner to confirm): `mcp` 3.0 is released (the `<3` pin then holds the server back), or Claude Desktop or Claude Code stops working with a 2.x server.

## D7: `next_check_at` in M1

- Status: decided by the owner, 2026-10-12
- Chosen: `next_check_at` = `observed_at` + the per-class interval from design 4.2 (`none` gives no date), as a pure function; the clock is injected. M2 extends it.
- Why: `due` ships in M1 and needs a date to compare against.
- Revisit if (drafted by Claude, 2026-10-13; owner to confirm): M2 adds checks, since this entry covers only M1 and M2 extends it; or the 6.1 replay shows another policy beats the per-class intervals on the held-out test split.

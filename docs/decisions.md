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
- Applied (owner, 2026-10-13): `text` is the user's sentence as given, in whatever language. Claude does not rewrite or translate it; it only structures it into the other fields. The `remember` description says so.
- Write eval (owner, 2026-10-13): an item is one user-given sentence plus the surrounding turn and the source URL, if any; the gold labels are the fields. The trap cases are listed in design 6.0-2.
- Revisit if: after about two weeks of daily use, entry feels tedious or I forget to save things. Next step would be "Claude proposes, I approve".

## D3: When `remember` is called

- Status: decided by the owner, 2026-10-13
- Options (design 8): Claude calls it on its own during conversations, or only when asked. If on its own, the 6.0 write eval is mandatory.
- Chosen: `remember` is called only when I ask. Claude may offer ("Want me to remember this?") but must not call `remember` without my confirmation.
- Why: consistent with D2; only approved claims enter memory.
- Applied: the server instructions and the `remember` tool description in `src/shelflife/server.py` say this, and `tests/integration/test_mcp_tools.py` pins the wording.
- Clarified (owner, 2026-10-13): an offer shows the exact sentence that would be stored, and the user's yes approves that sentence.
- Revisit if: together with D2.

## D4: Where LLM judgments happen

- Status: decided by the owner, 2026-10-13
- Options (design 8): (a) the server calls the Claude API (needs an API key, allows background web_page checks); (b) Claude in the conversation judges and stores the result with `record_check`. In both, the background job runs without an LLM. Design suggests (b) plus the rule-based background job for v1.
- Chosen: (b) Claude in the conversation judges and stores the result with `record_check`, plus the rule-based background job (pypi/github decided by rules; web_page only marked "possibly changed" via a hash of the relevant section).
- Why: works on the Claude subscription without an API key, and the server stays LLM-free and deterministic to test. The verbatim-quote check in code still guards every result.
- Accepted trade-off: web_page changes are only judged during a conversation or the weekly digest, so detection latency depends on usage.
- Implementation note: the judgment instructions are a versioned prompt template that `recall` returns and the eval harness reuses, so 6.2 measures what runs in daily use.
- Revisit if: "possibly changed" items pile up unjudged in the digest. Then add (a) as an optional mode with an API key.
- Volatility (owner, 2026-10-13): under (b) the "LLM fallback" for volatility is option (i): Claude sets volatility only at write time, through `remember`'s `volatility` parameter, when it is confident. No new tool. Revisit if many claims still carry the default volatility after the M2 rules.

## D5: `remember` parameters and field sources

- Status: decided by the owner, 2026-10-12 (recorded from the session that built M1)
- Chosen: `text` and `kind` are required. Optional: `subject`, `attribute`, `value`, `volatility`, `check_method`, `check_target`, `source_url`, `source_quote`, `observed_at`, `depends_on`. System-managed fields (`id`, `recorded_at`, `last_checked_at`, `next_check_at`, `status`) are never accepted, and unknown enum values are rejected. `volatility_source` and `check_method_source` record who set each value (`caller` or `default`, later `rule` or `llm`), so later stages never overwrite a caller's value and the write eval can tell them apart. The tool description tells the model to leave volatility and check_method empty unless it is confident.
- Why: design 5.2 listed only four inputs, but a claim (design 4.1) needs more. Under D4 above, LLM judgments happen in the conversation, not on the server, so Claude supplies volatility through these parameters. (Reworded on 2026-10-13: the first version assumed D4 (b) before D4 was decided.)
- Revisit if: the labeled write eval (design 6.0-2) shows that the volatility or check_method Claude supplies (`*_source` = `caller`) does worse than what the M2 rules set when the field is left empty, counting a fast claim labeled slower as the expensive error; or daily use needs a field `remember` does not accept. Then tell the model to leave both fields empty.

## D6: MCP SDK version

- Status: decided by the owner, 2026-10-12
- Chosen: `mcp>=2.3,<3` with `MCPServer`.
- Why: v2 is the current stable line; it renamed `FastMCP` to `MCPServer`.
- Revisit if: `mcp` 3.0 is released (the `<3` pin then holds the server back), or Claude Desktop or Claude Code stops working with a 2.x server.

## D7: `next_check_at` in M1

- Status: decided by the owner, 2026-10-12
- Chosen: `next_check_at` = `observed_at` + the per-class interval from design 4.2 (`none` gives no date), as a pure function; the clock is injected. M2 extends it.
- Why: `due` ships in M1 and needs a date to compare against.
- Revisit if: M2 adds checks, since this entry covers only M1 and M2 extends it; or the 6.1 replay shows another policy beats the per-class intervals on the held-out test split.

## D8: Search for Korean claims

- Status: decided by the owner, 2026-10-13
- Problem: the owner writes in Korean, and D2 stores the sentence as given, so `recall` must work for Korean. With the default `unicode61` tokenizer, particles fuse onto words: "Chatbox로" is one token, so "Chatbox 가격" finds nothing. The owner's test on SQLite 3.50: with `unicode61`, "Chatbox 가격" and "시험 비용" found nothing; with `trigram` plus LIKE for query words shorter than 3 characters, both matched.
- Options: keep `unicode61` (fails for Korean); A: the `trigram` tokenizer with a LIKE fallback for short query words. `porter` stemming (English only) was offered in #2 and declined, because Korean support matters more.
- Chosen: A. `claims_fts` uses `tokenize='trigram'`. Query words of 3 or more characters match through the index, shorter ones with LIKE. Results are ranked by the number of query words matched, then bm25, so short common words do not flood the top 10. The `recall` description tells the model to search for names in their original spelling (Hindsight, not 힌드사이트). The schema changed in place at version 1, because no database was in use yet.
- Trade-offs (drafted by Claude, 2026-10-13; owner to confirm): matching is by substring, so "mcp" also matches "mcpx"; a name written in another script is not found; query words shorter than 3 characters are matched by scanning every claim, which is fine at personal scale; a trigram index is larger than a `unicode61` one.
- Revisit if (drafted by Claude, 2026-10-13; owner to confirm): in daily use, Korean searches miss claims I know are stored (for example a query word that carries a different particle than the stored text, such as "Chatbox로" against "Chatbox의"), or substring matches crowd out the claim I wanted, or `recall` gets slow as the store grows into the thousands of claims.

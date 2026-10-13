# Shelf Life: Design Doc (v0.3)

> Memory with an expiry date. An MCP memory server that notices when remembered facts and decisions have gone stale because the world changed, re-verifies them, and measures **when re-checking pays off** using public, reproducible data.

**One-line pitch**
> Tools that re-check agent memories against the world already exist. None of the open-source ones I found measure *when* to re-check. Shelf Life is a small MCP memory that does both, and its eval compares re-check policies on reproducible ground truth from PyPI, GitHub releases and the Wayback Machine.

- Status: draft, last updated 2026-10-13. Milestones are in `docs/roadmap.md`.
- Repository: `shelflife-memory` (public, MIT). Distribution name `shelflife-memory`, import name `shelflife`. (`shelflife` cannot be registered on PyPI because it collides with the existing `shelf-life` project under PyPI's name normalization.)

---

## 1. Problem

Today's memory systems (Mem0, Zep/Graphiti, Hindsight and others) update a memory **when new information arrives and conflicts with the old**. When the world changes and nobody tells the system, the stale memory keeps being served.

- Hindsight's own docs say that when a fact stops being true with nothing to replace it, nothing in the pipeline knows the world changed, so the user has to invalidate it by hand.
- On evolving knowledge, RAG serves superseded values 15 to 40% of the time when forced to answer (MemStrata, arXiv 2606.26511).

This gap is about the **memory systems themselves**. A few tools that sit on top of them and re-check memories against the outside world already exist (1.1).

**Shelf Life's answer**: attach a volatility class and a check method to every memory and re-check it when it is due. Then measure, on reproducible data, when to re-check so that stale answers go down without the check budget going up. That measurement is the core of the project.

### 1.1 Prior art (checked 2026-10-12)

The README names these projects openly.

| Project | What it does | What it leaves open |
|---|---|---|
| Zep / Graphiti | Bi-temporal knowledge graph. Invalidates an old fact when a contradicting new fact arrives | Misses changes when no new information arrives |
| Hindsight | Separates world facts from experiences. Its curation API can invalidate and restore memories | Invalidation is manual |
| Mem0 | Decay, eviction, supersession on contradiction | Says itself that staleness in high-relevance memories is an open problem |
| MemStrata (arXiv 2606.26511) | Deterministic (subject, relation, object) supersession retires replaced values. Shows RAG serves 15-40% stale values | Also needs the new value to arrive |
| [MemGuard](https://github.com/ac12644/MemGuard) | **Closest match.** Sidecar for Mem0/Zep/Letta/LangMem: re-fetches source URLs, trust scores, quarantine, 4 MCP tools | No published eval or benchmark. Heavy stack (Postgres, Redis, Celery, React). Decision dependencies ("causal chain") only on the roadmap. 3 stars, no commits since 2026-06 |
| [agent-memory-staleness-audit](https://github.com/a-bhimava/agent-memory-staleness-audit) | Scores staleness from provenance, per-type half-lives and same-subject supersession | Deliberately no network re-validation. STALE eval planned, not yet run |
| [memwatch](https://github.com/kresnapandu/memwatch) | Ebbinghaus-style decay, per-category TTL, contradiction detection | Single commit, inactive |
| STALE (arXiv 2605.06527) | Benchmark for implicit conflicts in conversation. Best model 55.2%, most memory frameworks under 10% | Different problem (see 1.2) |

### 1.2 What Shelf Life adds

1. **It measures when to re-check.** Six re-check policies are replayed on PyPI/GitHub release histories and plotted as stale-answer rate vs check cost. None of the open-source tools I found publish this.
2. **It measures the verifier.** Accuracy of the web_page verifier on hand-labeled Wayback snapshot pairs (Haiku vs Sonnet).
3. **Decisions remember their grounds.** When a supporting claim changes, the decision is flagged for review. MemGuard has this only on its roadmap.
4. **It is light.** One SQLite file, no Docker, connects straight to Claude Desktop and Claude Code. A personal tool meant for daily use.

**Relation to STALE**: STALE measures inferring, from cues in a conversation, that a memory is no longer valid. That inference is the open research problem. Shelf Life does not infer; it **goes back to the source and checks**. This only works for facts that have a source, so the scope is narrower, but in exchange the problem is solvable. Shelf Life does not target a STALE score.

## 2. Usage scenarios

**Scenario 1: a research conclusion goes stale**
```
(Oct) Me: "Let's go with Chatbox for the multi-LLM app. Pro is $19.99/month."
      -> remember: decision + supporting claim ("Chatbox Pro costs $19.99/month", source URL, fast)

(Jan) Me: "Which multi-LLM app did we pick?"
      -> recall: the supporting claim is past its check date -> re-check the pricing page -> changed
      Claude: "In October you picked Chatbox. The reason was 'Pro is $19.99/month',
               which is now $24.99 (checked today, source link). Want to revisit the decision?"
      (The price change is a made-up example.)
```

**Scenario 2: a development decision**
```
Claude Code: "This project decided to use library X.
              X announced end of support last month (GitHub release notes)."
```

**Scenario 3: weekly digest**
```
3 things to revisit this week
- [changed] AWS AIP-C01 exam fee $300 -> $X (source)
- [changed] latest `mcp` package version 1.a -> 1.b
- [revisit decision] "Use Y for the project" (1 supporting claim changed)
```

## 3. Scope

**In**
- Freshness of facts about the world (prices, versions, features, policies, benchmark numbers)
- Links between decisions and their supporting claims (a changed claim flags the decision for review)
- MCP access from Claude Desktop and Claude Code (ChatGPT needs a remote server, so later)
- Eval of write quality, re-check policies and verifier accuracy

**Out (v1)**
- Competing as a general memory store (full conversation storage, graphs, advanced embedding search)
- "Checking" personal preferences or the reasons behind decisions (there is nothing to check against)
- Inferring from conversation cues that a memory is invalid (the STALE problem; Shelf Life re-checks the source instead)
- Automatic checks for facts with no source (marked `unverifiable` only)
- Dashboards, multiple users, cloud sync

## 4. Core concepts

### 4.1 Claim (the smallest unit of memory)

| Field | Meaning | Example |
|---|---|---|
| `text` | One human-readable sentence | "The AWS AIP-C01 exam fee is $300" |
| `kind` | `world_fact` / `decision` / `preference` / `note` | world_fact |
| `subject`, `attribute`, `value` | Structured form of a checkable fact (optional) | AIP-C01 / exam_fee / $300 |
| `volatility` | `fast` / `medium` / `slow` / `none` | fast |
| `volatility_source`, `check_method_source` | Who set volatility and check_method: `caller` / `rule` / `default`. Rules fill only empty fields and never overwrite a caller's value | caller |
| `check_method` | `pypi` / `github_release` / `web_page` / `none` | web_page |
| `check_target` | Package name, owner/repo, or URL. Required with a check method; `pypi` and `github_release` also need a `value` to compare | https://aws.amazon.com/certification/... |
| `source_url`, `source_quote` | Evidence at write time | One verbatim line from the source |
| `observed_at` | When the fact was confirmed true | 2026-10-08 |
| `next_check_at` | Next scheduled check | 2026-10-15 |
| `status` | `fresh` / `changed` / `unverifiable` / `retired`. "Due" is not a status: a claim with a check method that is not retired is due when its `next_check_at` is today or earlier, derived and never stored | fresh |

### 4.2 Volatility classes (defaults; later replaced by adaptive scheduling)

| volatility | Examples | Default check interval |
|---|---|---|
| fast | Prices, latest versions, rankings, benchmark numbers | 7 days |
| medium | Features, APIs, policies, support status | 30 days |
| slow | Concepts, historical facts, design principles | 180 days |
| none | Personal preferences, reasons behind past decisions | Never |

### 4.3 Decisions and their grounds

A `decision` claim points to its supporting claims through `depends_on`. If any supporting claim becomes `changed`, the decision is flagged "revisit". The decision itself is never changed automatically; a person decides.

### 4.4 Check log

Every check is recorded in the `checks` table: when, which method, result (same / changed / cannot_tell / error), old value, new value, evidence quote and cost. This is the audit trail for "why did it answer this way", which matters in regulated domains.

A `web_page` check also records which judgment template was used and what it judged: `prompt_version`, `page_sha256` and `section_sha256` (schema v2, D10). The section hash is the baseline M4's daily run compares with to mark a claim "possibly changed" (D4). `cost_usd` stays empty under the subscription: a judgment made in the conversation (D4 (b)) has no per-call price the server could know.

## 5. Architecture

```
Claude Desktop / Claude Code
        |  MCP (stdio)
        v
shelflife MCP server (Python, MCPServer)
  tools: remember / recall / due / verify / forget / record_check
        |
        v
Store (SQLite + FTS5)  <---  Verifiers
  claims, depends_on, checks      - pypi: PyPI JSON API (rule-based, no LLM)
                                  - github_release: GitHub API (rule-based)
                                  - web_page: fetch page -> compare with claim (see D4)
        ^
        |
Scheduler (cron/launchd): daily due run, weekly digest
```

### 5.1 SQLite schema draft

```sql
CREATE TABLE claims (
  id            TEXT PRIMARY KEY,
  text          TEXT NOT NULL,
  kind          TEXT NOT NULL,          -- world_fact | decision | preference | note
  subject       TEXT, attribute TEXT, value TEXT,
  volatility    TEXT NOT NULL,          -- fast | medium | slow | none
  volatility_source   TEXT NOT NULL,    -- caller | default | rule
  check_method  TEXT NOT NULL,          -- pypi | github_release | web_page | none
  check_method_source TEXT NOT NULL,    -- caller | default | rule
  check_target  TEXT,
  source_url    TEXT, source_quote TEXT,
  observed_at   TEXT NOT NULL,          -- ISO 8601
  recorded_at   TEXT NOT NULL,
  last_checked_at TEXT, next_check_at TEXT,
  status        TEXT NOT NULL DEFAULT 'fresh'
);
CREATE TABLE depends_on (decision_id TEXT, claim_id TEXT, PRIMARY KEY (decision_id, claim_id));
CREATE TABLE checks (
  id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, checked_at TEXT NOT NULL,
  method TEXT NOT NULL, result TEXT NOT NULL,   -- same | changed | cannot_tell | error
  old_value TEXT, new_value TEXT, evidence TEXT, cost_usd REAL,
  prompt_version TEXT, page_sha256 TEXT, section_sha256 TEXT   -- web_page (schema v2, D10)
);
CREATE VIRTUAL TABLE claims_fts USING fts5(text, subject, content='claims', tokenize='trigram');
```

Search works for Korean (D8). The trigram index matches substrings, so a particle fused onto a word ("Chatbox로") does not hide it. Query words shorter than 3 characters, common in Korean, are matched with LIKE. A query word that mixes Latin letters and Hangul is split where the scripts meet, and a common particle there is dropped. Results are ranked by the number of query words matched, then bm25.

### 5.2 MCP tools

| Tool | Input | What it does |
|---|---|---|
| `remember` | text, kind; optional: subject, attribute, value, volatility, check_method, check_target, source_url, source_quote, observed_at, depends_on | Stores a claim. Unknown enum values are rejected, and system-managed fields (id, recorded_at, last_checked_at, next_check_at, status, volatility_source, check_method_source) are never accepted. `text` is the user's sentence as given, in whatever language (D2). The model leaves volatility and check_method empty unless it is confident; for a world fact, empty ones are filled by write-time rules where one applies (`src/shelflife/rules.py`), else by a default, and the `*_source` columns record who set them. The check-method rule fires only when the attribute names a latest-version or latest-release fact, such as `latest_version` or `latest_release` (D5). A `pypi` or `github_release` claim needs a `value`. Claude sets volatility only here, at write time (D4). The user can correct them |
| `recall` | query, verify = auto / never / always | Searches and returns claims (Korean and English; names in their original spelling, D8). With `auto`, due claims are checked before they are served, and results are annotated with "checked today" or "changed: old -> new". `verify` arrives in M4 (D9); for a due `web_page` claim, `auto` returns `verify`'s `judge` payload (D10) |
| `due` | days? | Returns `{"due", "changed", "needs_check_method"}` (D9): claims whose next check is due (within `days`), each with its last check; claims a check found changed, each with that check; world facts with no check method, except those whose `none` the caller set on purpose (D10). Decisions to revisit join in M4 |
| `verify` | claim_id | Checks a claim now. pypi and github_release: the rule-based verifier compares the value, the check is recorded, and it returns `{"claim", "check"}`. The claim keeps its value; `changed` sets its status, and `next_check_at` follows D9. web_page: it fetches the page, selects the relevant section and returns `{"claim", "check": null, "judge": {"prompt_version", "prompt", "url", "section"}}`; Claude judges in the conversation and stores the result with `record_check` (D4, D10). A failed fetch is recorded as `error` |
| `forget` | claim_id | Marks the claim `retired` (history kept, nothing deleted) and returns `{"claim"}`. Forgetting a retired claim again is not an error |
| `record_check` | claim_id, result, new_value?, quote?, reason? | Stores a web_page judgment Claude made in the conversation (D4 (b)) from the section `verify` returned. `result` is same, changed or cannot_tell. Before anything is stored, code checks the quote against the page text `verify` fetched, which the server holds for about 30 minutes (otherwise: call `verify` again). `cannot_tell` needs no quote and may give a short reason. Rules in 5.3 and D10 |

Tool descriptions say when to use each tool and when not to. Claude calls `remember` only when the user asks; it may offer, but waits for the user's confirmation (D3).

### 5.3 web_page verifier

1. Fetch the page and extract its visible text. Only http and https URLs whose host is a public address are fetched, checked again on every redirect, at most 10 MB in about 30 s. The whole body is kept; hidden and struck-through text is dropped
2. Select only the part relevant to the claim (for long pages)
3. Get a structured judgment: same / changed (with new value) / cannot_tell, plus a **verbatim quote** as evidence for same and changed
4. Check in code that the quote really appears on the page (blocks invented evidence)

Under D4 and D10, `verify` does steps 1 and 2 and returns the section with the versioned judgment template. Claude makes the judgment in step 3 in the conversation and stores it with `record_check`. The eval harness reuses the same template, so 6.2 measures what runs in daily use. Step 4 runs in code, before anything is stored, for `same` and `changed`:

- The quote and the page text go through the same `normalize()`: invisible format characters removed, Unicode NFC, each run of whitespace as one space. No visible character changes, so the quote is still verbatim.
- The quote is at least about 20 characters and 3 words, appears exactly once on the page, and lies inside the section `verify` returned.
- `same` needs the claim's value inside the quote. `changed` needs `new_value` inside the quote and different from the claim's value. This value check also folds dashes and quote marks and matches money amounts with their currency ($300 = 300 USD = USD 300 = 300달러).

`cannot_tell` needs no quote. A failed fetch is recorded by the server as `error`.

## 6. Eval: write quality, when to check, whether the check is right

The three questions are measured **separately**, in the order a memory goes through them: write -> schedule -> verify. Separating them keeps costs low and shows where errors come from.

**Principle: Claude does not grade Claude.** Grading comes from code checks, the owner's labels and real-world records (PyPI dates, Wayback snapshots). If an LLM judge is ever used, its agreement with the owner's labels is reported alongside.

### 6.0 Write quality

The user decides what to remember and gives the claim sentence (D2, D3). When Claude calls `remember`, it structures that sentence into fields: (subject, attribute, value), kind, volatility, check_method/check_target, source and quote. If these are wrong, no re-check policy can fix it.

1. **Automatic checks (no labels, run on every claim)**
   - The quote appears verbatim on the source page
   - The value appears inside the quote
   - The check_target exists (PyPI package, GitHub repo, URL responds)
   - **Verify right after write returns `same`**: if a just-written claim verifies as changed or cannot_tell, either the claim or the verifier is wrong
   - Metric: write integrity rate (share of claims passing all four)
   - How they run (D10): pure functions over `remember`-shaped records, so the M8 write eval runs them without a database, plus a read-only CLI that writes one JSON line per claim and check; never inside `remember`. Check 3 fails only on HTTP 404 or 410; a 403, 429, 5xx or network error is reported as blocked. For `web_page`, check 4 needs a judgment and is left out of the rate until M5. The report gives pass, fail and skip counts per check, and the rate is over claims where all four checks applied
2. **Labeled set (small, hand-made)**
   - 40 items from my own research conversations (certifications, multi-LLM apps, memory frameworks; no employer data). An item is one sentence I gave, plus the surrounding turn and the source URL if any (D2). The gold labels are the fields Claude should fill: kind, subject/attribute/value, volatility, check_method/check_target, observed_at and source
   - Metrics: per-field accuracy for the given sentences, volatility confusion matrix. Recall (missed claims) and precision (invented or unneeded claims) measure extraction, which is a stretch goal under D2
   - **Labeling fast as slow is the most expensive error** (checks come too late and stale answers get served). The opposite error only costs extra checks, so the two directions are reported separately
   - Matching is done in code on normalized (subject, attribute); only ambiguous cases are judged by hand
   - Comparisons: Haiku vs Sonnet, prompt v1 (rules only) vs v2 (with examples)
   - **Trap cases** (about 10 of the 40), where the tempting output is a fabrication:
     - a sentence with no checkable value (right answer: check_method `none`)
     - a relative date ("last month") that must not become an invented observed_at
     - a value that belongs to a different subject in the context
     - an unstated check target ("the latest version" with no package named) that must not be guessed
     - two similar values (monthly vs annual price)
   - A filled-in trap is a fabrication and is reported on its own line
3. **Downstream impact (reuses the 6.1 replayer, almost free)**
   - Swap the owner's volatility labels for Claude's in the 6.1 replay and measure how much the stale-answer rate rises
   - Example finding: "When Claude assigns volatility, stale answers rise by X points compared with human labels"
4. **(Stretch) 10 to 15 behavior scenarios**
   - Run scripted conversations with headless Claude Code (`claude -p`) connected to shelflife. The outside world is frozen with recorded responses (fake PyPI, fixed pages) so every run gives the same result
   - Grade tool-call logs in code: did it remember with a source, did it recall before answering, did it tell the user what changed, did it avoid stating a stale value as current

### 6.1 When to check (re-check policy comparison, no LLM cost)

- **Data**: release histories of about 50 PyPI packages and 20 GitHub repos (exact dates). A mix of fast- and slow-changing projects.
- **Simulation**: replay 2024-01 to 2026-09 day by day. Claims like "the latest version of X is ..." appear at random times, and questions arrive at random times. Each policy decides when to check, and the answer at question time is compared with ground truth.
- **Policies** (each mapped to who uses it today, so the comparison is against real prior-art behavior)
  - Never check: the default in Mem0, Zep and Hindsight, which react only to new input
  - Check on every read
  - Fixed interval (7 and 30 days): a plain TTL
  - Per-class interval (table 4.2): closest to memwatch and agent-memory-staleness-audit (per-type half-lives)
  - LLM-judged class interval
  - **Adaptive**: per-claim next check date from the observed change rate
- **Fairness**: the adaptive policy has parameters, so tune them on a dev split (2024 timelines) and report on a held-out test split (2025-01 to 2026-09). Run 5 random seeds for claim and question times and report the mean with a 95% bootstrap interval.
- **Metrics**: stale-answer rate, checks per claim-month (cost), mean days to detect a change
- **Headline figure**: x = checks per claim-month, y = stale-answer rate, one point per policy.
- **Classic background**: search-engine crawlers deciding how often to revisit each page solve the same problem. This project brings a solved problem to a new domain.
  - Cho & Garcia-Molina (2003): sources don't announce changes, so they must be polled. Two freshness metrics and a Poisson change model -> used directly for the metric definitions
  - Cho & Garcia-Molina (2000): pages that change too often can be worth checking less -> used to interpret results
  - Avrachenkov et al. (2020): online change-rate estimation from changed/unchanged observations only -> basis for the **adaptive policy**
  - Kolobov et al. (NeurIPS 2019): optimal re-check scheduling when the change model is unknown
- **Basis for the LLM-judged policy**: fact duration prediction (Zhang & Choi, EMNLP 2023), EverGreenQA (EMNLP 2025)

### 6.2 Whether the check is right (web_page verifier accuracy)

- **Data**: 30 to 40 Wayback Machine snapshot pairs (pricing, feature and policy pages), hand-labeled changed/unchanged plus the new value.
- **Metrics**: accuracy, cannot_tell rate, cost per check. False alarms (unchanged labeled as changed) and missed changes are reported separately.
- **Comparisons**: Haiku vs Sonnet, full page vs relevant section only
- **Trap pairs**: the page layout changed but the value did not (false-alarm trap), and pages that show two similar values such as monthly vs annual price (wrong-value trap).
- **Failure attribution**: for every miss, record whether the selected section contained the evidence. "Extraction miss" and "judgment miss" need opposite fixes, so they are counted separately.

### 6.3 Eval hygiene (patterns borrowed from mature memory repos)

- **Tests and evals are separate.** Tests stub the model, are deterministic and run in CI. Evals use a real model, do not run in CI, and are reported as rates: each LLM item runs 3 times. A single bad run is a reason to re-run, not proof of a regression. (Same split as `hindsight-system-tests` vs `hindsight-system-evals`.)
- **Same model per comparison.** When conditions are compared, everything except the variable under test stays fixed, including model and prompt version.
- **Model runner on the subscription**: Claude Code print mode (`claude -p --model ...`), no API key. Basic Memory's benchmark suite uses the same approach.
- **Run artifacts**: each run writes `eval/results/<run-id>/` with the config, git SHA, model, prompt version, dataset hash, raw per-item outputs and metrics. Metrics can be recomputed from the raw outputs without calling the model again.
- **Smoke corpus**: a tiny synthetic dataset that runs every eval end to end in seconds with no network, used in CI to catch broken pipelines.
- **Label quality**: `eval/data/README.md` is a data card (sources, dates, licenses, labeling rules). After at least a week, re-label a blind 20% sample and report self-agreement. Public benchmark answer keys have had roughly 10% errors, so hand labels get the same scrutiny.

### 6.4 References

| # | Source | Relevance |
|---|---|---|
| 1 | MemGuard README | Closest prior work |
| 2 | agent-memory-staleness-audit README | Prior work; example of naming prior art openly |
| 3 | Cho & Garcia-Molina, "Effective page refresh policies for Web crawlers" (TODS 2003) | Freshness metrics and change model for 6.1 |
| 4 | MemStrata (arXiv 2606.26511) | Source of the 15-40% stale-value figure |
| 5 | STALE (arXiv 2605.06527) | Evidence that existing memory fails on implicit conflicts; scope boundary |
| 6 | Zep (arXiv 2501.13956), Hindsight (arXiv 2512.12818) | Structure of the integration targets |
| 7 | Avrachenkov et al. (arXiv 2004.02167) | Adaptive policy |
| 8 | Zhang & Choi (arXiv 2305.14824) | LLM-judged volatility policy |
| 9 | TRACE (arXiv 2609.33517), FreshQA (arXiv 2310.03214), LongMemEval | Related work |

## 7. Known limitations

- **Only sourced facts are checked.** Facts with no source are stored as `unverifiable`. Preferences and decision reasons are never checked.
- **Some pages cannot be read reliably.** JS-rendered or bot-protected pages produce `cannot_tell`. The rate of `cannot_tell` is reported as a result, not hidden.
- **Small labeled sets.** The write eval (40 snippets) and verifier eval (30-40 pairs) are small, so their results come with wide intervals. The large-sample result is the 6.1 replay.
- **Release histories are a proxy.** PyPI and GitHub release timelines change in a clean, dated way. Prices and policies on web pages change less regularly, which 6.2 covers only partly.
- **ChatGPT needs a remote server.** v1 runs over stdio for Claude Desktop and Claude Code.

## 8. Decisions D1-D4

These were open when the design was written. The owner decided them on 2026-10-13; `docs/decisions.md` records the option chosen, why, and when to revisit each one. The options are kept here for context. Later decisions (D5 onward, such as D8 on Korean search) are recorded only in `docs/decisions.md`.

- **D1: Storage.** A single SQLite file with FTS5 and no embeddings to start. Enough at personal scale; embeddings can be added later if search quality needs it. **Decided:** SQLite + FTS5, no embeddings.
- **D2: Who extracts claims.** The LLM, or the user giving sentences directly. Suggested: direct at first, since extraction quality is a separate problem. Revisit if manual entry turns out to be tedious enough that the tool goes unused. **Decided:** direct entry; Claude only structures the given sentence into fields.
- **D3: When `remember` is called.** Claude calls it on its own during conversations, or only when asked. If on its own, the 6.0 write eval is mandatory. **Decided:** only when asked; Claude may offer, but waits for confirmation.
- **D4: Where LLM judgments happen** (web_page comparison, volatility classification).
  - (a) The server calls the Claude API directly. web_page checks can run in the background. Needs an API key and a small cost.
  - (b) Claude in the conversation judges. `recall` returns "due + relevant part of the current page", Claude compares and stores the result with `record_check`. (M3 moved the hand-off to `verify`, D10.) Works with a Claude subscription only.
  - In both cases the background job (cron) runs without an LLM: pypi/github are decided by rules; web_page only detects whether the relevant section changed (hash comparison) and marks it "possibly changed", and Claude judges at the next conversation or in the weekly digest.
  - Suggested: (b) plus the rule-based background job for v1. Model comparisons in 6.0/6.2 run small-scale with `claude -p --model`.
  - **Decided:** (b) plus the rule-based background job.

## 9. Development workflow (Claude Code cloud)

- Development and tests run in Claude Code cloud sessions. Daily use runs on the local machine.
- **Environment**
  - Core development: the Default environment (Trusted network) is enough. PyPI and GitHub are included.
  - web_page tests and Wayback data collection: switch to Custom, keep the default list, and add `web.archive.org`, `archive.org` and the domains of pages being checked.
  - No setup script is needed (uv, pytest and ruff are preinstalled). Dependencies are installed by the SessionStart hook (`uv sync`) in `.claude/settings.json`.
- **Persistence**: each cloud session is a fresh VM, so SQLite files created there do not survive. For daily use, clone the repo locally and connect the MCP server to Claude Desktop or Claude Code. The DB lives outside the repo, for example `~/.shelflife/shelflife.db` (configurable with `SHELFLIFE_DB`).
- **Example data**: `examples/seed_claims.jsonl` holds a small set of real claims for trying the tool and for demos.

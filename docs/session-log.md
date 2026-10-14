# Session log

Handoff notes between working sessions. Newest entry first. Each entry says where the work stands, what waits on the owner, and what the next session should do first.

## 2026-10-14: #21 and #22 merged (schema v2 is on `main`); #23 open

### State at the end of the session

- Merged into `main`: #19, #20, #21 (**ONE-WAY DOOR**: schema v2, `verify` for web_page, `record_check`, the upgrade notice) and #22 (the four write checks, `check-writes`, the seed edits). M3 is done.
- Open: [#23](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/23) `[stack 5/5]`, branch `claude/tender-mayer-wts8cd-recall-particles`, base `main`: `recall` uses `drop_particle()`, and this log entry. `main` is merged into it.
- #21 has the outside review's changes, in new commits (D10 follow-up 18):
  - the owner's rollback steps, in the description and design 5.1;
  - `selector_version` and `fetched_at` in `checks`, stored by `record_check`;
  - a `claims_fts` rebuild in the migration, and the "never VACUUM without rebuilding claims_fts" note in the schema comment and design 5.1;
  - a timestamped backup when `.bak-v1` exists, a 60 s busy timeout for the migration, and the `checks_claim` index.
- The first daily-use open on the Mac upgrades the database and saves `shelflife.db.bak-v1`; the Rollback steps are in design 5.1.

### Waiting on the owner

- Merge #23.
- An unknown charset label (`LookupError`) is not a recorded error: `decode()` falls back to UTF-8 and the page is judged. A test documents this. Keep it, or record an error instead?
- The owner's last message also answered proposals this session has no record of, probably from another session:
  - a "hardening PR" (to drop the VACUUM note from) and "two new PRs" outside the stack. Neither exists on GitHub.
  - Roadmap defaults: split M5 into M5a (release timelines, dev/test split, smoke corpus) and M5b (Wayback pairs, write-eval snippets, labeling tools, model runner), in the order M1-M3, M5a, M6, M7, M4, M5b, M8, M9; "wording everywhere"; `remember` with volatility `none` skips the rule instead of refusing.
  - None of these were acted on here. `docs/roadmap.md` still has the old order.

### Next session: start here

1. Check #23 (merged? comments? CI?).
2. Find out whether the roadmap order above is decided and who edits the roadmap. If it is, the next milestone is M5a, not M4. Show a plan for it.
3. Notes for M4 from the reviews:
   - `checks` now stores `selector_version` and `fetched_at`, so a selector change can be told apart from a page change.
   - When a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
   - `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors.
   - `now` is read before the write lock; it matters only with three writers within one second.
   - A proper INTEGER PRIMARY KEY for `claims` waits for schema v3.

## 2026-10-14: the M3 stack opened (#19-#21), M3f and recall pushed

### State at the end of the session

- Merged into `main`: #16 (review rules) and #18 (handoff). The owner answered #16's three questions and the M3 review's decisions; they are D10 follow-ups 9-17 and item 7, in #19.
- Open: three stacked PRs (the limit). CI is green on each: tests on 3.11 and 3.13, size, and dependencies.

| PR | Branch | Base | Content |
|---|---|---|---|
| [#19](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/19) `[stack 1/5]` | `claude/tender-mayer-wts8cd-m3c-followups` | `main` | The owner's answers in D8, D9, D10 and the design; `drop_particle()`; this log entry |
| [#20](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/20) `[stack 2/5]` | `claude/tender-mayer-wts8cd-m3d` | #19 | `judgment.py`: template j2, `validate()`, value folding |
| [#21](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/21) `[stack 3/5]` | `claude/tender-mayer-wts8cd-m3e` | #20 | **ONE-WAY DOOR.** Schema v2, `verify` for web_page, `record_check`, the upgrade notice |

- Pushed, not opened yet (no free slot):
  - `claude/tender-mayer-wts8cd-m3f`, stack 4/5, base #21: the write checks and `check-writes`, and the seed edits.
  - `claude/tender-mayer-wts8cd-recall-particles`, stack 5/5, base M3f: `recall` uses `drop_particle()`.
  - Both are reviewed and fixed, and pass 634 and 638 tests. Their descriptions were drafted but live only in this session's scratch space; rewrite them from the commit messages in the CLAUDE.md template.
- Every PR was reviewed by the `pr-reviewer` agent, which loads now, after the earlier round of reviewers and skeptics. Confirmed findings are fixed in new commits. Each PR's description lists what was left as optional.
- Each lower branch was merged into the next one up with merge commits. When #19 merges, retarget #20 to `main`, and so on up the stack.

### Waiting on the owner

- Review and merge of #19, then #20, then #21.
- No open decisions. Things to check:
  - D10 follow-ups 9-17 say what the owner meant;
  - #21's two rollback plans (plan A drops the four columns and keeps the data; it was checked against `main`'s v1 code).

### Next session: start here

1. Check #19-#21 (merged? comments? CI?). Retarget the next PR to `main` as each lower one merges.
2. As slots free, open stack 4/5 (M3f) and then 5/5 (`recall`), with descriptions in the CLAUDE.md template.
3. M3 is done when the stack lands; the roadmap's M3 boxes are ticked in M3e and M3f. Then show a plan for M4 (decisions, scheduler, digest; `recall(verify=auto)` behind `SHELFLIFE_RECALL_VERIFY=never`).
4. Notes for M4 from the reviews:
   - When a section is a window of one long block, `section_sha256` hashes the whole block, so any edit to a one-block page marks the claim "possibly changed".
   - `web_page.py` lets two decode errors out as `UnicodeError` (the `undefined` charset in `_codec`, IDNA in `check_url`); `judge()` records them as errors.

## 2026-10-14: #16 reworked; the M3 stack built and reviewed, not yet opened (handoff)

### State at the end of the session

- Merged into `main` (f1d9c9d): #17, the previous handoff entry.
- Open: [#16](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/16). STEP 1 is done, CI is green and its description follows the new template. It waits for the owner's merge and three decisions, listed in its description. Also open: the PR that adds this entry.
- STEP 2 is built on pushed branches, one per planned PR. No PRs are opened for it yet: the stack should go up after #16, so the new PR checks run on it.

| Order | Branch | Base | Content | Changed lines (excl. tests) |
|---|---|---|---|---|
| 1 | `claude/tender-mayer-wts8cd-m3c-followups` (5d5e44c) | `main` | The owner's answers in D8, D9-5, D10, design and roadmap (M4 `SHELFLIFE_RECALL_VERIFY=never`, M9 launch-readiness pass); `drop_particle()`; 수수료; the fixtures README note | 62 |
| 2 | `claude/tender-mayer-wts8cd-m3d` (90827eb) | 1 | `verifiers/judgment.py`: template `j1` (hash pinned), `render()`, `validate()`, value folding | 221 |
| 3 | `claude/tender-mayer-wts8cd-m3e` (eafbd2f) | 2 | **ONE-WAY DOOR.** Schema v2 with the `.bak-v1` backup (SQLite backup API, under the write lock, notice on stderr); `verify` returns `judge` for web_page; `record_check`; `needs_check_method` leaves out a caller-set none; the tool interface hash is pinned | 269 |
| 4 | `claude/tender-mayer-wts8cd-m3f` (6bf3747) | 3 | `writechecks.py` and `shelflife-memory check-writes`; seed edits (MemGuard none, "60%", eligibility phrase, five `source_quote` proposals); M3 ticked | 164 |
| 5 | `claude/tender-mayer-wts8cd-recall-particles` (65ee73d) | 4 | `query_words()` uses `drop_particle()`, which closes D8's "가격이 vs 가격은" case | 10 |

- All five pass ruff and pytest (on M3e also with Python 3.11).
- A workflow reviewed PRs 1-4: a `pr-reviewer` stand-in plus one deep reviewer per PR, with two skeptics on each must-fix. **The findings below are not fixed yet.**
- The branches are based on f612b2c, not on f1d9c9d, which differs from it only in this log.
- PR descriptions drafted this session were in the container's scratch space and are gone. Rewrite them from the commit messages and these notes, in the CLAUDE.md template.

### Fix first: findings confirmed by both skeptics

**PR 1 (follow-ups):**
- `drop_particle()` falls back to 로 when 으로 fails the 2-character guard, so "앞으로" gives "앞으". Fix: stop at the longest particle that ends the word, and drop it only if 2 characters remain. Add the test cases ("앞으로", "앞으로") and ("방법으로", "방법"). The skeptics rated this optional, but it is a 1-line change.
- The description must not say that "가격" newly finds "가격은"; it already did. The change is that claim words such as "가격은" become "가격".

**PR 2 (M3d, `judgment.py`):**
1. The `ZERO_DECIMALS` lookahead does not fold "$300.00." before a full stop. A correct same is refused, and a false changed is accepted. Fix: `(?<![\d.])(\d+)\.0+(?!\d|\.\d)`, plus a test.
2. A quote cut in the middle of a page number or word passes. For example, the page says "$3000" and the quote ends at "$300", which gives a false same. Fix: also check the value against the quote widened to whole words on the page (from the space before the quote to the space after it).
3. Case: with the value "Free" and the page "free", same is refused but changed "free" is accepted, a false change. Fix: `same_value()` compares casefolded values. Raise case folding as a decision.
4. A Hangul value has no start boundary, so "지원" is found in "미지원" and gives a false same. Fix: before a value that starts with Hangul, require `(?<![가-힣])`.
5. changed with new_value "300" against the claim "$300" is accepted while the page still says "300 USD". Fix: refuse when `value_in(new_value, value)`.

**PR 3 (M3e):**
1. `judge.section.heading` puts page text outside the untrusted-data fence. Fix: drop `heading` from `judge.section`. If the heading should be shown, render it inside the fence and bump `PROMPT_VERSION`.
2. `judge()` records an error only on `FetchError`. A bad host (idna) or a bad charset (`UnicodeError`, `LookupError`) escapes as a tool error and records nothing. Fix: catch `(FetchError, UnicodeError)` around the fetch, `text()`, `extract()` and the hashing. The root causes in `check_url` and `_codec` can go in a follow-up.
3. The Rollback text must say: stop both servers, delete `shelflife.db-wal` and `shelflife.db-shm`, then copy (not move) `shelflife.db.bak-v1` to `shelflife.db`. A stale `-wal` file replays v2 or corrupts the copy.

**PR 4 (M3f):**
1. `summarize()` groups rows by `id`, so records without an id collapse into one. Fix: group by position in the input.
2. A check 3 failure never lowers the rate, because check 4 is then blocked and the record is left out. This is a metric decision for the owner. Option (a): a record with any fail (and no skip or needs_judgment) counts as applied and failing.
3. Check 3 builds URLs from an unvalidated `check_target`, so `mcp/2.3.0` passes. Fix: validate with `pypi.NAME` and `github_release.REPO`. Whether a mismatch is fail or blocked is the owner's call, since D10.7 says only 404 and 410 fail.
4. A record whose check_method a rule would fill skips checks 3 and 4. Proposal: say that the checks take what `remember` stores (M8 passes `claim.to_dict()`); this is documentation only.
5. `examples/README.md` lines 7-8 contradict the seed edits: there are now `source_quote` values, and MemGuard is a caller-set none, so the decision is never flagged. Fix both lines.
6. A non-string value crashes `check-writes`. Fix: read fields through a `_clean`-like helper.

**Optional, worth a look:**
- M3e: take the fetch time before the fetch, not after.
- M3f: check 3 sends no `GITHUB_TOKEN` or API headers; a web_page claim without a value gives skip on check 4.
- M3d: "€" after an amount can take the next amount's symbol; `MONEY_AFTER` backtracks on very long digit runs; "Uſd" raises `KeyError`, which should be refused.
- Follow-ups: design scenario 1 still shows `recall` re-checking by default; the roadmap's "(owner)" definition does not cover the M9 cleanup pass.

### Waiting on the owner

- Merge #16 and its three decisions: the `eval/data/` and `uv.lock` exclusions, the reviewer's file access, and the additions beyond the list. Merge this handoff PR.
- New decisions from the M3 review, to raise in the PR descriptions:
  - case folding in value matching;
  - how a check 3 failure counts in the write integrity rate;
  - fail or blocked for a malformed check_target;
  - from M3e: the `judge.section` shape, `record_check` returning `{claim, check}`, `reason` stored but not shown, and the upgrade notice on stderr;
  - from M3f: approval of the seed `source_quote` values and the two new values.

### Next session: start here

1. Check #16 and this handoff PR (merged? comments?). The `pr-reviewer` agent should load from this session on: the first agent file needed a restart.
2. Fix the confirmed findings as new commits on each branch, starting with PR 1. Then merge each lower branch into the one above it, with merge commits and no rebase. Run the `pr-reviewer` agent on each PR, with two skeptics per must-fix.
3. Open the PRs in order, at most 3 open, titled "[stack n/5]", each naming its base.
   - Open them after #16 has merged, or merge `main` into the branch first. `pr-checks.yml` runs only on a PR whose merge commit contains it.
   - M3e's description lists the migration under "Read these first" and says ONE-WAY DOOR.

## 2026-10-13: Review-rules rework and the rest of M3 approved (handoff)

### State at the end of the session

- Merged into `main` (f612b2c): #15 (the previous handoff entry).
- Open: [#16](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/16), branch `claude/tender-mayer-wts8cd-review-rules`, base `main`, one commit (0f11cab): a "Review rules" section in `CLAUDE.md` plus `REVIEW.md`. The owner asked for a rework (STEP 1 below); **nothing of it is done yet**.
- The owner approved the plan for the rest of M3 (five PRs, below) with additions. No code for it exists yet.

### STEP 1: rework #16 (new commits on its branch, no rebase)

The owner's instructions, close to verbatim:

- Delete `REVIEW.md` (only the managed Code Review product reads it, and the owner does not use it). Split the rules by how each piece loads:
- a) `CLAUDE.md` "Review rules": only what applies while writing code, about 6 lines: PR size (~400 changed lines excluding tests and fixtures); the PR description template (f); the code the owner always reads (`store.py` schema and transactions, MCP tool interfaces, quote and `record_check` validation, eval scoring); prefer the simpler fix and say what was removed; packages need the owner's approval and a PyPI check. Keep `CLAUDE.md` under 200 lines (it is 109 now on #16's branch).
- b) `.claude/skills/pr-review/SKILL.md`: the review checklist. Flag only gaps that affect correctness, security or `docs/decisions.md`; everything else goes in one optional list and is not fixed by default. Check: could it be simpler, what can be deleted, duplicated helpers, changes outside the PR's scope, tests that pass for the wrong reason, tests that duplicate others or test cases that cannot happen (propose tests to delete), defensive code for impossible cases, new dependencies. Output: a must-fix list and an optional list.
- c) `.claude/agents/pr-reviewer.md`: a read-only reviewer subagent (Read, Grep, Glob, and Bash only to run tests) that preloads the pr-review skill and sees only the diff, the PR description and docs. Claude's review workflow uses it from now on (the two skeptics per finding may stay).
- d) CI in `.github/workflows` (today only `ci.yml`): one job fails when the dependencies in `pyproject.toml` change unless the PR has the label `deps-approved` (the owner adds it); one job reports changed lines excluding `tests/` and fixtures, and fails above 600.
- e) A Stop hook in `.claude/settings.json` (today it has only the SessionStart hook) that runs ruff and pytest, so a session cannot end with failing checks.
- f) PR description template. Top part, at most 10 lines: What changed; Read these first (1-3 core files or functions); Decisions needed; Removed or simplified. Then: **Proof** (tests added and what each asserts, one line each; commands run and results), **Confidence** (high / medium / low per part, with a reason for anything not high), **Rollback** (how to undo it; write ONE-WAY DOOR if it changes the DB schema or stored data). Then **Details**.
- Rewrite #16's description in the new template, then tell the owner #16 is updated; the owner merges it right after. Building ahead on pushed branches is allowed meanwhile; open PRs in order, at most 3 open. No need to watch #16.

### STEP 2: the rest of M3, one PR each, in this order

The owner's answers from before the plan (not yet written into the docs; PR 1 does that):

- D10 open questions: 1 (a) a `reason` column in the v2 migration; 2 (a) quote rules only for a web_page claim without a value; 3 (a) also fold numbers in the value check (60% = 60.0%); 4 confirmed: values are compared after folding, so "300 USD" is no change from "$300", and write check 2 uses the same matcher; 5 (a) keep dropping struck-through text, revisit if 6.2 shows misjudgments from the missing "was ... now ..." context; 8 the proxy rule is confirmed. Remove the draft marker from D10's revisit line.
- On #14: M4 hashes `Section.core`; the price synonym group is approved, add `수수료`; drop a trailing D8 particle from a pure-Hangul word only if at least 2 characters remain ("가격은" to "가격", but "속도" and "회의" stay), one shared helper, used by section selection now; switch `recall` to it in a separate small PR after the M3 stack lands (that closes D8's "가격이 vs 가격은").
- Add a note to `tests/fixtures/README.md`: the recorded pages are third-party content kept only as test input, with each page's source URL and recording date.

The approved plan (rough size: src+docs / tests):

| PR | Content | Size |
|---|---|---|
| 1. M3c follow-ups | The answers above into D10, D8 and design 4.4, 5.1 and 5.3; the fixtures README note; `수수료` in the price group; one `drop_particle()` helper in `store.py` next to `PARTICLES` (drops a trailing particle only if at least 2 characters remain, longest particle first: `으로` before `로`); section `terms()` uses it on every Hangul run. | ~60 / ~40 |
| 2. M3d `judgment.py` | The versioned template (a test pins its hash), page text fenced as untrusted data; `render()`, `Judgment`, `validate()`. Quote rules: at least about 20 characters and 3 words, exactly once on the page, inside the section. Value matcher: folds dashes, quote marks, money with currency and numbers (60% = 60.0%; "2.3.0"-style versions are not folded). A claim without a value gets the quote rules only, but a given `new_value` must still appear in the quote (owner: yes). No model-output parser: that goes to M8 (owner: agreed). | ~200 / ~250 |
| 3. M3e tools, schema v2 | **ONE-WAY DOOR.** Schema v2: `prompt_version`, `page_sha256`, `section_sha256` (hash of `Section.core`) and `reason` on `checks`, with the v1 to v2 migration tested on a v1 file. Before migrating, copy the DB file to `shelflife.db.bak-v1` next to it and say so in the output; list the migration under "Read these first". `verify` on web_page returns `judge`, or records `error` when the fetch fails. `record_check` holds the page for 30 minutes and refuses a stale fetch inside the write transaction. `needs_check_method` leaves out a caller-set `none`. Tool descriptions pinned by tests. | ~230 / ~300 |
| 4. M3f write checks + seeds | The four checks as pure functions with an injected fetch, plus a read-only CLI that writes JSON lines with pass, fail, skip and blocked counts. Seed edits: MemGuard becomes `none`, the MetagenomicsBench value becomes "60%", the eligibility value becomes a phrase copied from the page. `source_quote` proposals copied from the fixtures for the owner to approve. Tick the M3 boxes. | ~200 / ~200 |
| 5. After the stack lands | `recall` switches to `drop_particle()`. | ~15 / ~20 |

Roadmap edits the owner asked for (fit them into PR 1 or PR 4):

- M4: `recall(verify=auto)` ships behind a setting that is off by default (`SHELFLIFE_RECALL_VERIFY=never`); note it in D9-5.
- M9: a launch-readiness pass before release: an agent audit (performance, bugs, security, fit to `docs/design.md`) and the owner's own cleanup and refactor pass.

### Waiting on the owner

- Merge of #16 once STEP 1 is pushed, and of this handoff PR.
- Nothing else: the plan, the open D10 questions and the M3e backup rule are all answered above.

### Next session: start here

1. Check #16 and this handoff PR (merged? comments?).
2. Do STEP 1 on `claude/tender-mayer-wts8cd-review-rules` with new commits, update #16's description, tell the owner.
3. Build PR 1 (M3c follow-ups) on `claude/tender-mayer-wts8cd-m3c-followups`, then M3d, M3e, M3f, reviewing each with the new `pr-reviewer` subagent. Keep at most 3 PRs open.

## 2026-10-13: M3a-M3c merged (handoff)

### State at the end of the session

- Merged into `main` (3950817): [#12](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/12) M3a (D10, safe page fetching, http(s)-only URLs), [#13](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/13) M3b (`normalize()`, `extract()`, five recorded seed pages), [#14](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/14) M3c (`verifiers/section.py`). On `main`: 510 passed, 3 xfailed (the known selection misses), ruff clean, CI green on 3.11 and 3.13.
- No PRs are open. Roadmap M3: fetch, extraction and section selection are ticked; the judgment, the `checks` rows for every check and the four write checks remain.
- Plan letters from here (the plan's M3a was split, so the rest moved one letter): M3d judgment module, M3e tools, M3f write checks and seed edits.

### Waiting on the owner

1. D10's open questions 1-5 (in `docs/decisions.md`, under D10 "Open"): where `cannot_tell`'s reason is stored; `same`/`changed` for a web_page claim without a value; MetagenomicsBench "60%" against the page's "60.0%"; Claude's reading that "differs" compares folded values; struck-through text dropped, not marked.
2. Claude's choices to confirm: behind a proxy, host names are left to the proxy (D10.8); M4 hashes `Section.core`; the fee/cost/price synonym group in `section.py`; D10's revisit line.
3. Proposal, not built: drop D8 particles from pure Hangul words in section selection.

### Next session: start here

1. Read CLAUDE.md, this entry, D10 (with its open questions) and roadmap M3. Get the owner's answers to the open questions first: M3d and M3e build on them.
2. Show a short plan for the rest of M3 and wait for approval:
   - M3d `shelflife/judgment.py`: the versioned judgment template (a test pins its hash), render, parse and validate a `Judgment {result, new_value, quote, reason}`; the quote rules of D10-3 on `normalize()`d text; the value matcher of D10-5 (dashes, quote marks, money with currency, plus whatever question 3 decides); page text marked as untrusted.
   - M3e tools: `verify` on web_page returns `{claim, check: null, judge}`; `record_check` with the 30-minute hold and the stale-fetch refusal (D10-2); schema v2 migration tested on a v1 file; `needs_check_method` without caller-set `none`; the MemGuard seed as `none` (caller); tool descriptions and the tests that pin them.
   - M3f write checks (pure functions plus a read-only CLI, D10-7), the seed edits ("60%" per question 3, the eligibility phrase, `source_quote` proposals copied from the fixtures for the owner to approve).
3. Keep PRs near 400 lines: reviews added about half again to M3a-M3c, so plan smaller pieces.

### Notes for the next session

- After any change to fetching, re-record the fixtures (`uv run python tests/fixtures/record.py pages`): that is how the cloud-proxy bug (NO_PROXY lists the proxy itself) was caught.
- Tests refuse DNS lookups and connections (`tests/conftest.py`). Python 3.11 locally: `UV_PROJECT_ENVIRONMENT=<some dir> uv run --python 3.11 pytest -q`; the `fsum` test only fails on 3.11.
- The developer-mode seed URL returns HTTP 404 on purpose (D10): it is the "source moved" case for write check 3.

## 2026-10-13: M3a-M3c open (web_page fetch, extraction, section selection)

### State at the end of the session

- Merged into `main`: #11 (M2d). The owner approved the M3 plan and answered Q1-Q8; the answers are D10 in `docs/decisions.md`.
- The plan's M3a came to about 920 changed lines, so it was split in two and the later PRs shift by one letter. Open, stacked, each reviewed by a workflow (reviewers per angle, two skeptics per finding) with the confirmed findings fixed in later commits:

| PR | Branch | Base | Content |
|---|---|---|---|
| [#12](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/12) M3a `[stack 1/3]` | `claude/tender-mayer-wts8cd-m3a` | `main` | D10 and the doc edits it asked for; safe page fetching (`verifiers/web_page.py`: http(s) and public addresses only, every redirect checked, the connected peer checked, 10 MB and about 30 s) and `decode()`; `remember` takes only http(s) URLs (Q8) |
| [#13](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/13) M3b `[stack 2/3]` | `claude/tender-mayer-wts8cd-m3b` | M3a | `normalize()` and `extract()`: the whole visible body as blocks, hidden and struck text dropped, implied end tags, linear time on hostile pages; five recorded seed pages (`tests/fixtures/pages/`) |
| [#14](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/14) M3c `[stack 3/3]` | `claude/tender-mayer-wts8cd-m3c` | M3b | `verifiers/section.py`: deterministic section selection with its position, heading, core and scores |

- Plan letters from here: M3d judgment module (template, render, parse), M3e tools (`verify` for web_page, `record_check`, schema v2, `needs_check_method` without caller-set `none`), M3f write checks and the seed edits (MemGuard `none` (caller), the eligibility phrase, `source_quote` proposals).
- Found while re-recording: a review fix had made every fetch through the cloud proxy fail (NO_PROXY lists the proxy itself); fixed in M3a with a test that copies that setup. Run `uv run python tests/fixtures/record.py pages` after fetch changes.

### Waiting on the owner

1. Review and merge of #12-#14 (three open PRs: the limit).
2. D10's open questions 1-5: where `cannot_tell`'s reason is stored; `same`/`changed` for a web_page claim without a value; MetagenomicsBench "60%" against the page's "60.0%"; Claude's reading that "differs" compares folded values; struck-through text dropped, not marked as planned.
3. Claude's choices to confirm: behind a proxy, host names are left to the proxy (D10.8); M4 hashes `Section.core`, not the grown section; the fee/cost/price synonym group in `section.py`; D10's revisit line.
4. Not done, proposed: dropping D8 particles from pure Hangul words in section selection ("가격은" matches only "가격은").

### Next session: start here

1. Check #12-#14 (merged? review comments? CI?). When a lower PR merges, retarget the next one to `main` at once.
2. With the open questions answered, build M3d, then M3e and M3f, one PR each, at most three open.

## 2026-10-13: M2d, the owner's follow-ups to #8-#10

### State at the end of the session

- Merged into `main`: #8-#10 (M2a-M2c), so M2 is done apart from these follow-ups.
- Open: [#11](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/11) "M2d: follow-ups from the owner's review of #8-#10", branch `claude/tender-mayer-wts8cd-m2d`, base `main`. It applies the owner's answers to the questions in the entry below:
  1. The check-method rule reads only the attribute, which must say latest, newest, current or 최신 (`latest_version`, `latest_release`). A claim whose text alone mentions the latest version, or whose attribute is a bare `version` or `release`, gets no check method and waits under `due`'s `needs_check_method`. A bare year or a date (2025, 2024-06, 2024-06-20, 2024/06/20) is not a version string; dotted calendar versions (2024.08.30) and compact dates (20240620) still are.
  2. `remember` refuses a `pypi` or `github_release` claim without a `value`; `verify` still refuses one too. `web_page` may have no value.
  3. `add_check` and `forget` run in `BEGIN IMMEDIATE` transactions (`Store._write`), with a test where a second connection retires the claim while a check starts.
  4. `Status.DUE` is gone; design 4.1 says "due" is derived from `next_check_at`.
  5. D9's revisit line is confirmed; the `change` field on changed items is approved as built. Both recorded in `docs/decisions.md` (D5 and D9).

### Waiting on the owner

- Review and merge of #11.
- Nothing else: the owner answered both questions on #11. The attribute must say latest, newest, current or 최신 (a bare `version`, `release`, `버전` or `릴리스` may be a pinned version), and a compact date (20240620) stays a version. Both are in D5.
- Noticed in review, outside M2d: `import_claims` checks which ids exist before its write transaction, so two imports at once could raise an IntegrityError that the CLI prints as a traceback. Rare (the owner runs imports by hand); not fixed.

### Next session: start here

1. Check #11 (merged? review comments? CI?).
2. With #11 merged, show a short plan for M3 (web_page verifier, `record_check` with the verbatim-quote check, the four write checks) and wait for approval.

## 2026-10-13: M2 complete as #8-#10 (handoff)

### State at the end of the session

All three PRs are open, stacked and pushed. Each was reviewed by a Fable workflow (one reviewer per angle, then a skeptic per angle), and the confirmed findings are fixed in new commits:

| PR | Branch | Base | Content |
|---|---|---|---|
| [#8](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/8) `[stack 1/3] M2a` | `claude/tender-mayer-wts8cd-m2a` | `main` | Write-time rules, `pypi` and `github_release` verifiers. Findings 1-8 of the entry below fixed (`ce89a20`), then the Fable round (`5aa054d`). Description rewritten |
| [#9](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/9) `[stack 2/3] M2b` | `claude/tender-mayer-wts8cd-m2b` | M2a branch | `verify` tool, check log, scheduling after a check; D9 |
| [#10](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/10) `[stack 3/3] M2c` | `claude/tender-mayer-wts8cd-m2c` | M2b branch | `forget` tool; `due` returns the due, changed and needs_check_method lists |

The owner's answers from this session:
- The keyword table and "a price amount means fast" are approved as heuristics (design 6.0-3 measures them); `최신` was added to the fast keywords.
- D8's example ("가격이" against "가격은") is confirmed.
- The owner checked the hand-written GitHub fixtures against the live API, and supplied `name` and `published_at`. `record.py` still re-records them; running it on the Mac does not block #8.
- The five M2b interface questions and `forget`'s output are recorded as D9. The owner added the retry cap (3 inconclusive results in a row) and the M4 `supersede` item.

### Waiting on the owner

1. #8: the text path of the check-method rule (no attribute) is too loose. "The latest mcp release requires Python 3.10" (value 3.10) and "The latest API version is 2024-06-20" get a check and a false `changed`, and a bare year counts as a version. The options are in the chat. Until the owner decides, the text path stays as in #8.
2. D9's "Revisit if" line is Claude's draft.
3. Two choices Claude made that the owner may overrule:
   - #9: `verify` refuses a claim without a value.
   - #10: each changed item carries `change`, the check that found the new value.
4. Design 4.1 lists a `due` status that nothing sets, because due-ness comes from `next_check_at`. Should 4.1 say so, or should M4 store it?
5. Optional: `BEGIN IMMEDIATE` in `add_check`, against a forget from another process landing between its read and its write (judged far-fetched in review).

### Next session: start here

1. Check #8-#10 (merged? review comments? CI?). When a lower PR merges, check the upper PR's base at once.
2. Apply the owner's text-path decision as a new commit on `claude/tender-mayer-wts8cd-m2a` (never rebase commits that are in a PR).
3. With M2 merged, show a short plan for M3 (web_page verifier, `record_check` with the verbatim-quote check, the four write checks) and wait for approval.

## 2026-10-13: M2a open as #8 (handoff)

### State at the end of the session

- Merged into `main`: #1-#7 (M1a-M1f). #7 (M1f) pinned all 15 particles in tests and corrected the M1e entry below.
- Open: [#8](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/8) "M2: Volatility classification and rule-based verifiers", branch `claude/tender-mayer-wts8cd-m2a`, opened from the Claude Code UI. CI is green. It contains:
  - `src/shelflife/rules.py`: write-time rules that fill an empty volatility (English and Korean keywords in the attribute, then the text; a price amount means fast) and an empty check_method (pypi or github_release for version facts whose URL is a PyPI project or GitHub repository page). The source is recorded as `rule`.
  - `src/shelflife/verifiers/`: an injectable `Fetch` (urllib, timeout, User-Agent), `FetchError`, `Outcome`, and `compare_version`, whose evidence must appear verbatim in the fetched body; `pypi.py` reads `info.version`, `github_release.py` reads the latest release's `tag_name` (uses `GITHUB_TOKEN` if set).
  - `models.CheckResult`; `store._new_claim` applies the rules.
  - Fixtures: PyPI recorded live and trimmed; GitHub written by hand in the documented shape, because the GitHub API returns 403 from the cloud session. `tests/fixtures/record.py` re-records both.
  - This entry and the CLAUDE.md rule "One session per milestone or so. Before a session ends, update docs/session-log.md." The branch also has a merge of `main` (for #7).
- #8's description was generated by the UI and is wrong in two places: it calls the GitHub fixtures recorded, and it says English keywords use regex word boundaries (they use ASCII-letter lookarounds). Rewrite it per CLAUDE.md once the fixes below are in.

### Do not merge #8 yet: review findings to fix first

A review of #8 (one reviewer per angle, then a skeptic per angle) was cut short by the end of the session. Confirmed by the skeptic:
1. (major) The check_method rule rewrites a caller-supplied `check_target` (a URL becomes the package or repo name, and case changes). D5 and the docs say a caller's value is never replaced. Let the rule fire only when `check_target` is empty, or keep the caller's value as given.
2. (major) The check_method rule fires on any fact whose attribute or text contains "version", "release" or "latest" as a substring ("versioning policy", "released in 2019", "Python version support"). Such facts then get a pypi/github_release check and a permanent false `changed`. Require a latest-version or latest-release fact (for example the attribute `latest_version` / `latest_release`, or whole-word phrasing).
3. (major) Korean keywords match as raw substrings: "정의" inside "일정의", "설정의" or "규정의" makes a world fact slow, which is the expensive error. Drop ambiguous short keywords, or match them at word starts.
4. (major) A medium keyword outranks a price amount, so common price claims become medium, not fast; the precedence is not disclosed. Check the price pattern before medium and slow keywords, and state the precedence in the PR.
5. (nit) The `infer_volatility` docstring misstates the precedence.

Reported by the correctness reviewer but not yet checked by its skeptic:
6. `GITHUB_URL` accepts non-repository pages (such as `github.com/orgs/x/...`) as owner/repo.
7. `compare_version` reports `changed` for equivalent versions ("1.0" and "1.0.0"; tags like "release-1.0").
8. The `check_target` agreement check ignores PyPI name normalization ("-", "_" and "." are equivalent).

The test-gap angle did not finish. Re-run a review of the correctness and tests angles after the fixes.

### Waiting on the owner

- Answers to the five M2b interface questions asked in the chat on 2026-10-13:
  1. When a check finds a new value: proposed that the claim keeps its observed value, its status becomes `changed`, and the `checks` row holds the old and new values; to adopt the new value, the user remembers a new claim and can `forget` the old one. The alternative is updating the value in place, with history in `checks`.
  2. `verify` output: `{"claim": {...}, "check": {"result", "old_value", "new_value", "evidence", "checked_at"}}`.
  3. `due` output: `{"due": [...], "changed": [...], "needs_check_method": [...]}`, replacing the single `"claims"` list.
  4. Scheduling after a check: `same` or `changed` gives next_check_at = check date + class interval; `error` or `cannot_tell` leaves next_check_at alone, so the claim stays due and is retried.
  5. `recall`'s `verify = auto/never/always` parameter (design 5.2): proposed for M4, with the daily due run; `recall` stays read-only in M2.
- The keyword table in `rules.py` and the rule "any price amount means fast" (in #8).
- Confirm the new example in D8's revisit line ("가격이" against "가격은"); asked in #7, which was merged without an explicit answer.
- Run `uv run python tests/fixtures/record.py` on the Mac to replace the hand-written GitHub fixtures with recorded ones.

### What is left of M2

- #8 (M2a): fix the findings above with new commits on its branch, re-review, rewrite the description, merge.
- M2b, after the owner answers the interface questions: the `verify` tool (writes a `checks` row, updates `last_checked_at`, `next_check_at` and `status`), the `forget` tool, and the `due` extension (`changed` claims and the "needs a check method" section).

### Next session: start here

1. Read this entry. Fix #8's findings 1-5 (and 6-8 if they hold) as new commits on `claude/tender-mayer-wts8cd-m2a`; never rebase or recreate commits that are in a PR. Run the checks, re-review, then rewrite #8's description.
2. If the owner has answered the M2b questions, show a short M2b plan; otherwise ask them first.
3. Working rules: at most 3 unmerged PRs; check an upper PR's base as soon as the PR below it merges; update this log before the session ends.

## 2026-10-13: recall follow-ups (M1e)

### State at the end of the session

- The owner answered the four questions of the M1d entry below. The answers went into M1e, which the owner merged as #6; #6 also carried #4's commits, so `main` has M1a-M1e.
- Answers:
  1. Particles: (a) and (b). The `recall` description asks for bare key words, and the store splits a query word where Latin letters meet Hangul, dropping the Hangul part only if it is a common particle (D8, "Added").
  2. Filler words: (a). The `recall` description asks for 2-5 key words (names and nouns), not a full question; D8's revisit line names the filler-word ranking.
  3. `FieldSource.LLM`: removed. It comes back if D4 is revisited (D4 note).
  4. D8's trade-offs and revisit line: confirmed; draft markers removed. The confirmed example in the revisit line ("Chatbox로" against "Chatbox의") no longer fails after answer 1, so M1e replaced it with "가격이" against "가격은". The owner has not confirmed the new example yet.

### Next session: start here

1. Check the small M1f PR (tests for the full particle list, this log entry).
2. M2, as in `docs/roadmap.md`. Keep at most 3 unmerged PRs open, and check an upper PR's base as soon as the PR below it is merged.

## 2026-10-13: owner review of #1-#3, M1d follow-ups

### State at the end of the session

- #1 merged into `main`. #2 and #3 were merged into their stack branches (their bases were still the branches below them), so the owner landed M1b + M1c on `main` through #5. `main`'s tree equals the reviewed M1c head.
- [#4](https://github.com/Myeongcheol-Hong/shelflife-memory/pull/4) "M1d: follow-ups" is open against `main`. It was rebuilt on `main` by cherry-picking the M1d commit, then got one more commit with fixes from its review.
- M1d contents:
  - Korean search (D8): `claims_fts` uses the `trigram` tokenizer; query words shorter than 3 characters use LIKE; ranking is by matched words, then bm25. Schema changed in place at version 1.
  - WAL, so Claude Desktop and Claude Code can each run a server process on the same file. Switching a new file to WAL is retried while another process holds a write lock. The 5-second busy timeout was already Python's default; it is now an explicit constant.
  - Tool wording: `text` is the user's sentence as given (D2), an offer shows the exact sentence and the yes approves it (D3), and `recall` asks for names in their original spelling (D8).
  - Docs: the owner's answers to the proposals in #1-#3 and to questions 1-4 of the entry below, D5-D7 revisit lines confirmed, D8 recorded, the stale "open decisions" pointer in CLAUDE.md fixed.

### Working rules added by the owner

- Do not rebase or recreate commits that are already in an open or merged PR. Add new commits instead.
- When the PR below a stacked PR is merged, check the upper PR's base at once: a PR merged into a stack branch does not reach `main`.

### Owner answers recorded (2026-10-13)

- #1 world facts default to `fast`; #2 `due` leaves out `check_method = none` for now, the extra validation rules, and the M1 meaning of "unverifiable"; #3 refusing unknown arguments and `{"claims": [...]}`: all agreed.
- `porter` stemming: no (Korean matters more, D8).
- Question 1: `text` is the user's sentence as given, in whatever language; never rewritten or translated. Question 2: the offer shows the exact sentence. Question 3: option (i), volatility is set only at write time through `remember`, no new tool (recorded under D4). Question 4: a write-eval item is one given sentence plus the surrounding turn and source URL; the trap list is in design 6.0-2.
- M2 adds a "needs a check method" section to `due`. M5's release timelines are collected by a script the owner runs on the Mac (roadmap M5).

### Questions for the owner

1. A particle in a query word must match the stored particle: "Chatbox의" does not find "Chatbox로 정했다", and "가격이" does not find "가격은". Options: (a) tell the model in the `recall` description to search with bare words ("Chatbox 가격", not "Chatbox의 가격은"); (b) split query words where Latin script meets Hangul ("Chatbox의" becomes "Chatbox" + "의"); (c) leave it, as D8's revisit line already names it.
2. Ranking by matched-word count can put filler-word matches above the right claim for natural-language English questions: "What is the price of Chatbox Pro?" ranks a claim that only shares "the", "is" and "of" above "Chatbox Pro costs $19.99 per month". Keyword queries still rank correctly. Options: (a) tell the model to search with a few key words; (b) stop counting a word that matches most of the store; (c) leave it.
3. `FieldSource.LLM` is now unused (D4 option (i) records Claude's volatility as `caller`). Remove it, or keep it reserved?
4. D8's trade-offs and "Revisit if" line are Claude's drafts; confirm or rewrite them.

### Next session: start here

1. Check #4 (merged? review comments? CI?) and the answers to the questions above.
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

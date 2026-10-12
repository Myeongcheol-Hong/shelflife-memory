# Examples

`seed_claims.jsonl` is a small set of real claims, one JSON object per line, for trying Shelf Life and for demos. Values were observed on the `observed_at` date, so several of them will have changed by the time you read this, which is the point.

Fields follow the claim model in `docs/design.md` section 4.1. A few notes:

- `source_quote` is left out. It is filled in on the first verification, and the quote check rejects any quote that does not appear verbatim on the page.
- `depends_on` links a decision to the claims it rests on. If `seed-memguard-no-eval` changes, the decision `seed-decision-focus` is flagged for review.
- `check_method: none` claims are stored but never re-checked.

# Examples

`seed_claims.jsonl` is a small set of real claims, one JSON object per line, for trying Shelf Life and for demos. Values were observed on the `observed_at` date, so several of them will have changed by the time you read this, which is the point.

Fields follow the claim model in `docs/design.md` section 4.1. A few notes:

- `source_quote`, where given, is copied verbatim from the source page; `shelflife-memory check-writes examples/seed_claims.jsonl` checks that it is still there and that it contains the value (design 6.0-1).
- `depends_on` links a decision to the claims it rests on (`seed-decision-focus` rests on `seed-memguard-no-eval`). That claim's `check_method` is `none`, set on purpose (an absence cannot be quoted, D10), so nothing checks it and the decision is flagged only if the claim is changed by hand.
- `check_method: none` claims are stored but never re-checked.

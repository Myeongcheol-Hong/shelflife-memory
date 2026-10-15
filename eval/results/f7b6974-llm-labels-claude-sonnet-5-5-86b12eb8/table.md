# 6.1 LLM-judged volatility policy (M7), run f7b6974-llm-labels-claude-sonnet-5-5-86b12eb8

Claude (claude-sonnet-5-5, prompt v2) said 3 times how often each project's latest version changes, from its source and name alone. A project's label is the median of its valid answers, and per-class checks it every 7, 30 or 180 days (D14). Both label sets use present-day knowledge of the projects' 2025-2026 releases, so this compares label quality, not foresight (D13).

## Labels

| Maintainer \ Claude | fast | medium | slow | no valid answer |
|---|---|---|---|---|
| fast | 6 | 4 | 1 | 0 |
| medium | 10 | 19 | 2 | 0 |
| slow | 5 | 14 | 9 | 0 |

- Projects, 70: same 34 (49%), Claude faster (more checks) 29 (41%), Claude slower (staler) 7 (10%), invalid 0 (0%).
- Projects without the four labeled late, 66: same 32 (48%), Claude faster (more checks) 28 (42%), Claude slower (staler) 6 (9%), invalid 0 (0%).
- Answers, 210: same 97 (46%), Claude faster (more checks) 89 (42%), Claude slower (staler) 24 (11%), invalid 0 (0%).
- Projects whose answers all agree: 59; decided between two: 0.
- No valid answer, so medium: none.

## Test (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.79 (1.41 to 2.17) | 31.1% (27.2 to 35.1) | 31.0% (27.1 to 35.0) | 6.61 (2.3%) |
| per-class, the maintainer's labels | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -15.4% (-21.5 to -9.4) | -15.5% (-21.6 to -9.4) | 0.67 (0.25 to 1.08) |
| Claude's labels minus fixed 30 | -6.8% (-11.8 to -2.0) | -7.0% (-11.9 to -2.1) | 0.83 (0.46 to 1.21) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 3.0 points (0.9 to 5.2); below 0 is below the curve.

## Dev (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.66 (1.29 to 2.04) | 32.4% (28.0 to 37.0) | 32.3% (27.8 to 36.9) | 7.38 (4.3%) |
| per-class, the maintainer's labels | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -16.4% (-22.7 to -9.9) | -16.3% (-22.7 to -9.8) | 0.69 (0.28 to 1.11) |
| Claude's labels minus fixed 30 | -5.9% (-11.3 to -0.5) | -5.8% (-11.2 to -0.4) | 0.74 (0.37 to 1.12) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 3.1 points (0.8 to 5.7); below 0 is below the curve.

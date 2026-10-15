# 6.1 LLM-judged volatility policy (M7), run f7b6974-llm-labels-claude-fable-5-16d48296

Claude (claude-fable-5, prompt v2) said 3 times how often each project's latest version changes, from its source and name alone. A project's label is the median of its valid answers, and per-class checks it every 7, 30 or 180 days (D14). Both label sets use present-day knowledge of the projects' 2025-2026 releases, so this compares label quality, not foresight (D13).

## Labels

| Maintainer \ Claude | fast | medium | slow | no valid answer |
|---|---|---|---|---|
| fast | 7 | 2 | 2 | 0 |
| medium | 7 | 20 | 4 | 0 |
| slow | 4 | 11 | 13 | 0 |

- Projects, 70: same 40 (57%), Claude faster (more checks) 22 (31%), Claude slower (staler) 8 (11%), invalid 0 (0%).
- Projects without the four labeled late, 66: same 38 (58%), Claude faster (more checks) 21 (32%), Claude slower (staler) 7 (11%), invalid 0 (0%).
- Answers, 210: same 116 (55%), Claude faster (more checks) 67 (32%), Claude slower (staler) 27 (13%), invalid 0 (0%).
- Projects whose answers all agree: 62; decided between two: 0.
- No valid answer, so medium: none.

## Test (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.59 (1.22 to 1.98) | 36.9% (31.9 to 41.9) | 36.8% (31.9 to 41.8) | 8.63 (3.3%) |
| per-class, the maintainer's labels | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -9.6% (-16.1 to -3.1) | -9.7% (-16.1 to -3.2) | 0.47 (0.08 to 0.87) |
| Claude's labels minus fixed 30 | -1.0% (-7.3 to 4.9) | -1.1% (-7.5 to 4.8) | 0.64 (0.26 to 1.03) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 6.5 points (3.6 to 9.8); below 0 is below the curve.

## Dev (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.44 (1.08 to 1.82) | 37.4% (32.7 to 42.2) | 37.3% (32.7 to 42.1) | 8.27 (4.6%) |
| per-class, the maintainer's labels | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -11.4% (-18.2 to -4.8) | -11.3% (-18.2 to -4.7) | 0.47 (0.07 to 0.87) |
| Claude's labels minus fixed 30 | -0.9% (-6.5 to 5.2) | -0.8% (-6.4 to 5.3) | 0.52 (0.16 to 0.90) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 5.4 points (2.7 to 8.4); below 0 is below the curve.

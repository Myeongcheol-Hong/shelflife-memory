# 6.1 LLM-judged volatility policy (M7), run f7b6974-llm-labels-claude-opus-5-5-bf48e181

Claude (claude-opus-5-5, prompt v2) said 3 times how often each project's latest version changes, from its source and name alone. A project's label is the median of its valid answers, and per-class checks it every 7, 30 or 180 days (D14). Both label sets use present-day knowledge of the projects' 2025-2026 releases, so this compares label quality, not foresight (D13).

## Labels

| Maintainer \ Claude | fast | medium | slow | no valid answer |
|---|---|---|---|---|
| fast | 5 | 2 | 2 | 2 |
| medium | 9 | 16 | 3 | 3 |
| slow | 3 | 11 | 9 | 5 |

- Projects, 70: same 30 (43%), Claude faster (more checks) 23 (33%), Claude slower (staler) 7 (10%), invalid 10 (14%).
- Projects without the four labeled late, 66: same 29 (44%), Claude faster (more checks) 21 (32%), Claude slower (staler) 6 (9%), invalid 10 (15%).
- Answers, 210: same 74 (35%), Claude faster (more checks) 47 (22%), Claude slower (staler) 15 (7%), invalid 74 (35%).
- Projects whose answers all agree: 25; decided between two: 2.
- No valid answer, so medium: BurntSushi/ripgrep, attrs, claude-agent-sdk, click, getzep/graphiti, home-assistant/core, instructor, jqlang/jq, pytz, requests.

## Test (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.60 (1.25 to 1.97) | 35.2% (30.4 to 40.6) | 35.2% (30.3 to 40.5) | 8.33 (3.1%) |
| per-class, the maintainer's labels | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -11.3% (-17.8 to -4.2) | -11.3% (-17.9 to -4.3) | 0.47 (0.05 to 0.90) |
| Claude's labels minus fixed 30 | -2.7% (-8.4 to 3.2) | -2.8% (-8.6 to 3.1) | 0.64 (0.29 to 1.02) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 4.9 points (2.0 to 8.1); below 0 is below the curve.

## Dev (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.50 (1.15 to 1.83) | 36.7% (31.7 to 41.6) | 36.6% (31.6 to 41.4) | 8.27 (4.7%) |
| per-class, the maintainer's labels | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -12.1% (-19.1 to -5.1) | -12.0% (-19.1 to -5.0) | 0.53 (0.11 to 0.94) |
| Claude's labels minus fixed 30 | -1.5% (-7.3 to 4.3) | -1.5% (-7.2 to 4.4) | 0.58 (0.23 to 0.91) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 5.4 points (2.7 to 8.7); below 0 is below the curve.

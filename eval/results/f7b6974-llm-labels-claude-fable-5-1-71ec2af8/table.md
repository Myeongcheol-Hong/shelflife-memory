# 6.1 LLM-judged volatility policy (M7), run f7b6974-llm-labels-claude-fable-5-1-71ec2af8

Claude (claude-fable-5-1, prompt v2) said 3 times how often each project's latest version changes, from its source and name alone. A project's label is the median of its valid answers, and per-class checks it every 7, 30 or 180 days (D14). Both label sets use present-day knowledge of the projects' 2025-2026 releases, so this compares label quality, not foresight (D13).

## Labels

| Maintainer \ Claude | fast | medium | slow | no valid answer |
|---|---|---|---|---|
| fast | 8 | 0 | 1 | 2 |
| medium | 9 | 9 | 5 | 8 |
| slow | 5 | 6 | 9 | 8 |

- Projects, 70: same 26 (37%), Claude faster (more checks) 20 (29%), Claude slower (staler) 6 (9%), invalid 18 (26%).
- Projects without the four labeled late, 66: same 25 (38%), Claude faster (more checks) 19 (29%), Claude slower (staler) 6 (9%), invalid 16 (24%).
- Answers, 210: same 59 (28%), Claude faster (more checks) 43 (20%), Claude slower (staler) 10 (5%), invalid 98 (47%).
- Projects whose answers all agree: 22; decided between two: 2.
- No valid answer, so medium: attrs, caddyserver/caddy, certifi, cli/cli, docker/compose, duckdb, gohugoio/hugo, httpx, matplotlib, mypy, pip, prettier/prettier, pyarrow, pytz, redis, starlette, starship/starship, uvicorn.

## Test (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.81 (1.42 to 2.21) | 33.5% (28.8 to 38.1) | 33.4% (28.8 to 38.1) | 7.20 (2.7%) |
| per-class, the maintainer's labels | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -13.0% (-19.4 to -6.6) | -13.1% (-19.5 to -6.7) | 0.69 (0.30 to 1.07) |
| Claude's labels minus fixed 30 | -4.4% (-10.2 to 1.7) | -4.6% (-10.4 to 1.5) | 0.85 (0.46 to 1.25) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 5.6 points (2.8 to 8.6); below 0 is below the curve.

## Dev (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels | 1.64 (1.25 to 2.02) | 33.4% (29.0 to 37.9) | 33.3% (28.9 to 37.8) | 7.25 (3.8%) |
| per-class, the maintainer's labels | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's | -15.4% (-22.2 to -8.5) | -15.2% (-22.0 to -8.4) | 0.67 (0.26 to 1.06) |
| Claude's labels minus fixed 30 | -4.8% (-10.3 to 1.3) | -4.7% (-10.2 to 1.5) | 0.72 (0.33 to 1.10) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 3.8 points (1.4 to 6.7); below 0 is below the curve.

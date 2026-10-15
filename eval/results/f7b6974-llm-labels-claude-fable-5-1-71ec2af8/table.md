# 6.1 LLM-judged volatility policy (M7), run f7b6974-llm-labels-claude-fable-5-1-71ec2af8

Claude (claude-fable-5-1, prompt v2) said 3 times how often each project's latest version changes, from its source and name alone. A project's label is the median of its valid answers, and per-class checks it every 7, 30 or 180 days (D14). Both label sets use present-day knowledge of the projects' 2025-2026 releases, so this compares label quality, not foresight (D13).

Answers are read with parser v2 (D14), set after the runs from the answers' format alone: the last non-empty line, without * and _ and a final period, must be exactly a label. Parser v1, the rule before the runs, read the whole answer; its numbers stand next to v2's.

## Labels

| Maintainer \ Claude (parser v2) | fast | medium | slow | no valid answer |
|---|---|---|---|---|
| fast | 7 | 2 | 2 | 0 |
| medium | 9 | 16 | 6 | 0 |
| slow | 5 | 9 | 14 | 0 |

|  | Parser v2 | Parser v1 |
|---|---|---|
| Projects (70): same / faster / slower / invalid | 37 / 23 / 10 / 0 | 26 / 20 / 6 / 18 |
| Projects without the four labeled late (66): same / faster / slower / invalid | 35 / 22 / 9 / 0 | 25 / 19 / 6 / 16 |
| Answers (210): same / faster / slower / invalid | 112 / 70 / 27 / 1 | 59 / 43 / 10 / 98 |
| Projects whose answers all agree | 60 | 22 |
| Projects decided between two different answers | 0 | 2 |
| No valid answer, so medium | none | attrs, caddyserver/caddy, certifi, cli/cli, docker/compose, duckdb, gohugoio/hugo, httpx, matplotlib, mypy, pip, prettier/prettier, pyarrow, pytz, redis, starlette, starship/starship, uvicorn |

## Test (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels (parser v2) | 1.68 (1.29 to 2.08) | 37.9% (32.8 to 43.0) | 37.9% (32.7 to 43.0) | 8.37 (3.3%) |
| per-class, Claude's labels (parser v1) | 1.81 (1.42 to 2.21) | 33.5% (28.8 to 38.1) | 33.4% (28.8 to 38.1) | 7.20 (2.7%) |
| per-class, the maintainer's labels | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's (parser v2) | -8.6% (-15.4 to -1.6) | -8.6% (-15.4 to -1.7) | 0.56 (0.15 to 0.99) |
| Claude's labels minus the maintainer's (parser v1) | -13.0% (-19.4 to -6.6) | -13.1% (-19.5 to -6.7) | 0.69 (0.30 to 1.07) |
| Claude's labels minus fixed 30 (parser v2) | 0.0% (-6.8 to 6.9) | -0.1% (-7.0 to 6.8) | 0.72 (0.33 to 1.12) |
| Claude's labels minus fixed 30 (parser v1) | -4.4% (-10.2 to 1.7) | -4.6% (-10.4 to 1.5) | 0.85 (0.46 to 1.25) |

Parser v2: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 8.6 points (5.1 to 12.3); below 0 is below the curve.
Parser v1: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 5.6 points (2.8 to 8.6); below 0 is below the curve.

## Dev (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels (parser v2) | 1.50 (1.12 to 1.88) | 38.3% (33.5 to 43.0) | 38.2% (33.4 to 42.9) | 8.35 (5.0%) |
| per-class, Claude's labels (parser v1) | 1.64 (1.25 to 2.02) | 33.4% (29.0 to 37.9) | 33.3% (28.9 to 37.8) | 7.25 (3.8%) |
| per-class, the maintainer's labels | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's (parser v2) | -10.4% (-17.8 to -3.4) | -10.3% (-17.6 to -3.3) | 0.53 (0.13 to 0.94) |
| Claude's labels minus the maintainer's (parser v1) | -15.4% (-22.2 to -8.5) | -15.2% (-22.0 to -8.4) | 0.67 (0.26 to 1.06) |
| Claude's labels minus fixed 30 (parser v2) | 0.1% (-6.3 to 6.8) | 0.2% (-6.2 to 6.8) | 0.58 (0.20 to 0.97) |
| Claude's labels minus fixed 30 (parser v1) | -4.8% (-10.3 to 1.3) | -4.7% (-10.2 to 1.5) | 0.72 (0.33 to 1.10) |

Parser v2: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 7.1 points (4.1 to 10.4); below 0 is below the curve.
Parser v1: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 3.8 points (1.4 to 6.7); below 0 is below the curve.

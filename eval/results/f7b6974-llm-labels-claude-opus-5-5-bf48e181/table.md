# 6.1 LLM-judged volatility policy (M7), run f7b6974-llm-labels-claude-opus-5-5-bf48e181

Claude (claude-opus-5-5, prompt v2) said 3 times how often each project's latest version changes, from its source and name alone. A project's label is the median of its valid answers, and per-class checks it every 7, 30 or 180 days (D14). Both label sets use present-day knowledge of the projects' 2025-2026 releases, so this compares label quality, not foresight (D13).

Answers are read with parser v2 (D14), set after the runs from the answers' format alone: the last non-empty line, without * and _ and a final period, must be exactly a label. Parser v1, the rule before the runs, read the whole answer; its numbers stand next to v2's.

## Labels

| Maintainer \ Claude (parser v2) | fast | medium | slow | no valid answer |
|---|---|---|---|---|
| fast | 7 | 2 | 2 | 0 |
| medium | 11 | 16 | 4 | 0 |
| slow | 4 | 11 | 13 | 0 |

| Maintainer \ Claude (parser v1) | fast | medium | slow | no valid answer |
|---|---|---|---|---|
| fast | 5 | 2 | 2 | 2 |
| medium | 9 | 16 | 3 | 3 |
| slow | 3 | 11 | 9 | 5 |

|  | Parser v2 | Parser v1 |
|---|---|---|
| Projects (70): same / faster / slower / invalid | 36 (51%) / 26 (37%) / 8 (11%) / 0 (0%) | 30 (43%) / 23 (33%) / 7 (10%) / 10 (14%) |
| Projects without the four labeled late (66): same / faster / slower / invalid | 35 (53%) / 24 (36%) / 7 (11%) / 0 (0%) | 29 (44%) / 21 (32%) / 6 (9%) / 10 (15%) |
| Answers (210): same / faster / slower / invalid | 109 (52%) / 75 (36%) / 25 (12%) / 1 (0%) | 74 (35%) / 47 (22%) / 15 (7%) / 74 (35%) |
| Projects whose answers all agree | 59 | 25 |
| Projects decided between two different answers | 0 | 2 |
| No valid answer, so medium | none | BurntSushi/ripgrep, attrs, claude-agent-sdk, click, getzep/graphiti, home-assistant/core, instructor, jqlang/jq, pytz, requests |

## Test (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels (parser v2) | 1.76 (1.36 to 2.16) | 35.0% (30.6 to 39.5) | 34.8% (30.4 to 39.3) | 7.31 (2.9%) |
| per-class, Claude's labels (parser v1) | 1.60 (1.25 to 1.97) | 35.2% (30.4 to 40.6) | 35.2% (30.3 to 40.5) | 8.33 (3.1%) |
| per-class, the maintainer's labels | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's (parser v2) | -11.6% (-18.1 to -4.9) | -11.7% (-18.2 to -5.0) | 0.63 (0.21 to 1.05) |
| Claude's labels minus the maintainer's (parser v1) | -11.3% (-17.8 to -4.2) | -11.3% (-17.9 to -4.3) | 0.47 (0.05 to 0.90) |
| the same, without the four labeled late (parser v2) | -12.1% (-18.7 to -5.5) | -12.2% (-18.8 to -5.6) | 0.63 (0.24 to 1.06) |
| the same, without the four labeled late (parser v1) | -11.9% (-18.6 to -4.5) | -11.9% (-18.7 to -4.6) | 0.46 (0.04 to 0.90) |
| Claude's labels minus fixed 30 (parser v2) | -2.9% (-9.5 to 3.5) | -3.1% (-9.8 to 3.3) | 0.80 (0.41 to 1.21) |
| Claude's labels minus fixed 30 (parser v1) | -2.7% (-8.4 to 3.2) | -2.8% (-8.6 to 3.1) | 0.64 (0.29 to 1.02) |

Parser v2: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 6.5 points (3.5 to 9.7); below 0 is below the curve.
Parser v1: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 4.9 points (2.0 to 8.1); below 0 is below the curve.

## Dev (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class, Claude's labels (parser v2) | 1.60 (1.21 to 1.97) | 35.4% (31.1 to 39.4) | 35.3% (31.0 to 39.3) | 7.25 (4.2%) |
| per-class, Claude's labels (parser v1) | 1.50 (1.15 to 1.83) | 36.7% (31.7 to 41.6) | 36.6% (31.6 to 41.4) | 8.27 (4.7%) |
| per-class, the maintainer's labels | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| Claude's labels minus the maintainer's (parser v2) | -13.4% (-20.3 to -6.4) | -13.3% (-20.1 to -6.3) | 0.63 (0.20 to 1.06) |
| Claude's labels minus the maintainer's (parser v1) | -12.1% (-19.1 to -5.1) | -12.0% (-19.1 to -5.0) | 0.53 (0.11 to 0.94) |
| the same, without the four labeled late (parser v2) | -14.0% (-21.1 to -7.1) | -13.9% (-20.9 to -7.1) | 0.62 (0.18 to 1.08) |
| the same, without the four labeled late (parser v1) | -12.6% (-19.7 to -5.4) | -12.5% (-19.6 to -5.4) | 0.52 (0.09 to 0.94) |
| Claude's labels minus fixed 30 (parser v2) | -2.9% (-8.8 to 3.7) | -2.8% (-8.7 to 3.8) | 0.68 (0.29 to 1.05) |
| Claude's labels minus fixed 30 (parser v1) | -1.5% (-7.3 to 4.3) | -1.5% (-7.2 to 4.4) | 0.58 (0.23 to 0.91) |

Parser v2: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 5.3 points (2.6 to 8.4); below 0 is below the curve.
Parser v1: On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is 5.4 points (2.7 to 8.7); below 0 is below the curve.

# 6.1 every policy on the dense curve (M7e), run 2026-10-16-45ee09a-compare

M7e was asked for by the maintainer after M7's results, so it is not pre-registered; its rules, the tuned intervals and both μ were fixed in D12 before this run, on dev only. Uniform scenario, 1 a week, seeds: 5, 95% intervals over projects. The headline compares scheduled policies; every read (0% stale answers by construction) and the oracle are apart. The true-rate bound knows the future and is exploratory.

7 scheduled policies, each read on its own at 95% with no correction for multiplicity; four of them, budget-aware (M7d) and M7e's three, were added after results and are not pre-registered (D12).

The tuned per-class checks every 30 days whatever the label: it is fixed 30.

## Test

### Scheduled policies

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| per-class tuned 30/30/30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |
| per-class, Claude's labels | 1.76 (1.36 to 2.16) | 35.0% (30.6 to 39.5) | 34.8% (30.4 to 39.3) | 7.31 (2.9%) |
| adaptive p=0.7 a=2 max=180 | 0.78 (0.53 to 1.10) | 54.1% (48.7 to 59.6) | 54.1% (48.7 to 59.5) | 33.39 (10.5%) |
| budget-aware μ=4.846 | 1.03 (0.93 to 1.13) | 36.5% (31.3 to 41.8) | 36.5% (31.3 to 41.8) | 12.62 (3.7%) |
| count-aware μ=4.92 | 0.98 (0.89 to 1.07) | 37.0% (31.5 to 42.5) | 37.0% (31.6 to 42.6) | 28.88 (10.9%) |
| true-rate μ=5.911 (exploratory) | 0.94 (0.83 to 1.03) | 35.7% (30.1 to 41.5) | 35.8% (30.1 to 41.6) | 38.57 (13.6%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| per-class minus fixed 30 | 8.6% (2.4 to 14.5) | 8.5% (2.3 to 14.4) | 0.17 (-0.13 to 0.50) |
| per-class tuned 30/30/30 minus fixed 30 | 0.0% (0.0 to 0.0) | 0.0% (0.0 to 0.0) | 0.00 (0.00 to 0.00) |
| per-class, Claude's labels minus fixed 30 | -2.9% (-9.5 to 3.5) | -3.1% (-9.8 to 3.3) | 0.80 (0.41 to 1.21) |
| adaptive p=0.7 a=2 max=180 minus fixed 30 | 16.2% (10.7 to 21.4) | 16.1% (10.5 to 21.3) | -0.17 (-0.42 to 0.14) |
| budget-aware μ=4.846 minus fixed 30 | -1.4% (-3.5 to 0.5) | -1.4% (-3.5 to 0.5) | 0.07 (-0.02 to 0.17) |
| count-aware μ=4.92 minus fixed 30 | -0.9% (-2.7 to 0.9) | -0.9% (-2.8 to 0.9) | 0.03 (-0.06 to 0.12) |
| true-rate μ=5.911 (exploratory) minus fixed 30 | -2.2% (-3.6 to -0.7) | -2.2% (-3.6 to -0.6) | -0.02 (-0.12 to 0.07) |
| tuned minus per-class | -8.6% (-14.5 to -2.4) | -8.5% (-14.5 to -2.3) | -0.17 (-0.50 to 0.13) |

- per-class: On the fixed-N curve (D12): between fixed 30 and fixed 25, its stale claim-days minus the curve's at the same cost is 11.5 points (7.5 to 15.2); below 0 is below the curve.
- per-class tuned 30/30/30: On the fixed-N curve (D12): between fixed 40 and fixed 30, its stale claim-days minus the curve's at the same cost is 0.0 points (0.0 to 0.0); below 0 is below the curve.
- per-class, Claude's labels: On the fixed-N curve (D12): between fixed 20 and fixed 14, its stale claim-days minus the curve's at the same cost is 7.3 points (4.1 to 10.8); below 0 is below the curve.
- adaptive p=0.7 a=2 max=180: On the fixed-N curve (D12): between fixed 40 and fixed 30, its stale claim-days minus the curve's at the same cost is 12.1 points (7.5 to 16.1); below 0 is below the curve.
- budget-aware μ=4.846: On the fixed-N curve (D12): between fixed 30 and fixed 25, its stale claim-days minus the curve's at the same cost is -0.1 points (-1.1 to 0.9); below 0 is below the curve.
- count-aware μ=4.92: On the fixed-N curve (D12): between fixed 30 and fixed 25, its stale claim-days minus the curve's at the same cost is -0.5 points (-1.4 to 0.4); below 0 is below the curve.
- true-rate μ=5.911 (exploratory): On the fixed-N curve (D12): between fixed 40 and fixed 30, its stale claim-days minus the curve's at the same cost is -2.6 points (-3.7 to -1.7); below 0 is below the curve.

- true-rate μ=5.911 (exploratory) lies below the curve at 95%. Under Bonferroni over the 7 scheduled policies (99.29% each): -4.1 to -1.4 points, still below 0. Minus fixed 30: stale claim-days -2.2% (-3.6 to -0.6), checks per claim-month -0.02 (-0.12 to 0.07).

### Apart: not scheduled

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| every read | 4.29 (4.27 to 4.30) | 0.0% (0.0 to 0.0) | 20.6% (16.4 to 24.9) | 5.91 (2.0%) |
| oracle | 1.96 (1.33 to 2.75) | 0.0% (0.0 to 0.0) | 0.0% (0.0 to 0.0) | 0.00 (0.0%) |

### The dense fixed-N curve

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| fixed 3 | 9.97 (9.97 to 9.97) | 6.0% (4.2 to 8.1) | 6.0% (4.2 to 8.1) | 1.00 (0.5%) |
| fixed 7 | 4.25 (4.24 to 4.25) | 14.4% (10.8 to 18.3) | 14.4% (10.8 to 18.3) | 2.98 (1.2%) |
| fixed 14 | 2.10 (2.10 to 2.10) | 24.2% (19.3 to 29.3) | 24.3% (19.3 to 29.4) | 6.49 (2.1%) |
| fixed 20 | 1.46 (1.45 to 1.46) | 30.2% (24.8 to 35.9) | 30.3% (24.8 to 36.1) | 9.53 (3.1%) |
| fixed 25 | 1.15 (1.15 to 1.16) | 34.4% (28.6 to 40.4) | 34.4% (28.7 to 40.4) | 12.03 (3.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |
| fixed 40 | 0.70 (0.70 to 0.71) | 43.8% (37.6 to 50.2) | 43.8% (37.5 to 50.2) | 19.60 (6.0%) |
| fixed 45 | 0.62 (0.62 to 0.62) | 46.3% (40.0 to 52.7) | 46.3% (39.9 to 52.8) | 22.10 (6.8%) |
| fixed 60 | 0.45 (0.45 to 0.46) | 52.2% (45.9 to 58.7) | 52.3% (45.9 to 58.7) | 29.63 (8.7%) |
| fixed 90 | 0.29 (0.29 to 0.29) | 60.5% (54.3 to 66.8) | 60.5% (54.2 to 66.8) | 44.78 (13.2%) |
| fixed 180 | 0.12 (0.12 to 0.12) | 72.0% (66.0 to 77.9) | 71.9% (65.9 to 77.8) | 90.22 (25.8%) |

### By observed change rate: stale claim-days (checks per claim-month)

| Policy | 0 changes a year (3 projects) | under 6 (22 projects) | 6 to 52 (37 projects) | over 52 (8 projects) |
|---|---|---|---|---|
| fixed 3 | 0.0% (0.0 to 0.0) (9.97) | 1.1% (0.8 to 1.3) (9.97) | 5.4% (4.4 to 6.5) (9.97) | 25.8% (19.2 to 34.6) (9.97) |
| fixed 7 | 0.0% (0.0 to 0.0) (4.25) | 3.1% (2.4 to 3.8) (4.25) | 14.8% (12.1 to 17.7) (4.25) | 51.5% (43.4 to 61.3) (4.24) |
| fixed 14 | 0.0% (0.0 to 0.0) (2.10) | 6.4% (4.9 to 7.9) (2.10) | 27.4% (22.9 to 31.8) (2.10) | 71.7% (65.4 to 78.4) (2.10) |
| fixed 20 | 0.0% (0.0 to 0.0) (1.46) | 9.4% (7.2 to 11.7) (1.45) | 35.3% (30.4 to 40.2) (1.46) | 80.0% (74.8 to 85.0) (1.45) |
| fixed 25 | 0.0% (0.0 to 0.0) (1.16) | 11.5% (8.9 to 14.2) (1.16) | 41.1% (35.9 to 46.2) (1.16) | 83.6% (79.2 to 87.7) (1.15) |
| fixed 30 | 0.0% (0.0 to 0.0) (0.96) | 13.9% (10.7 to 17.3) (0.95) | 45.8% (40.6 to 50.9) (0.95) | 85.9% (81.9 to 89.6) (0.95) |
| fixed 40 | 0.0% (0.0 to 0.0) (0.71) | 18.0% (13.8 to 22.3) (0.70) | 53.8% (48.5 to 58.8) (0.70) | 89.3% (86.0 to 92.3) (0.70) |
| fixed 45 | 0.0% (0.0 to 0.0) (0.62) | 20.1% (15.7 to 24.7) (0.62) | 56.9% (51.5 to 61.9) (0.62) | 90.1% (87.0 to 92.9) (0.62) |
| fixed 60 | 0.0% (0.0 to 0.0) (0.46) | 25.7% (20.0 to 31.4) (0.45) | 64.4% (59.3 to 69.0) (0.45) | 92.6% (90.1 to 94.7) (0.45) |
| fixed 90 | 0.0% (0.0 to 0.0) (0.29) | 34.7% (27.7 to 41.8) (0.29) | 74.0% (69.9 to 77.9) (0.29) | 94.9% (93.2 to 96.3) (0.28) |
| fixed 180 | 0.0% (0.0 to 0.0) (0.13) | 52.2% (43.4 to 60.4) (0.12) | 84.7% (82.0 to 87.3) (0.12) | 97.1% (96.1 to 98.0) (0.12) |
| per-class | 0.0% (0.0 to 0.0) (0.13) | 32.2% (23.1 to 41.2) (0.80) | 55.7% (47.7 to 63.5) (1.04) | 62.5% (46.4 to 80.2) (2.87) |
| per-class tuned 30/30/30 | 0.0% (0.0 to 0.0) (0.96) | 13.9% (10.7 to 17.3) (0.95) | 45.8% (40.6 to 50.9) (0.95) | 85.9% (81.9 to 89.6) (0.95) |
| per-class, Claude's labels | 0.0% (0.0 to 0.0) (0.13) | 36.9% (28.8 to 45.4) (0.39) | 33.2% (28.8 to 38.0) (2.21) | 51.5% (43.4 to 61.3) (4.24) |
| adaptive p=0.7 a=2 max=180 | 0.0% (0.0 to 0.0) (0.13) | 42.6% (35.0 to 49.5) (0.24) | 63.7% (58.6 to 69.1) (0.67) | 62.6% (46.9 to 80.4) (3.23) |
| budget-aware μ=4.846 | 0.0% (0.0 to 0.0) (0.36) | 18.2% (14.7 to 21.5) (0.73) | 42.0% (37.5 to 46.2) (1.18) | 79.0% (72.5 to 85.5) (1.45) |
| count-aware μ=4.92 | 0.0% (0.0 to 0.0) (0.36) | 18.7% (15.0 to 22.3) (0.71) | 41.3% (37.2 to 45.3) (1.21) | 85.5% (77.2 to 93.1) (0.87) |
| true-rate μ=5.911 (exploratory) | 0.0% (0.0 to 0.0) (0.13) | 16.7% (13.9 to 19.5) (0.70) | 38.7% (34.2 to 43.2) (1.26) | 92.6% (86.5 to 97.9) (0.37) |
| every read | 0.0% (0.0 to 0.0) (4.31) | 5.7% (4.4 to 7.0) (4.29) | 23.1% (19.6 to 26.7) (4.28) | 60.6% (54.3 to 67.7) (4.26) |
| oracle | 0.0% (0.0 to 0.0) (0.00) | 0.0% (0.0 to 0.0) (0.32) | 0.0% (0.0 to 0.0) (1.68) | 0.0% (0.0 to 0.0) (9.05) |

## Dev, where the tuned per-class and both μ were set

### Scheduled policies

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| per-class | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| per-class tuned 30/30/30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |
| per-class, Claude's labels | 1.60 (1.21 to 1.97) | 35.4% (31.1 to 39.4) | 35.3% (31.0 to 39.3) | 7.25 (4.2%) |
| adaptive p=0.7 a=2 max=180 | 0.52 (0.34 to 0.76) | 56.6% (50.5 to 62.6) | 56.3% (50.2 to 62.4) | 36.10 (22.5%) |
| budget-aware μ=4.846 | 0.92 (0.82 to 1.01) | 39.1% (33.3 to 44.3) | 38.9% (33.0 to 44.1) | 14.34 (6.5%) |
| count-aware μ=4.92 | 0.92 (0.83 to 1.01) | 38.4% (32.8 to 43.6) | 38.3% (32.6 to 43.5) | 19.05 (13.7%) |
| true-rate μ=5.911 (exploratory) | 0.92 (0.82 to 1.02) | 35.7% (29.7 to 41.3) | 35.5% (29.4 to 41.3) | 30.05 (21.8%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| per-class minus fixed 30 | 10.5% (5.3 to 16.1) | 10.5% (5.3 to 15.9) | 0.05 (-0.23 to 0.35) |
| per-class tuned 30/30/30 minus fixed 30 | 0.0% (0.0 to 0.0) | 0.0% (0.0 to 0.0) | 0.00 (0.00 to 0.00) |
| per-class, Claude's labels minus fixed 30 | -2.9% (-8.8 to 3.7) | -2.8% (-8.7 to 3.8) | 0.68 (0.29 to 1.05) |
| adaptive p=0.7 a=2 max=180 minus fixed 30 | 18.3% (13.8 to 22.9) | 18.3% (13.8 to 22.7) | -0.40 (-0.58 to -0.16) |
| budget-aware μ=4.846 minus fixed 30 | 0.8% (-1.3 to 3.1) | 0.8% (-1.2 to 3.0) | -0.00 (-0.10 to 0.09) |
| count-aware μ=4.92 minus fixed 30 | 0.1% (-1.8 to 2.1) | 0.2% (-1.7 to 2.2) | -0.00 (-0.09 to 0.09) |
| true-rate μ=5.911 (exploratory) minus fixed 30 | -2.6% (-4.1 to -1.1) | -2.5% (-4.0 to -1.0) | -0.00 (-0.10 to 0.10) |
| tuned minus per-class | -10.5% (-16.1 to -5.3) | -10.5% (-16.0 to -5.3) | -0.05 (-0.36 to 0.23) |

- per-class: On the fixed-N curve (D12): between fixed 30 and fixed 25, its stale claim-days minus the curve's at the same cost is 11.4 points (7.3 to 14.9); below 0 is below the curve.
- per-class tuned 30/30/30: On the fixed-N curve (D12): between fixed 40 and fixed 30, its stale claim-days minus the curve's at the same cost is 0.0 points (0.0 to 0.0); below 0 is below the curve.
- per-class, Claude's labels: On the fixed-N curve (D12): between fixed 20 and fixed 14, its stale claim-days minus the curve's at the same cost is 6.3 points (3.5 to 9.5); below 0 is below the curve.
- adaptive p=0.7 a=2 max=180: On the fixed-N curve (D12): between fixed 60 and fixed 45, its stale claim-days minus the curve's at the same cost is 8.6 points (4.2 to 12.4); below 0 is below the curve.
- budget-aware μ=4.846: On the fixed-N curve (D12): between fixed 40 and fixed 30, its stale claim-days minus the curve's at the same cost is 0.8 points (-0.3 to 1.7); below 0 is below the curve.
- count-aware μ=4.92: On the fixed-N curve (D12): between fixed 30 and fixed 25, its stale claim-days minus the curve's at the same cost is 0.2 points (-0.6 to 1.0); below 0 is below the curve.
- true-rate μ=5.911 (exploratory): On the fixed-N curve (D12): between fixed 40 and fixed 30, its stale claim-days minus the curve's at the same cost is -2.5 points (-3.6 to -1.7); below 0 is below the curve.

- true-rate μ=5.911 (exploratory) lies below the curve at 95%. Under Bonferroni over the 7 scheduled policies (99.29% each): -3.9 to -1.4 points, still below 0. Minus fixed 30: stale claim-days -2.5% (-4.0 to -1.0), checks per claim-month -0.00 (-0.10 to 0.10).

### Apart: not scheduled

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| every read | 4.28 (4.26 to 4.30) | 0.0% (0.0 to 0.0) | 20.6% (16.4 to 24.7) | 5.82 (2.6%) |
| oracle | 1.88 (1.30 to 2.56) | 0.0% (0.0 to 0.0) | 0.0% (0.0 to 0.0) | 0.00 (0.0%) |

### The dense fixed-N curve

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| fixed 3 | 9.94 (9.94 to 9.95) | 5.8% (4.2 to 7.7) | 5.8% (4.1 to 7.6) | 1.00 (0.4%) |
| fixed 7 | 4.21 (4.21 to 4.22) | 14.3% (11.0 to 17.9) | 14.4% (11.0 to 18.0) | 3.02 (1.1%) |
| fixed 14 | 2.07 (2.06 to 2.07) | 24.4% (19.3 to 29.4) | 24.4% (19.3 to 29.3) | 6.53 (2.4%) |
| fixed 20 | 1.42 (1.42 to 1.42) | 30.8% (24.8 to 36.3) | 30.7% (24.8 to 36.2) | 9.58 (3.9%) |
| fixed 25 | 1.12 (1.12 to 1.12) | 34.6% (28.2 to 40.5) | 34.6% (28.2 to 40.4) | 12.02 (5.2%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |
| fixed 40 | 0.67 (0.66 to 0.67) | 43.8% (36.9 to 50.1) | 43.6% (36.6 to 50.0) | 19.54 (10.2%) |
| fixed 45 | 0.59 (0.58 to 0.59) | 45.9% (38.8 to 52.2) | 45.7% (38.5 to 52.1) | 22.06 (11.6%) |
| fixed 60 | 0.42 (0.42 to 0.42) | 51.5% (44.2 to 58.0) | 51.2% (43.7 to 57.8) | 29.64 (15.6%) |
| fixed 90 | 0.25 (0.25 to 0.25) | 58.6% (51.1 to 65.2) | 58.3% (50.8 to 64.9) | 44.96 (24.1%) |
| fixed 180 | 0.09 (0.08 to 0.09) | 69.1% (61.9 to 75.3) | 68.8% (61.6 to 75.1) | 89.67 (49.5%) |

### By observed change rate: stale claim-days (checks per claim-month)

| Policy | 0 changes a year (2 projects) | under 6 (20 projects) | 6 to 52 (38 projects) | over 52 (8 projects) |
|---|---|---|---|---|
| fixed 3 | 0.0% (0.0 to 0.0) (9.95) | 0.8% (0.6 to 1.0) (9.95) | 5.3% (4.4 to 6.2) (9.94) | 23.5% (17.3 to 31.7) (9.94) |
| fixed 7 | 0.0% (0.0 to 0.0) (4.22) | 2.5% (1.9 to 3.0) (4.22) | 14.4% (12.0 to 16.8) (4.22) | 50.9% (43.3 to 59.9) (4.21) |
| fixed 14 | 0.0% (0.0 to 0.0) (2.07) | 5.1% (3.9 to 6.3) (2.07) | 26.7% (22.7 to 30.7) (2.07) | 72.3% (66.5 to 78.2) (2.06) |
| fixed 20 | 0.0% (0.0 to 0.0) (1.43) | 7.2% (5.5 to 9.0) (1.42) | 35.3% (30.4 to 40.2) (1.42) | 80.1% (76.1 to 84.5) (1.42) |
| fixed 25 | 0.0% (0.0 to 0.0) (1.13) | 8.8% (6.6 to 10.9) (1.12) | 40.7% (35.4 to 45.9) (1.12) | 83.8% (80.2 to 87.5) (1.12) |
| fixed 30 | 0.0% (0.0 to 0.0) (0.93) | 10.5% (7.8 to 13.1) (0.92) | 45.4% (39.9 to 50.8) (0.92) | 86.6% (83.6 to 89.7) (0.91) |
| fixed 40 | 0.0% (0.0 to 0.0) (0.68) | 13.7% (10.3 to 16.9) (0.67) | 53.1% (47.3 to 58.6) (0.67) | 89.7% (87.6 to 92.1) (0.66) |
| fixed 45 | 0.0% (0.0 to 0.0) (0.59) | 14.9% (11.2 to 18.5) (0.59) | 55.9% (50.1 to 61.4) (0.59) | 91.0% (88.9 to 93.1) (0.58) |
| fixed 60 | 0.0% (0.0 to 0.0) (0.43) | 18.7% (14.1 to 23.2) (0.42) | 63.3% (57.7 to 68.3) (0.42) | 93.0% (91.4 to 94.7) (0.41) |
| fixed 90 | 0.0% (0.0 to 0.0) (0.26) | 26.2% (20.0 to 32.3) (0.25) | 71.6% (66.4 to 76.2) (0.25) | 95.1% (93.8 to 96.4) (0.25) |
| fixed 180 | 0.0% (0.0 to 0.0) (0.09) | 40.5% (31.6 to 48.8) (0.09) | 82.4% (77.8 to 86.0) (0.08) | 97.2% (96.4 to 98.0) (0.08) |
| per-class | 0.0% (0.0 to 0.0) (2.12) | 26.2% (18.2 to 34.5) (0.57) | 58.1% (49.5 to 66.2) (0.95) | 75.2% (59.5 to 87.7) (1.83) |
| per-class tuned 30/30/30 | 0.0% (0.0 to 0.0) (0.93) | 10.5% (7.8 to 13.1) (0.92) | 45.4% (39.9 to 50.8) (0.92) | 86.6% (83.6 to 89.7) (0.91) |
| per-class, Claude's labels | 0.0% (0.0 to 0.0) (0.09) | 28.6% (21.2 to 36.2) (0.33) | 37.8% (32.9 to 43.2) (1.84) | 50.9% (43.3 to 59.9) (4.21) |
| adaptive p=0.7 a=2 max=180 | 0.0% (0.0 to 0.0) (0.25) | 33.0% (26.2 to 39.9) (0.20) | 67.8% (61.3 to 73.7) (0.46) | 77.5% (60.4 to 90.9) (1.81) |
| budget-aware μ=4.846 | 0.0% (0.0 to 0.0) (0.61) | 15.2% (11.9 to 18.7) (0.62) | 45.8% (40.4 to 51.0) (1.00) | 79.7% (74.4 to 85.7) (1.40) |
| count-aware μ=4.92 | 0.0% (0.0 to 0.0) (0.61) | 15.2% (11.9 to 18.8) (0.62) | 44.0% (39.2 to 48.4) (1.07) | 83.3% (76.2 to 90.2) (1.09) |
| true-rate μ=5.911 (exploratory) | 0.0% (0.0 to 0.0) (0.09) | 13.4% (10.9 to 15.8) (0.62) | 38.5% (34.2 to 42.8) (1.22) | 91.2% (85.2 to 96.8) (0.45) |
| every read | 0.0% (0.0 to 0.0) (4.30) | 4.6% (3.5 to 5.6) (4.24) | 22.6% (19.4 to 25.9) (4.30) | 59.7% (54.0 to 66.6) (4.26) |
| oracle | 0.0% (0.0 to 0.0) (0.00) | 0.0% (0.0 to 0.0) (0.26) | 0.0% (0.0 to 0.0) (1.63) | 0.0% (0.0 to 0.0) (8.10) |

### The tuned per-class grid (exploratory)

| Policy | Checks per claim-month | Stale claim-days |  |
|---|---|---|---|
| per-class tuned 3/14/30 | 2.550 | 26.4% |  |
| per-class tuned 3/14/45 | 2.408 | 29.6% |  |
| per-class tuned 3/14/60 | 2.337 | 32.0% |  |
| per-class tuned 3/14/90 | 2.266 | 35.1% |  |
| per-class tuned 3/14/120 | 2.231 | 37.2% |  |
| per-class tuned 3/21/30 | 2.226 | 30.1% |  |
| per-class tuned 3/21/45 | 2.084 | 33.3% |  |
| per-class tuned 3/21/60 | 2.013 | 35.7% |  |
| per-class tuned 3/21/90 | 1.942 | 38.8% |  |
| per-class tuned 3/21/120 | 1.907 | 40.9% |  |
| per-class tuned 3/30/30 | 2.032 | 33.5% |  |
| per-class tuned 3/30/45 | 1.889 | 36.6% |  |
| per-class tuned 3/30/60 | 1.819 | 39.0% |  |
| per-class tuned 3/30/90 | 1.748 | 42.1% |  |
| per-class tuned 3/30/120 | 1.712 | 44.3% |  |
| per-class tuned 3/45/30 | 1.881 | 37.3% |  |
| per-class tuned 3/45/45 | 1.739 | 40.4% |  |
| per-class tuned 3/45/60 | 1.668 | 42.8% |  |
| per-class tuned 3/45/90 | 1.597 | 45.9% |  |
| per-class tuned 3/45/120 | 1.562 | 48.1% |  |
| per-class tuned 5/14/30 | 2.055 | 27.3% |  |
| per-class tuned 5/14/45 | 1.913 | 30.5% |  |
| per-class tuned 5/14/60 | 1.842 | 32.8% |  |
| per-class tuned 5/14/90 | 1.771 | 35.9% |  |
| per-class tuned 5/14/120 | 1.736 | 38.1% |  |
| per-class tuned 5/21/30 | 1.732 | 31.0% |  |
| per-class tuned 5/21/45 | 1.589 | 34.2% |  |
| per-class tuned 5/21/60 | 1.518 | 36.5% |  |
| per-class tuned 5/21/90 | 1.448 | 39.6% |  |
| per-class tuned 5/21/120 | 1.412 | 41.8% |  |
| per-class tuned 5/30/30 | 1.537 | 34.3% |  |
| per-class tuned 5/30/45 | 1.394 | 37.5% |  |
| per-class tuned 5/30/60 | 1.324 | 39.8% |  |
| per-class tuned 5/30/90 | 1.253 | 42.9% |  |
| per-class tuned 5/30/120 | 1.217 | 45.1% |  |
| per-class tuned 5/45/30 | 1.387 | 38.1% |  |
| per-class tuned 5/45/45 | 1.244 | 41.3% |  |
| per-class tuned 5/45/60 | 1.173 | 43.6% |  |
| per-class tuned 5/45/90 | 1.103 | 46.7% |  |
| per-class tuned 5/45/120 | 1.067 | 48.9% |  |
| per-class tuned 7/14/30 | 1.844 | 27.9% |  |
| per-class tuned 7/14/45 | 1.701 | 31.1% |  |
| per-class tuned 7/14/60 | 1.631 | 33.5% |  |
| per-class tuned 7/14/90 | 1.560 | 36.6% |  |
| per-class tuned 7/14/120 | 1.525 | 38.7% |  |
| per-class tuned 7/21/30 | 1.520 | 31.6% |  |
| per-class tuned 7/21/45 | 1.378 | 34.8% |  |
| per-class tuned 7/21/60 | 1.307 | 37.2% |  |
| per-class tuned 7/21/90 | 1.236 | 40.3% |  |
| per-class tuned 7/21/120 | 1.201 | 42.4% |  |
| per-class tuned 7/30/30 | 1.325 | 35.0% |  |
| per-class tuned 7/30/45 | 1.183 | 38.1% |  |
| per-class tuned 7/30/60 | 1.112 | 40.5% |  |
| per-class tuned 7/30/90 | 1.041 | 43.6% |  |
| per-class tuned 7/30/120 | 1.006 | 45.8% |  |
| per-class tuned 7/45/30 | 1.175 | 38.8% |  |
| per-class tuned 7/45/45 | 1.033 | 41.9% |  |
| per-class tuned 7/45/60 | 0.962 | 44.3% |  |
| per-class tuned 7/45/90 | 0.891 | 47.4% | within fixed 30's cost |
| per-class tuned 7/45/120 | 0.856 | 49.6% | within fixed 30's cost |
| per-class tuned 10/14/30 | 1.685 | 28.7% |  |
| per-class tuned 10/14/45 | 1.543 | 31.9% |  |
| per-class tuned 10/14/60 | 1.472 | 34.2% |  |
| per-class tuned 10/14/90 | 1.401 | 37.4% |  |
| per-class tuned 10/14/120 | 1.366 | 39.5% |  |
| per-class tuned 10/21/30 | 1.361 | 32.4% |  |
| per-class tuned 10/21/45 | 1.219 | 35.6% |  |
| per-class tuned 10/21/60 | 1.148 | 38.0% |  |
| per-class tuned 10/21/90 | 1.077 | 41.1% |  |
| per-class tuned 10/21/120 | 1.042 | 43.2% |  |
| per-class tuned 10/30/30 | 1.166 | 35.7% |  |
| per-class tuned 10/30/45 | 1.024 | 38.9% |  |
| per-class tuned 10/30/60 | 0.953 | 41.3% |  |
| per-class tuned 10/30/90 | 0.883 | 44.4% | within fixed 30's cost |
| per-class tuned 10/30/120 | 0.847 | 46.6% | within fixed 30's cost |
| per-class tuned 10/45/30 | 1.016 | 39.5% |  |
| per-class tuned 10/45/45 | 0.874 | 42.7% | within fixed 30's cost |
| per-class tuned 10/45/60 | 0.803 | 45.1% | within fixed 30's cost |
| per-class tuned 10/45/90 | 0.732 | 48.2% | within fixed 30's cost |
| per-class tuned 10/45/120 | 0.697 | 50.4% | within fixed 30's cost |
| per-class tuned 14/14/30 | 1.579 | 29.4% |  |
| per-class tuned 14/14/45 | 1.437 | 32.6% |  |
| per-class tuned 14/14/60 | 1.366 | 35.0% |  |
| per-class tuned 14/14/90 | 1.295 | 38.1% |  |
| per-class tuned 14/14/120 | 1.260 | 40.2% |  |
| per-class tuned 14/21/30 | 1.255 | 33.1% |  |
| per-class tuned 14/21/45 | 1.113 | 36.3% |  |
| per-class tuned 14/21/60 | 1.042 | 38.7% |  |
| per-class tuned 14/21/90 | 0.971 | 41.8% |  |
| per-class tuned 14/21/120 | 0.936 | 43.9% |  |
| per-class tuned 14/30/30 | 1.061 | 36.5% |  |
| per-class tuned 14/30/45 | 0.918 | 39.6% | within fixed 30's cost |
| per-class tuned 14/30/60 | 0.848 | 42.0% | within fixed 30's cost |
| per-class tuned 14/30/90 | 0.777 | 45.1% | within fixed 30's cost |
| per-class tuned 14/30/120 | 0.741 | 47.3% | within fixed 30's cost |
| per-class tuned 14/45/30 | 0.910 | 40.3% | within fixed 30's cost |
| per-class tuned 14/45/45 | 0.768 | 43.4% | within fixed 30's cost |
| per-class tuned 14/45/60 | 0.697 | 45.8% | within fixed 30's cost |
| per-class tuned 14/45/90 | 0.626 | 48.9% | within fixed 30's cost |
| per-class tuned 14/45/120 | 0.591 | 51.1% | within fixed 30's cost |
| per-class tuned 21/14/30 | 1.491 | 30.3% |  |
| per-class tuned 21/14/45 | 1.349 | 33.5% |  |
| per-class tuned 21/14/60 | 1.278 | 35.8% |  |
| per-class tuned 21/14/90 | 1.207 | 38.9% |  |
| per-class tuned 21/14/120 | 1.172 | 41.1% |  |
| per-class tuned 21/21/30 | 1.167 | 34.0% |  |
| per-class tuned 21/21/45 | 1.025 | 37.2% |  |
| per-class tuned 21/21/60 | 0.954 | 39.5% |  |
| per-class tuned 21/21/90 | 0.883 | 42.7% | within fixed 30's cost |
| per-class tuned 21/21/120 | 0.848 | 44.8% | within fixed 30's cost |
| per-class tuned 21/30/30 | 0.973 | 37.3% |  |
| per-class tuned 21/30/45 | 0.830 | 40.5% | within fixed 30's cost |
| per-class tuned 21/30/60 | 0.760 | 42.9% | within fixed 30's cost |
| per-class tuned 21/30/90 | 0.689 | 46.0% | within fixed 30's cost |
| per-class tuned 21/30/120 | 0.653 | 48.1% | within fixed 30's cost |
| per-class tuned 21/45/30 | 0.822 | 41.1% | within fixed 30's cost |
| per-class tuned 21/45/45 | 0.680 | 44.3% | within fixed 30's cost |
| per-class tuned 21/45/60 | 0.609 | 46.7% | within fixed 30's cost |
| per-class tuned 21/45/90 | 0.538 | 49.8% | within fixed 30's cost |
| per-class tuned 21/45/120 | 0.503 | 51.9% | within fixed 30's cost |
| per-class tuned 30/14/30 | 1.439 | 31.0% |  |
| per-class tuned 30/14/45 | 1.296 | 34.2% |  |
| per-class tuned 30/14/60 | 1.226 | 36.5% |  |
| per-class tuned 30/14/90 | 1.155 | 39.7% |  |
| per-class tuned 30/14/120 | 1.119 | 41.8% |  |
| per-class tuned 30/21/30 | 1.115 | 34.7% |  |
| per-class tuned 30/21/45 | 0.972 | 37.9% |  |
| per-class tuned 30/21/60 | 0.902 | 40.3% | within fixed 30's cost |
| per-class tuned 30/21/90 | 0.831 | 43.4% | within fixed 30's cost |
| per-class tuned 30/21/120 | 0.795 | 45.5% | within fixed 30's cost |
| per-class tuned 30/30/30 | 0.920 | 38.0% | selected |
| per-class tuned 30/30/45 | 0.777 | 41.2% | within fixed 30's cost |
| per-class tuned 30/30/60 | 0.707 | 43.6% | within fixed 30's cost |
| per-class tuned 30/30/90 | 0.636 | 46.7% | within fixed 30's cost |
| per-class tuned 30/30/120 | 0.601 | 48.9% | within fixed 30's cost |
| per-class tuned 30/45/30 | 0.770 | 41.8% | within fixed 30's cost |
| per-class tuned 30/45/45 | 0.627 | 45.0% | within fixed 30's cost |
| per-class tuned 30/45/60 | 0.557 | 47.4% | within fixed 30's cost |
| per-class tuned 30/45/90 | 0.486 | 50.5% | within fixed 30's cost |
| per-class tuned 30/45/120 | 0.450 | 52.7% | within fixed 30's cost |

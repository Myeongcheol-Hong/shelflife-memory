# 6.1 adaptive policy (M7), run 2026-10-15-e2d0e3d-adaptive

Selected on dev (D12): adaptive p=0.7 a=2 max=180, the lowest stale claim-days among the grid
points costing at most per-class's 0.97 checks per claim-month on dev.
Uniform scenario, 1 a week, seeds: 5, 95% intervals over projects.

## Test

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| adaptive p=0.7 a=2 max=180 | 0.78 (0.53 to 1.10) | 54.1% (48.7 to 59.6) | 54.1% (48.7 to 59.5) | 33.39 (10.5%) |
| per-class | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |
| adaptive p=0.7 a=2 max=180 label-free | 0.58 (0.52 to 0.65) | 51.1% (46.0 to 56.0) | 51.1% (46.0 to 55.9) | 22.85 (5.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| selected minus per-class | 7.6% (5.3 to 10.0) | 7.6% (5.2 to 9.9) | -0.34 (-0.56 to -0.12) |
| selected minus fixed 30 | 16.2% (10.7 to 21.4) | 16.1% (10.5 to 21.3) | -0.17 (-0.42 to 0.14) |
| label-free minus selected | -3.0% (-6.9 to 1.2) | -3.0% (-6.9 to 1.1) | -0.20 (-0.48 to 0.02) |

On the fixed-N curve (D12): between fixed 60 and fixed 30, its stale claim-days minus the curve's at the same cost is 11.2 points (6.7 to 15.6); below 0 is below the curve.

## Dev

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| adaptive p=0.7 a=2 max=180 | 0.52 (0.34 to 0.76) | 56.6% (50.5 to 62.6) | 56.3% (50.2 to 62.4) | 36.10 (22.5%) |
| per-class | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| selected minus per-class | 7.8% (5.6 to 9.9) | 7.8% (5.6 to 9.9) | -0.45 (-0.67 to -0.26) |
| selected minus fixed 30 | 18.3% (13.8 to 22.9) | 18.3% (13.8 to 22.7) | -0.40 (-0.58 to -0.16) |

On the fixed-N curve (D12): between fixed 60 and fixed 30, its stale claim-days minus the curve's at the same cost is 7.9 points (4.2 to 11.5); below 0 is below the curve.

Label-free runs are exploratory (D12); staleness differences are in points.

## Dev grid (exploratory)

| Policy | Checks per claim-month | Stale claim-days |  |
|---|---|---|---|
| adaptive p=0.05 a=0.5 max=180 | 2.75 | 55.2% |  |
| adaptive p=0.05 a=0.5 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.05 a=1 max=180 | 2.90 | 54.7% |  |
| adaptive p=0.05 a=1 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.05 a=2 max=180 | 13.14 | 4.9% |  |
| adaptive p=0.05 a=2 max=365 | 13.14 | 4.9% |  |
| adaptive p=0.1 a=0.5 max=180 | 1.69 | 57.4% |  |
| adaptive p=0.1 a=0.5 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.1 a=1 max=180 | 1.84 | 56.4% |  |
| adaptive p=0.1 a=1 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.1 a=2 max=180 | 8.30 | 11.3% |  |
| adaptive p=0.1 a=2 max=365 | 8.30 | 11.3% |  |
| adaptive p=0.2 a=0.5 max=180 | 0.68 | 61.6% | within per-class's cost |
| adaptive p=0.2 a=0.5 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.2 a=1 max=180 | 0.89 | 59.5% | within per-class's cost |
| adaptive p=0.2 a=1 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.2 a=2 max=180 | 4.40 | 23.5% |  |
| adaptive p=0.2 a=2 max=365 | 4.40 | 23.5% |  |
| adaptive p=0.3 a=0.5 max=180 | 0.30 | 65.0% | within per-class's cost |
| adaptive p=0.3 a=0.5 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.3 a=1 max=180 | 0.50 | 62.1% | within per-class's cost |
| adaptive p=0.3 a=1 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.3 a=2 max=180 | 2.70 | 33.7% |  |
| adaptive p=0.3 a=2 max=365 | 2.70 | 33.7% |  |
| adaptive p=0.5 a=0.5 max=180 | 0.10 | 68.2% | within per-class's cost |
| adaptive p=0.5 a=0.5 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.5 a=1 max=180 | 0.19 | 66.1% | within per-class's cost |
| adaptive p=0.5 a=1 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.5 a=2 max=180 | 1.13 | 47.1% |  |
| adaptive p=0.5 a=2 max=365 | 1.11 | 48.9% |  |
| adaptive p=0.7 a=0.5 max=180 | 0.09 | 68.8% | within per-class's cost |
| adaptive p=0.7 a=0.5 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.7 a=1 max=180 | 0.11 | 67.8% | within per-class's cost |
| adaptive p=0.7 a=1 max=365 | 0.00 | 75.6% | within per-class's cost |
| adaptive p=0.7 a=2 max=180 | 0.52 | 56.3% | selected |
| adaptive p=0.7 a=2 max=365 | 0.49 | 59.9% | within per-class's cost |
| per-class | 0.97 | 48.6% |  |
| fixed 3 | 9.94 | 5.8% |  |
| fixed 7 | 4.21 | 14.4% |  |
| fixed 14 | 2.07 | 24.4% |  |
| fixed 30 | 0.92 | 38.0% |  |
| fixed 60 | 0.42 | 51.2% |  |
| fixed 90 | 0.25 | 58.3% |  |
| fixed 180 | 0.09 | 68.8% |  |

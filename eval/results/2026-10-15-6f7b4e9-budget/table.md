# 6.1 budget-aware allocation (M7), run 2026-10-15-6f7b4e9-budget

Asked for by the maintainer after M7b's results, so not pre-registered; the rule and μ = 4.84557 days were fixed in D12 before this run. μ was set on dev by cost alone, at most fixed 30's dev cost.

## Test (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| budget-aware μ=4.846 | 1.03 (0.93 to 1.13) | 36.5% (31.3 to 41.8) | 36.5% (31.3 to 41.8) | 12.62 (3.7%) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| budget-aware μ=4.846 minus fixed 30 | -1.4% (-3.5 to 0.5) | -1.4% (-3.5 to 0.5) | 0.07 (-0.02 to 0.17) |

On the fixed-N curve (D12): between fixed 30 and fixed 14, its stale claim-days minus the curve's at the same cost is -0.6 points (-1.6 to 0.5); below 0 is below the curve.

## Dev, where μ was set (uniform, 1 a week, seeds: 5, 95% intervals over projects)

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|---|
| budget-aware μ=4.846 | 0.92 (0.82 to 1.01) | 39.1% (33.3 to 44.3) | 38.9% (33.0 to 44.1) | 14.34 (6.5%) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) |

| Paired, on the same claims | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| budget-aware μ=4.846 minus fixed 30 | 0.8% (-1.3 to 3.1) | 0.8% (-1.2 to 3.0) | -0.00 (-0.10 to 0.09) |

On the fixed-N curve (D12): between fixed 60 and fixed 30, its stale claim-days minus the curve's at the same cost is 0.8 points (-0.5 to 1.6); below 0 is below the curve.

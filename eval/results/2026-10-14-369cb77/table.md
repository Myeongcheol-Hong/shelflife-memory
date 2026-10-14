# 6.1 replay, run 2026-10-14-369cb77

Test split, uniform scenario, questions 1 a week per claim; 1400 claims about 70 projects per seed. 95% intervals over resampled projects (D12). Days to detect counts only the changes found; the share left undetected follows it.

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) | Peak per day (to mean) |
|---|---|---|---|---|---|
| oracle | 1.96 (1.33 to 2.75) | 0.0% (0.0 to 0.0) | 0.0% (0.0 to 0.0) | 0.00 (0.0%) | 180 (x4.0) |
| every read | 4.29 (4.27 to 4.30) | 0.0% (0.0 to 0.0) | 20.6% (16.4 to 24.9) | 5.91 (2.0%) | 223 (x2.3) |
| fixed 3 | 9.97 (9.97 to 9.97) | 6.0% (4.2 to 8.1) | 6.0% (4.2 to 8.1) | 1.00 (0.5%) | 484 (x2.1) |
| fixed 7 | 4.25 (4.24 to 4.25) | 14.4% (10.8 to 18.3) | 14.4% (10.8 to 18.3) | 2.98 (1.2%) | 213 (x2.2) |
| fixed 14 | 2.10 (2.10 to 2.10) | 24.2% (19.3 to 29.3) | 24.3% (19.3 to 29.4) | 6.49 (2.1%) | 113 (x2.3) |
| fixed 30 | 0.95 (0.95 to 0.96) | 37.9% (32.0 to 44.1) | 38.0% (32.0 to 44.2) | 14.51 (4.5%) | 57 (x2.6) |
| fixed 60 | 0.45 (0.45 to 0.46) | 52.2% (45.9 to 58.7) | 52.3% (45.9 to 58.7) | 29.63 (8.7%) | 31 (x3.0) |
| fixed 90 | 0.29 (0.29 to 0.29) | 60.5% (54.3 to 66.8) | 60.5% (54.2 to 66.8) | 44.78 (13.2%) | 23 (x3.5) |
| fixed 180 | 0.12 (0.12 to 0.12) | 72.0% (66.0 to 77.9) | 71.9% (65.9 to 77.8) | 90.22 (25.8%) | 13 (x4.6) |
| per-class | 1.12 (0.82 to 1.45) | 46.5% (39.9 to 52.9) | 46.5% (39.9 to 52.7) | 28.87 (9.9%) | 68 (x2.6) |
| per-class without lazygit, starship, zed, hugo | 1.08 (0.77 to 1.43) | 46.1% (39.6 to 53.1) | 46.0% (39.6 to 53.0) | 31.05 (10.9%) | - |
| never | 0.00 (0.00 to 0.00) | 83.5% (78.0 to 88.6) | 83.5% (78.0 to 88.6) | - (100.0%) | 0 (x0.0) |

## Per-class minus fixed 30, paired (uniform, 1 a week)

| Split | Stale-answer rate | Stale claim-days | Checks per claim-month |
|---|---|---|---|
| test | 8.6% (2.4 to 14.5) | 8.5% (2.3 to 14.4) | 0.17 (-0.13 to 0.50) |
| dev | 10.5% (5.3 to 16.1) | 10.5% (5.3 to 15.9) | 0.05 (-0.23 to 0.35) |

Each column is per-class minus fixed 30 on the same claims (staleness in points), with its paired 95% interval over resampled projects (D12); above 0, per-class is staler or costs more. Added at the maintainer's request after the first run; not pre-registered.

## Every read at each question rate (test, uniform)

| Questions | Checks per claim-month | Stale claim-days | Days to detect (undetected) |
|---|---|---|---|
| 2 a month | 2.00 (1.99 to 2.01) | 33.2% (27.9 to 38.6) | 13.52 (4.3%) |
| 1 a week | 4.29 (4.27 to 4.30) | 20.6% (16.4 to 24.9) | 5.91 (2.0%) |
| 1 a day | 30.00 (30.00 to 30.00) | 0.0% (0.0 to 0.0) | 0.00 (0.0%) |

## Jitter, with minus without, paired (test, 1 a week)

| Scenario / policy | Peak per day: without | With | With minus without | Stale-answer rate | Stale claim-days |
|---|---|---|---|---|---|
| uniform / per-class (exploratory) | 68.2 | 68.4 | 0.20 (-5.60 to 5.80) | -0.0% (-0.3 to 0.2) | -0.0% (-0.2 to 0.2) |
| uniform / fixed 7 (exploratory) | 213.0 | 218.0 | 5.00 (-2.00 to 19.60) | 0.2% (0.1 to 0.4) | 0.2% (0.1 to 0.4) |
| uniform / fixed 30 (exploratory) | 57.4 | 60.0 | 2.60 (-2.40 to 8.20) | 0.0% (-0.2 to 0.3) | 0.0% (-0.2 to 0.2) |
| sessions / per-class (primary) | 87.8 | 68.4 | -19.40 (-23.00 to -7.40) | -0.0% (-0.2 to 0.2) | 0.0% (-0.2 to 0.2) |
| sessions / fixed 7 (exploratory) | 264.0 | 227.2 | -36.80 (-42.00 to -10.60) | 0.1% (-0.1 to 0.2) | 0.2% (0.0 to 0.4) |
| sessions / fixed 30 (exploratory) | 94.0 | 62.0 | -32.00 (-34.40 to -18.20) | 0.0% (-0.2 to 0.2) | -0.1% (-0.2 to 0.1) |

Primary comparison (D12), sessions / per-class: jitter helps.

## By label and by observed change rate (test, uniform, 1 a week)

| Group | Projects | Per-class: stale claim-days | Checks per claim-month | Fixed 30: stale claim-days | Checks per claim-month |
|---|---|---|---|---|---|
| fast | 11 | 26.3% (16.4 to 37.6) | 4.24 (4.24 to 4.25) | 57.3% (40.7 to 73.2) | 0.95 (0.95 to 0.96) |
| medium | 31 | 43.3% (35.4 to 51.3) | 0.95 (0.95 to 0.96) | 43.3% (35.4 to 51.3) | 0.95 (0.95 to 0.96) |
| slow | 28 | 57.6% (45.7 to 68.1) | 0.12 (0.12 to 0.12) | 24.9% (16.9 to 34.3) | 0.95 (0.95 to 0.96) |
| 0 changes a year | 3 | 0.0% (0.0 to 0.0) | 0.13 (0.13 to 0.13) | 0.0% (0.0 to 0.0) | 0.96 (0.95 to 0.96) |
| under 6 | 22 | 32.2% (23.1 to 41.2) | 0.80 (0.39 to 1.37) | 13.9% (10.7 to 17.3) | 0.95 (0.95 to 0.96) |
| 6 to 52 | 37 | 55.7% (47.7 to 63.5) | 1.04 (0.70 to 1.43) | 45.8% (40.6 to 50.9) | 0.95 (0.95 to 0.96) |
| over 52 | 8 | 62.5% (46.4 to 80.2) | 2.87 (1.57 to 3.98) | 85.9% (81.9 to 89.6) | 0.95 (0.94 to 0.96) |

## Dev split (not compared with test: dev claims live shorter)

Dev split, uniform scenario, questions 1 a week per claim; 1360 claims about 68 projects per seed. 95% intervals over resampled projects (D12). Days to detect counts only the changes found; the share left undetected follows it.

| Policy | Checks per claim-month | Stale-answer rate | Stale claim-days | Days to detect (undetected) | Peak per day (to mean) |
|---|---|---|---|---|---|
| oracle | 1.88 (1.30 to 2.56) | 0.0% (0.0 to 0.0) | 0.0% (0.0 to 0.0) | 0.00 (0.0%) | 170 (x4.1) |
| every read | 4.28 (4.26 to 4.30) | 0.0% (0.0 to 0.0) | 20.6% (16.4 to 24.7) | 5.82 (2.6%) | 209 (x2.2) |
| fixed 3 | 9.94 (9.94 to 9.95) | 5.8% (4.2 to 7.7) | 5.8% (4.1 to 7.6) | 1.00 (0.4%) | 469 (x2.1) |
| fixed 7 | 4.21 (4.21 to 4.22) | 14.3% (11.0 to 17.9) | 14.4% (11.0 to 18.0) | 3.02 (1.1%) | 210 (x2.2) |
| fixed 14 | 2.07 (2.06 to 2.07) | 24.4% (19.3 to 29.4) | 24.4% (19.3 to 29.3) | 6.53 (2.4%) | 112 (x2.4) |
| fixed 30 | 0.92 (0.92 to 0.92) | 38.3% (31.6 to 44.3) | 38.0% (31.3 to 44.1) | 14.59 (7.0%) | 55 (x2.7) |
| fixed 60 | 0.42 (0.42 to 0.42) | 51.5% (44.2 to 58.0) | 51.2% (43.7 to 57.8) | 29.64 (15.6%) | 30 (x3.2) |
| fixed 90 | 0.25 (0.25 to 0.25) | 58.6% (51.1 to 65.2) | 58.3% (50.8 to 64.9) | 44.96 (24.1%) | 21 (x3.7) |
| fixed 180 | 0.09 (0.08 to 0.09) | 69.1% (61.9 to 75.3) | 68.8% (61.6 to 75.1) | 89.67 (49.5%) | 11 (x5.8) |
| per-class | 0.97 (0.69 to 1.27) | 48.8% (42.0 to 55.6) | 48.6% (41.7 to 55.3) | 27.64 (18.7%) | 60 (x2.8) |
| never | 0.00 (0.00 to 0.00) | 75.8% (68.9 to 81.6) | 75.6% (68.9 to 81.5) | - (100.0%) | 0 (x0.0) |

## Claims in each results row (per seed, averaged over the seeds)

| Split / scenario / questions | Projects | Claims | Dropped (of 20 a project) |
|---|---|---|---|
| dev / uniform / 2 a month | 68 | 1360.0 | 0.0 |
| dev / uniform / 1 a week | 68 | 1360.0 | 0.0 |
| dev / uniform / 1 a day | 68 | 1360.0 | 0.0 |
| dev / sessions / 2 a month | 68 | 1356.0 | 4.0 |
| dev / sessions / 1 a week | 68 | 1356.0 | 4.0 |
| dev / sessions / 1 a day | 68 | 1356.0 | 4.0 |
| test / uniform / 2 a month | 70 | 1400.0 | 0.0 |
| test / uniform / 1 a week | 70 | 1400.0 | 0.0 |
| test / uniform / 1 a day | 70 | 1400.0 | 0.0 |
| test / sessions / 2 a month | 70 | 1400.0 | 0.0 |
| test / sessions / 1 a week | 70 | 1400.0 | 0.0 |
| test / sessions / 1 a day | 70 | 1400.0 | 0.0 |

Projects counts those with a claim in the split.

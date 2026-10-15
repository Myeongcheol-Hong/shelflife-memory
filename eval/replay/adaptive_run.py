"""Run M7's adaptive policy (D12) and write eval/results/<run-id>/.

    uv run python -m eval.replay.adaptive_run [--out eval/results]

Uniform scenario, 1 question a week, 5 seeds. Dev runs every grid point next to
per-class and the fixed-N curve, and the point is selected there: the lowest stale
claim-days among the points costing no more checks per claim-month than per-class,
ties to the cheaper. Test then runs that one point, its label-free variant
(exploratory), per-class and the curve. Nothing is chosen on test.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.replay import adaptive, run, score
from eval.replay.replay import FIXED, POLICIES, QUESTION_RATES, Counts, replay
from eval.replay.timelines import Timeline, load_all, load_projects

RATE = "1 a week"
CURVE = [f"fixed {n}" for n in FIXED]
COST = (*run.STALE, "checks per claim-month")


def evaluate(timelines: list[Timeline], labels: dict[str, str], seeds: list[int]) -> dict:
    """metrics.json: the selected point, then each split's comparisons, then the grid."""
    base = {name: POLICIES[name] for name in ("per-class", *CURVE)}
    grid = {adaptive.name(*point): adaptive.policy(*point) for point in adaptive.GRID}
    dev = _projects(timelines, labels, "dev", seeds, base | grid)
    chosen = select(dev, list(grid))
    point = adaptive.GRID[list(grid).index(chosen)]
    free = adaptive.name(*point, label_free=True)
    more = {chosen: grid[chosen], free: adaptive.policy(*point, label_free=True)}
    test = _projects(timelines, labels, "test", seeds, base | more)
    out: dict[str, Any] = {"selected": chosen, "per-class dev cost": _cost(dev["per-class"])}
    for split, projects in (("test", test), ("dev", dev)):
        shown = (chosen, "per-class", "fixed 30", *([free] if split == "test" else []))
        out[split] = {
            "policies": {name: run._metrics(projects[name]) for name in shown},
            "selected minus per-class": run._paired(projects[chosen], projects["per-class"], COST),
            "selected minus fixed 30": run._paired(projects[chosen], projects["fixed 30"], COST),
            "on the fixed-N curve": place(projects, chosen),
        }
    out["test"]["label-free minus selected"] = run._paired(test[free], test[chosen], COST)
    out["dev grid"] = {
        name: {m: score.value(m, score.total(dev[name])) for m in COST}
        for name in (*grid, "per-class", *CURVE)
    }
    return out


def _projects(timelines, labels, split, seeds, policies) -> dict[str, dict[str, Counts]]:
    rows = replay(timelines, labels, split, seeds, QUESTION_RATES[RATE], policies)
    return {name: score.per_project(rows, name) for name in policies}


def select(dev: dict[str, dict[str, Counts]], names: list[str]) -> str:
    """D12's rule on dev: the lowest stale claim-days among the points costing no more
    checks per claim-month than per-class, ties to the cheaper, then to the grid order."""
    cap = _cost(dev["per-class"])
    fits = [name for name in names if _cost(dev[name]) <= cap]
    if not fits:
        raise ValueError(f"no grid point costs at most per-class's {cap:.3f} on dev")
    stale = {name: score.value("stale claim-days", score.total(dev[name])) for name in fits}
    return min(fits, key=lambda name: (stale[name], _cost(dev[name])))


def _cost(projects: dict[str, Counts]) -> float:
    return score.value("checks per claim-month", score.total(projects))


def place(projects: dict[str, dict[str, Counts]], name: str) -> dict:
    """Where a policy sits against the fixed-N curve (proposed, D12): the curve's stale
    claim-days at the policy's checks per claim-month, linear between the two fixed N
    whose costs bracket it, and the policy minus that, with its 95% interval over the
    same project resamples as every other interval. Below 0 is below the curve."""
    units = sorted(projects[name])
    pairs = {
        n: [(30 * c.checks, c.stale_days, c.days) for c in (projects[n][u] for u in units)]
        for n in (name, *CURVE)
    }
    found = _gap(pairs, name, range(len(units)))
    gaps = [g[0] for pick in score._resamples(len(units)) if (g := _gap(pairs, name, pick))]
    if found is None:
        return {"value": None, "between": None, "ci": None}
    return {"value": found[0], "between": found[1], "ci": score.percentiles(gaps)}


def _gap(pairs: dict[str, list[tuple]], name: str, pick) -> tuple[float, list[str]] | None:
    """The policy's stale claim-days minus the curve's at its cost, over the projects in
    `pick`, with the two fixed N around it; None outside the curve."""
    sums = {n: [sum(rows[i][k] for i in pick) for k in range(3)] for n, rows in pairs.items()}
    cost = {n: s[0] / s[2] for n, s in sums.items()}
    stale = {n: s[1] / s[2] for n, s in sums.items()}
    curve = sorted((cost[n], stale[n], n) for n in CURVE)
    for (x0, y0, n0), (x1, y1, n1) in zip(curve, curve[1:], strict=False):
        if x0 <= cost[name] <= x1 and x1 > x0:
            line = y0 + (y1 - y0) * (cost[name] - x0) / (x1 - x0)
            return stale[name] - line, [n0, n1]
    return None  # cheaper than the longest fixed N or dearer than the shortest


def table(metrics: dict, run_id: str) -> str:
    """table.md: the selected point on test, its comparisons in both splits, the grid."""
    chosen = metrics["selected"]
    cap = metrics["per-class dev cost"]
    lines = [f"# 6.1 adaptive policy (M7), run {run_id}", ""]
    lines += [f"Selected on dev (D12): {chosen}, the lowest stale claim-days among the grid"]
    lines += [f"points costing at most per-class's {cap:.2f} checks per claim-month on dev."]
    lines += ["Uniform scenario, 1 question a week, 5 seeds, 95% intervals over projects.", ""]
    for split in ("test", "dev"):
        found = metrics[split]
        lines += [f"## {split.capitalize()}", "", *_policies(found["policies"]), ""]
        rows = [[key, *_differences(found[key])] for key in found if " minus " in key]
        header = ["Paired, on the same claims", "Stale-answer rate", "Stale claim-days"]
        lines += [*run._table([*header, "Checks per claim-month"], rows), ""]
        lines += [_curve_line(chosen, found["on the fixed-N curve"]), ""]
    lines += ["Label-free runs are exploratory (D12); staleness differences are in points.", ""]
    lines += ["## Dev grid (exploratory)", "", *_grid(metrics["dev grid"], chosen, cap)]
    return "\n".join(lines) + "\n"


def _policies(policies: dict) -> list[str]:
    columns = run.COLUMNS[:4]
    header = ["Policy", "Checks per claim-month", "Stale-answer rate", "Stale claim-days"]
    rows = [[name, *(f(m) for f in columns)] for name, m in policies.items()]
    return run._table([*header, "Days to detect (undetected)"], rows)


def _differences(found: dict) -> list[str]:
    return [*(run._pct(found[m]) for m in run.STALE), run._num(found["checks per claim-month"])]


def _curve_line(name: str, found: dict) -> str:
    if found["value"] is None:
        return f"On the fixed-N curve: {name} costs less than fixed 180 or more than fixed 3."
    (lo, hi), (a, b) = found["ci"], found["between"]
    return (
        f"On the fixed-N curve (proposed, D12): between {a} and {b}, its stale claim-days"
        f" minus the curve's at the same cost is {100 * found['value']:.1f} points"
        f" ({100 * lo:.1f} to {100 * hi:.1f}); below 0 is below the curve."
    )


def _grid(grid: dict, chosen: str, cap: float) -> list[str]:
    rows = []
    for name, m in grid.items():
        cost, stale = m["checks per claim-month"], m["stale claim-days"]
        mark = "within per-class's cost" if cost <= cap else ""
        mark = "selected" if name == chosen else "" if name in ("per-class", *CURVE) else mark
        rows.append([name, f"{cost:.2f}", f"{100 * stale:.1f}%", mark])
    return run._table(["Policy", "Checks per claim-month", "Stale claim-days", ""], rows)


def main(
    argv: list[str] | None = None, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> int:
    parser = argparse.ArgumentParser(prog="adaptive_run", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("eval/data/timelines"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    args = parser.parse_args(argv)
    labels = {p.name: p.volatility for p in load_projects(args.data / "projects.toml")}
    cfg = run.config(args.data, now())
    cfg |= {"run": cfg["run"] + "-adaptive", "decision": "D12 (M7)", "question rate": RATE}
    cfg |= {"grid": adaptive.GRID, "label-free days": adaptive.LABEL_FREE_DAYS}
    cfg["policies"] = ["per-class", *CURVE, *(adaptive.name(*point) for point in adaptive.GRID)]
    folder = args.out / cfg["run"]
    if folder.exists():
        print(f"error: {folder} exists; a run never overwrites another", file=sys.stderr)
        return 1
    metrics = evaluate(load_all(args.data), labels, cfg["seeds"])
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps(cfg, indent=1) + "\n")
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    (folder / "table.md").write_text(table(metrics, cfg["run"]))
    print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

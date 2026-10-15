"""Run M7's adaptive policy (D12) and write eval/results/<run-id>/.

    uv run python -m eval.replay.adaptive_run [--out eval/results] [--dev-costs]

Uniform scenario, 1 question a week, 5 seeds. Dev runs every grid point next to
per-class and the fixed-N curve, and the point is selected there: the lowest stale
claim-days among the points costing no more checks per claim-month than per-class,
ties to the cheaper. Test then runs that one point, its label-free variant
(exploratory), per-class and the curve. Nothing is chosen on test. --dev-costs only
prints each grid point's checks per claim-month on dev, with no staleness (D12).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.replay import adaptive, run, score
from eval.replay.replay import (
    FIXED,
    POLICIES,
    QUESTION_RATES,
    Counts,
    Policy,
    claims,
    replay,
    stream,
    truth,
)
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


def dev_costs(timelines, labels, seeds, policies: dict[str, Policy]) -> dict[str, float]:
    """Each policy's checks per claim-month on dev from its claims and checks alone. It
    never calls outcome(), so no staleness is computed: the maintainer's pre-run cost
    check (D12). The claims and streams are replay()'s, and the ratio is select()'s."""
    checks: Counter[str] = Counter()
    days = 0
    for t in timelines:
        tr = truth(t, "dev")
        for seed in seeds:
            cs = claims(t.project, labels[t.project], tr, "dev", seed, QUESTION_RATES[RATE])
            days += sum((c.end - c.created).days for c in cs)
            for name, policy in policies.items():
                for i, c in enumerate(cs):
                    checks[name] += len(policy(c, tr, stream(seed, "dev", t.project, i, name)))
    return {name: 30 * checks[name] / days for name in policies}


def cost_table(found: dict[str, float]) -> str:
    """dev_costs() of per-class and the grid: a row per p, a column per α and `max`; *
    marks a point at or below per-class's cost."""
    cap = found["per-class"]
    columns = sorted({(a, m) for _, a, m in adaptive.GRID})
    rows = [
        [f"{p:g}", *(_mark(found[adaptive.name(p, a, m)], cap) for a, m in columns)]
        for p in sorted({p for p, _, _ in adaptive.GRID})
    ]
    header = ["p", *(f"α={a:g} max={m}" for a, m in columns)]
    lines = [f"Checks per claim-month on dev; per-class {cap:.3f}.", ""]
    return "\n".join([*lines, *run._table(header, rows)]) + "\n"


def _mark(cost: float, cap: float) -> str:
    return f"{cost:.3f}" + (" *" if cost <= cap else "")


def place(projects: dict[str, dict[str, Counts]], name: str) -> dict:
    """Where a policy sits against the fixed-N curve (proposed, D12): the curve's stale
    claim-days at the policy's checks per claim-month, linear between the two fixed N
    whose costs bracket it, and the policy minus that, with its 95% interval over the
    same project resamples as every other interval. Below 0 is below the curve. If the
    policy falls outside the curve in any resample, no interval is given and "resamples
    outside" counts them."""
    units = sorted(projects[name])
    rows = {n: [projects[n][u] for u in units] for n in (name, *CURVE)}
    found = _gap(rows, name, range(len(units)))
    if found is None:
        return {"value": None, "between": None, "ci": None, "resamples outside": None}
    picks = score._resamples(len(units))
    gaps = [g[0] for pick in picks if (g := _gap(rows, name, pick))]
    outside = len(picks) - len(gaps)
    ci = None if outside else score.percentiles(gaps)
    return {"value": found[0], "between": found[1], "ci": ci, "resamples outside": outside}


def _gap(rows: dict[str, list[Counts]], name: str, pick) -> tuple[float, list[str]] | None:
    """The policy's stale claim-days minus the curve's at its cost, over the projects in
    `pick`, with the two fixed N around it; None outside the curve."""
    sums = {n: sum((counts[i] for i in pick), Counts()) for n, counts in rows.items()}
    cost = {n: score.value("checks per claim-month", s) for n, s in sums.items()}
    stale = {n: score.value("stale claim-days", s) for n, s in sums.items()}
    curve = sorted((cost[n], stale[n], n) for n in CURVE)
    for (x0, y0, n0), (x1, y1, n1) in zip(curve, curve[1:], strict=False):
        if x0 <= cost[name] <= x1 and x1 > x0:
            line = y0 + (y1 - y0) * (cost[name] - x0) / (x1 - x0)
            return stale[name] - line, [n0, n1]
    return None  # cheaper than the longest fixed N or dearer than the shortest


def table(metrics: dict, run_id: str, seeds: int) -> str:
    """table.md: the selected point on test, its comparisons in both splits, the grid."""
    chosen = metrics["selected"]
    cap = metrics["per-class dev cost"]
    lines = [f"# 6.1 adaptive policy (M7), run {run_id}", ""]
    lines += [f"Selected on dev (D12): {chosen}, the lowest stale claim-days among the grid"]
    lines += [f"points costing at most per-class's {cap:.2f} checks per claim-month on dev."]
    lines += [f"Uniform scenario, {RATE}, {seeds} seed(s), 95% intervals over projects.", ""]
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
    a, b = found["between"]
    if found["ci"] is None:
        ci = f"no interval: outside the curve in {found['resamples outside']} resamples"
    else:
        ci = f"{100 * found['ci'][0]:.1f} to {100 * found['ci'][1]:.1f}"
    return (
        f"On the fixed-N curve (proposed, D12): between {a} and {b}, its stale claim-days"
        f" minus the curve's at the same cost is {100 * found['value']:.1f} points ({ci});"
        " below 0 is below the curve."
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
    parser.add_argument("--dev-costs", action="store_true", help="print dev costs; write nothing")
    args = parser.parse_args(argv)
    labels = {p.name: p.volatility for p in load_projects(args.data / "projects.toml")}
    if args.dev_costs:
        grid = {adaptive.name(*point): adaptive.policy(*point) for point in adaptive.GRID}
        policies = {"per-class": POLICIES["per-class"]} | grid
        print(cost_table(dev_costs(load_all(args.data), labels, run.SEEDS, policies)), end="")
        return 0
    cfg = run.config(args.data, now())
    del cfg["question rates per claim-day"], cfg["session size"]  # M6's other scenarios
    cfg |= {"run": cfg["run"] + "-adaptive", "decision": "D12 (M7)", "scenario": "uniform"}
    cfg |= {"question rate per claim-day": {RATE: QUESTION_RATES[RATE]}, "grid": adaptive.GRID}
    cfg["label-free days"] = adaptive.LABEL_FREE_DAYS
    grid = [adaptive.name(*point) for point in adaptive.GRID]
    cfg["policies"] = ["per-class", *CURVE, *grid, "the selected point, label-free (test only)"]
    folder = args.out / cfg["run"]
    if folder.exists():
        print(f"error: {folder} exists; a run never overwrites another", file=sys.stderr)
        return 1
    metrics = evaluate(load_all(args.data), labels, cfg["seeds"])
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps(cfg, indent=1) + "\n")
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    (folder / "table.md").write_text(table(metrics, cfg["run"], len(cfg["seeds"])))
    print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

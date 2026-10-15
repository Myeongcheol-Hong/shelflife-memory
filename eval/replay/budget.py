"""The budget-aware allocation (D12, asked for after M7b's results): each claim's next
check from its estimated change rate under one budget multiplier μ, in days (Cho &
Garcia-Molina 2003).

    uv run python -m eval.replay.budget --dev-costs   # the grid's dev costs and μ only
    uv run python -m eval.replay.budget [--out eval/results]  # the run, once MU is set

With Poisson changes at rate λ, a claim checked every 1 / f days is fresh a share
F(λ, f) = (f / λ)(1 - e^(-λ / f)) of the time. Maximizing Σ F under one check budget
gives g(x) = 1 - (1 + x) e^(-x) = μλ for every checked claim, with x = λ / f, so it waits
x / λ days; with μλ ≥ 1 the optimum is not to check, and the claim waits the cap. λ is
M7b's per-claim estimate with its selected point's prior; only the wait changes.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from eval.replay import adaptive, adaptive_run, run
from eval.replay.replay import POLICIES, Policy
from eval.replay.timelines import load_all, load_projects

ALPHA, CAP = 2, 180  # M7b's selected point's prior strength and longest wait (D12)
GRID = [2**k for k in range(7)]  # μ in days; from 53.7 every wait is the cap: fixed 180
HALVINGS = 20  # of log μ inside the grid's bracket
# Set on dev by cost alone (--dev-costs at 7422cb5) and recorded in D12 before any run.
MU: float | None = 4.845574065445341


def name(mu: float) -> str:
    return f"budget-aware μ={mu:.4g}"


def g(x: float) -> float:
    return -math.expm1(-x) - x * math.exp(-x)  # 1 - (1 + x) e^(-x), accurate for small x


def wait(mu: float, lam: float) -> int:
    """x / λ rounded half up, from 1 to CAP, exactly: the smallest whole d below CAP with
    g(λ(d + 0.5)) > μλ (g rises), else CAP, which covers μλ ≥ 1."""
    days = range(1, CAP)
    return days.start + bisect.bisect_right(days, mu * lam, key=lambda d: g(lam * (d + 0.5)))


def policy(mu: float) -> Policy:
    return adaptive.learning(ALPHA, lambda lam: wait(mu, lam))


def search(cost: Callable[[float], float], target: float) -> tuple[float, dict]:
    """μ by D12's rule from dev costs alone: the grid's costs, which must not rise, then
    HALVINGS halvings of log μ in the doubling bracket where the cost crosses `target`; μ
    is the bracket's end whose cost is at most `target`. ValueError, never another rule,
    if a cost rises or `target` lies outside the grid's costs."""
    grid = {mu: cost(mu) for mu in GRID}
    costs = list(grid.values())
    if any(b > a for a, b in zip(costs, costs[1:], strict=False)):
        raise ValueError(f"the dev cost rises with μ: {grid}")
    if not costs[-1] <= target < costs[0]:
        raise ValueError(f"{target:.4f} lies outside the grid's costs {grid}")
    k = next(i for i, c in enumerate(costs) if c <= target)
    lo, hi, steps = math.log2(GRID[k - 1]), math.log2(GRID[k]), {}
    for _ in range(HALVINGS):
        mid = (lo + hi) / 2
        steps[2**mid] = cost(2**mid)
        lo, hi = (lo, mid) if steps[2**mid] <= target else (mid, hi)
    return 2**hi, {"grid": grid, "halvings": steps}


def dev_costs(data: Path) -> dict:
    """The grid's dev costs, the search and μ, with no staleness computed (D12)."""
    labels = {p.name: p.volatility for p in load_projects(data / "projects.toml")}
    timelines = load_all(data)

    def costs(policies: dict[str, Policy]) -> dict[str, float]:
        return adaptive_run.dev_costs(timelines, labels, run.SEEDS, policies)

    base = costs({n: POLICIES[n] for n in ("fixed 30", "fixed 180")})
    if costs({name(GRID[-1]): policy(GRID[-1])})[name(GRID[-1])] != base["fixed 180"]:
        raise ValueError(f"μ = {GRID[-1]} should be fixed 180")  # every wait at the cap
    mu, found = search(lambda m: costs({name(m): policy(m)})[name(m)], base["fixed 30"])
    return {"fixed 30": base["fixed 30"], "fixed 180": base["fixed 180"], "μ": mu} | found


def cost_table(found: dict) -> str:
    """--dev-costs' report: the grid, the halvings and μ, costs only."""
    lines = ["Dev checks per claim-month, uniform scenario, 1 question a week (D12):"]
    lines += [f"fixed 30 {found['fixed 30']:.4f}, fixed 180 {found['fixed 180']:.4f}.", ""]
    rows = [[f"{mu:g}", f"{c:.4f}"] for mu, c in found["grid"].items()]
    rows += [[f"{mu:.6g} (halving)", f"{c:.4f}"] for mu, c in found["halvings"].items()]
    lines += [*run._table(["μ (days)", "Checks per claim-month"], rows), ""]
    lines += [f"μ = {found['μ']!r} days: the bracket's end at most fixed 30's cost."]
    return "\n".join(lines) + "\n"


def evaluate(timelines, labels: dict, seeds: list[int], mu: float) -> dict:
    """Per split: the policy and fixed 30, the policy minus fixed 30 (paired), and its
    place on the fixed-N curve."""
    ours = name(mu)
    policies = {ours: policy(mu)} | {n: POLICIES[n] for n in adaptive_run.CURVE}
    out = {}
    for split in ("test", "dev"):
        projects = adaptive_run._projects(timelines, labels, split, seeds, policies)
        out[split] = {
            "policies": {n: run._metrics(projects[n]) for n in (ours, "fixed 30")},
            "minus fixed 30": run._paired(projects[ours], projects["fixed 30"], adaptive_run.COST),
            "on the fixed-N curve": adaptive_run.place(projects, ours),
        }
    return out


def table(metrics: dict, cfg: dict) -> str:
    """table.md: test, then dev, where μ was set."""
    ours = name(cfg["μ"])
    lines = [f"# 6.1 budget-aware allocation (M7), run {cfg['run']}", ""]
    lines += [
        "Asked for by the maintainer after M7b's results, so not pre-registered; the rule and"
        f" μ = {cfg['μ']:.6g} days were fixed in D12 before this run. μ was set on dev by cost"
        " alone, at most fixed 30's dev cost.",
        "",
    ]
    for split in ("test", "dev"):
        part = metrics[split]
        where = f"uniform, {adaptive_run.RATE}, seeds: {len(cfg['seeds'])}"
        lines += [f"## {split.capitalize()} ({where}, 95% intervals over projects)", ""]
        lines += [*adaptive_run._policies(part["policies"]), ""]
        row = [f"{ours} minus fixed 30", *adaptive_run._differences(part["minus fixed 30"])]
        header = ["Paired, on the same claims", "Stale-answer rate", "Stale claim-days"]
        lines += [*run._table([*header, "Checks per claim-month"], [row]), ""]
        lines += [adaptive_run._curve_line(ours, part["on the fixed-N curve"]), ""]
    return "\n".join(lines[:-1]) + "\n"


def main(
    argv: list[str] | None = None, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> int:
    parser = argparse.ArgumentParser(prog="budget", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("eval/data/timelines"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    parser.add_argument("--dev-costs", action="store_true", help="costs and μ; write nothing")
    args = parser.parse_args(argv)
    if args.dev_costs:
        try:
            found = dev_costs(args.data)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print(cost_table(found), end="")
        return 0
    if MU is None:
        print("error: MU is not set: run --dev-costs and record μ in D12 first", file=sys.stderr)
        return 1
    labels = {p.name: p.volatility for p in load_projects(args.data / "projects.toml")}
    cfg = run.config(args.data, now())
    del cfg["question rates per claim-day"], cfg["session size"]  # M6's other scenarios
    cfg |= {"run": cfg["run"] + "-budget", "decision": "D12 (M7, after M7b's results)"}
    cfg |= {"scenario": "uniform", "question rate": adaptive_run.RATE, "μ": MU}
    cfg |= {"α": ALPHA, "max": CAP, "policies": [name(MU), *adaptive_run.CURVE]}
    folder = args.out / cfg["run"]
    if folder.exists():
        print(f"error: {folder} exists; a run never overwrites another", file=sys.stderr)
        return 1
    metrics = evaluate(load_all(args.data), labels, cfg["seeds"], MU)
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps(cfg, indent=1) + "\n")
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    (folder / "table.md").write_text(table(metrics, cfg))
    print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

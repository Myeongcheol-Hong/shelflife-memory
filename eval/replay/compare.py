"""M7e (D12, asked for after M7's results): three more scheduled policies, and every M7
policy on one run against the dense fixed-N curve, with the change-rate breakdown.

    uv run python -m eval.replay.compare --dev-costs   # costs and both μ; no staleness
    uv run python -m eval.replay.compare --dev-select  # the tuned per-class, on dev
    uv run python -m eval.replay.compare [--out eval/results]  # the run, once all are set

Per-class tuned checks each label at its own interval from a 140-point dev grid. The
count-aware rate sees how many times the latest changed since the last check, and the
true-rate bound knows each project's rate in the split; both wait by M7d's budget rule.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import sys
from bisect import bisect_right
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from eval.replay import adaptive, adaptive_run, budget, run, score
from eval.replay.adaptive_run import COST, RATE, _projects
from eval.replay.llm_labels import MISSING
from eval.replay.replay import (
    FIXED,
    POLICIES,
    QUESTION_RATES,
    SPLITS,
    Claim,
    Policy,
    Truth,
    changes_per_year,
    interval,
)
from eval.replay.timelines import LABELS, load_all, load_projects
from shelflife.models import Volatility
from shelflife.scheduler import DEFAULT_INTERVAL_DAYS

# Widened at #37's review so that 30/30/30 is in it (D12).
GRID = list(itertools.product((3, 5, 7, 10, 14, 21, 30), (14, 21, 30, 45), (30, 45, 60, 90, 120)))
DENSE = sorted({*FIXED, 20, 25, 40, 45})
CURVE = [f"fixed {n}" for n in DENSE]
CURVE_POLICIES = {name: interval(n) for name, n in zip(CURVE, DENSE, strict=True)}
CLAUDE = Path("eval/results/f7b6974-llm-labels-claude-opus-5-5-bf48e181/metrics.json")
APART = ("every read", "oracle")  # not scheduled: reported apart (D12)
RUN_FILES = ("metrics.json", "config.json")
# Set on dev and recorded in D12 before the test run.
TUNED: tuple[int, int, int] | None = (30, 30, 30)  # selected again on the widened grid
MU_COUNT: float | None = 4.92012052554465
MU_TRUE: float | None = 5.911261617681446


def tuned_name(fast: int, medium: int, slow: int) -> str:
    return f"per-class tuned {fast}/{medium}/{slow}"


def per_class(fast: int, medium: int, slow: int) -> Policy:
    """A check every interval of the claim's label, from the creation, without jitter."""
    by = {label: interval(n) for label, n in zip(LABELS, (fast, medium, slow), strict=True)}
    return lambda claim, truth, rng: by[claim.label](claim, truth, rng)


def relabeled(labels: dict[str, str]) -> Policy:
    """Per-class with other labels for the same claims (M7c's labels; D14)."""

    def checks(claim: Claim, truth: Truth, rng) -> list[date]:
        claim = dataclasses.replace(claim, label=labels[claim.project])
        return POLICIES["per-class"](claim, truth, rng)

    return checks


def count_aware(mu: float) -> Policy:
    """λ = (α - 1 + changes seen) / (β + days observed), each check counting the days the
    latest changed since the last one; the wait is M7d's (budget.wait)."""

    def checks(claim: Claim, truth: Truth, rng) -> list[date]:
        beta = budget.ALPHA * DEFAULT_INTERVAL_DAYS[Volatility(claim.label)]
        seen = observed = 0
        out, last = [], claim.created
        while True:
            lam = (budget.ALPHA - 1 + seen) / (beta + observed)
            nxt = last + timedelta(budget.wait(mu, lam))
            if nxt > claim.end:
                return out
            seen += bisect_right(truth.days, nxt) - bisect_right(truth.days, last)
            observed += (nxt - last).days
            out.append(nxt)
            last = nxt

    return checks


def true_rate(mu: float) -> Policy:
    """The budget wait with the project's own rate in the split, known in advance: a fixed
    interval per project (exploratory, D12)."""

    def checks(claim: Claim, truth: Truth, rng) -> list[date]:
        split = next(s for s, (_, end) in SPLITS.items() if end == claim.end)
        return interval(budget.wait(mu, true_lambda(truth, split)))(claim, truth, rng)

    return checks


def true_lambda(truth: Truth, split: str) -> float:
    """Changes a day: the change-rate breakdown's count over the split (D12)."""
    return changes_per_year(truth, split) / 365


def dev_costs(data: Path) -> dict:
    """The grid's dev costs, and μ for both budget policies by M7d's search, with no
    staleness computed (D12)."""
    grid = {tuned_name(*p): per_class(*p) for p in GRID}
    found = {"grid": adaptive_run.dev_costs(load_all(data), _labels(data), run.SEEDS, grid)}
    for key, make in (("count-aware", count_aware), ("true-rate", true_rate)):
        found[key] = budget.dev_costs(data, make)
    return found | {"fixed 30": found["count-aware"]["fixed 30"]}


def dev_select(data: Path) -> tuple[str, dict]:
    """The tuned per-class: D12's rule on dev, with fixed 30's dev cost as the cap."""
    grid = {tuned_name(*p): per_class(*p) for p in GRID}
    base = {"fixed 30": POLICIES["fixed 30"]}
    dev = _projects(load_all(data), _labels(data), "dev", run.SEEDS, grid | base)
    return adaptive_run.select(dev, list(grid), "fixed 30"), _values(dev, grid)


def scheduled(claude: dict[str, str]) -> dict[str, Policy]:
    assert TUNED and MU_COUNT and MU_TRUE
    return {
        "per-class": POLICIES["per-class"],
        tuned_name(*TUNED): per_class(*TUNED),
        "per-class, Claude's labels": relabeled(claude),
        adaptive.name(0.7, 2, 180): adaptive.policy(0.7, 2, 180),  # M7b's selected point
        budget.name(budget.MU): budget.policy(budget.MU),
        f"count-aware μ={MU_COUNT:.4g}": count_aware(MU_COUNT),
        f"true-rate μ={MU_TRUE:.4g} (exploratory)": true_rate(MU_TRUE),
    }


def evaluate(timelines, labels, claude, seeds) -> dict:
    """Per split, dev first: every policy's metrics and breakdown; for the scheduled ones,
    minus fixed 30 and the place on the dense curve. Dev also shows the tuned per-class
    grid, and stops the run unless it selects TUNED and every μ costs at most fixed 30."""
    ours = scheduled(claude)
    policies = CURVE_POLICIES | ours | {n: POLICIES[n] for n in APART}
    out: dict = {}
    for split in ("dev", "test"):
        grid = {tuned_name(*p): per_class(*p) for p in GRID} if split == "dev" else {}
        projects = _projects(timelines, labels, split, seeds, policies | grid)
        if grid:
            if (chosen := adaptive_run.select(projects, list(grid), "fixed 30")) != (
                tuned := tuned_name(*TUNED)
            ):
                raise ValueError(f"dev selects {chosen}, not the recorded {tuned}")
            cap = adaptive_run._cost(projects["fixed 30"]) * (1 + 1e-9)  # rounding only
            if over := [n for n in ours if " μ=" in n and adaptive_run._cost(projects[n]) > cap]:
                raise ValueError(f"{over} cost more than fixed 30 on dev")
        groups = run._groups(timelines, labels, split)
        places = {n: adaptive_run.place(projects, n, CURVE) for n in ours}
        out[split] = {
            "policies": {n: _with_groups(projects[n], groups) for n in policies},
            "minus fixed 30": {
                n: run._paired(projects[n], projects["fixed 30"], COST) for n in ours
            },
            "tuned minus per-class": run._paired(
                projects[tuned_name(*TUNED)], projects["per-class"], COST
            ),
            "on the dense curve": places,
            "below the curve, Bonferroni": bonferroni(projects, places),
        } | ({"grid": _values(projects, grid)} if grid else {})
    return {"test": out["test"], "dev": out["dev"]}


def bonferroni(projects: dict, places: dict) -> dict:
    """For each policy whose 95% place interval lies below 0, its interval under Bonferroni
    over the scheduled policies, `places` (D12, #37's review)."""
    alpha = 0.05 / len(places)
    below = [n for n, p in places.items() if p["ci"] and p["ci"][1] < 0]
    found = {n: adaptive_run.place(projects, n, CURVE, alpha)["ci"] for n in below}
    return {"policies": len(places), "level": 1 - alpha, "below 0 at 95%": found}


def _values(projects: dict, names) -> dict:
    return {n: {m: score.value(m, score.total(projects[n])) for m in COST} for n in names}


def _with_groups(projects: dict, groups: dict[str, set[str]]) -> dict:
    found = run._metrics(projects)
    found["buckets"] = {
        b: run._metrics({p: c for p, c in projects.items() if p in groups[b]}) for b in run.BUCKETS
    }
    return found


def table(metrics: dict, cfg: dict) -> str:
    lines = [f"# 6.1 every policy on the dense curve (M7e), run {cfg['run']}", ""]
    lines += [
        "M7e was asked for by the maintainer after M7's results, so it is not pre-registered;"
        " its rules, the tuned intervals and both μ were fixed in D12 before this run, on dev"
        f" only. Uniform scenario, {RATE}, seeds: {len(cfg['seeds'])}, 95% intervals over"
        " projects. The headline compares scheduled policies; every read (0% stale answers by"
        " construction) and the oracle are apart. The true-rate bound knows the future and is"
        " exploratory.",
        "",
        f"{len(cfg['scheduled'])} scheduled policies, each read on its own at 95% with no"
        " correction for multiplicity; four of them, budget-aware (M7d) and M7e's three, were"
        " added after results and are not pre-registered (D12).",
        "",
    ]
    lines += _uniform(cfg["tuned"])
    for split in ("test", "dev"):
        part, found = metrics[split], metrics[split]["policies"]
        rows = [
            [f"{n} minus fixed 30", *adaptive_run._differences(v)]
            for n, v in part["minus fixed 30"].items()
        ]
        rows.append(
            ["tuned minus per-class", *adaptive_run._differences(part["tuned minus per-class"])]
        )
        header = ["Paired, on the same claims", "Stale-answer rate", "Stale claim-days"]
        paired = run._table([*header, "Checks per claim-month"], rows)
        curve = [
            f"- {n}: {adaptive_run._curve_line(n, v)}"
            for n, v in part["on the dense curve"].items()
        ]
        curve += _bonferroni_lines(part)
        ours = [*part["minus fixed 30"], "fixed 30"]
        sections = {
            "Scheduled policies": [*_rows(found, ours), "", *paired, "", *curve],
            "Apart: not scheduled": _rows(found, APART),
            "The dense fixed-N curve": _rows(found, CURVE),
            "By observed change rate: stale claim-days (checks per claim-month)": _buckets(found),
        }
        if "grid" in part:
            cap = found["fixed 30"]["checks per claim-month"]["value"]
            sections["The tuned per-class grid (exploratory)"] = _grid(part["grid"], cfg, cap)
        title = "Test" if split == "test" else "Dev, where the tuned per-class and both μ were set"
        lines += [f"## {title}", ""]
        for head, body in sections.items():
            lines += [f"### {head}", "", *body, ""]
    return "\n".join(lines[:-1]) + "\n"


def _bonferroni_lines(part: dict) -> list[str]:
    report = part["below the curve, Bonferroni"]
    k, level = report["policies"], f"{100 * report['level']:.2f}%"
    if not (found := report["below 0 at 95%"]):
        return ["", f"None of the {k} scheduled policies' 95% intervals lies below the curve."]
    out = [""]
    for n, (lo, hi) in found.items():
        diff = part["minus fixed 30"][n]
        out.append(
            f"- {n} lies below the curve at 95%. Under Bonferroni over the {k} scheduled"
            f" policies ({level} each): {100 * lo:.1f} to {100 * hi:.1f} points,"
            f" {'still below 0' if hi < 0 else 'not below 0'}. Minus fixed 30: stale claim-days"
            f" {run._pct(diff['stale claim-days'])}, checks per claim-month"
            f" {run._num(diff['checks per claim-month'])}."
        )
    return out


def _uniform(tuned) -> list[str]:
    """A sentence when the dev selection chose one interval for every label."""
    if len(set(tuned)) > 1:
        return []
    n = tuned[0]
    return [f"The tuned per-class checks every {n} days whatever the label: it is fixed {n}.", ""]


def _rows(found: dict, names) -> list[str]:
    return adaptive_run._policies({n: found[n] for n in names})


def _buckets(found: dict) -> list[str]:
    first = next(iter(found.values()))["buckets"]
    header = ["Policy", *(f"{b} ({first[b]['projects']} projects)" for b in run.BUCKETS)]
    cell = "{} ({})".format
    rows = [
        [
            n,
            *(
                cell(
                    run._pct(b["stale claim-days"]), run._num(b["checks per claim-month"], ci=False)
                )
                for b in m["buckets"].values()
            ),
        ]
        for n, m in found.items()
    ]
    return run._table(header, rows)


def _grid(grid: dict, cfg: dict, cap: float) -> list[str]:
    chosen, header = tuned_name(*cfg["tuned"]), ["Policy", "Checks per claim-month"]
    rows = [
        [n, f"{m['checks per claim-month']:.3f}", f"{100 * m['stale claim-days']:.1f}%"]
        + ["selected" if n == chosen else "within fixed 30's cost" if m[COST[2]] <= cap else ""]
        for n, m in grid.items()
    ]
    return run._table([*header, "Stale claim-days", ""], rows)


def _labels(data: Path) -> dict[str, str]:
    return {p.name: p.volatility for p in load_projects(data / "projects.toml")}


def main(
    argv: list[str] | None = None, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> int:
    parser = argparse.ArgumentParser(prog="compare", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("eval/data/timelines"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    parser.add_argument("--claude-labels", type=Path, default=CLAUDE, help="M7c's metrics.json")
    parser.add_argument("--dev-costs", action="store_true", help="costs and μ; no staleness")
    parser.add_argument("--dev-select", action="store_true", help="the tuned per-class on dev")
    parser.add_argument("--table", type=Path, help="write a run's table.md again; no replay")
    args = parser.parse_args(argv)
    if args.table:  # from the run's own metrics.json and config.json
        metrics, cfg = (json.loads((args.table / f).read_text()) for f in RUN_FILES)
        (args.table / "table.md").write_text(table(metrics, cfg))
        return 0
    try:
        if args.dev_costs:
            print(json.dumps(dev_costs(args.data), indent=1))
            return 0
        if args.dev_select:
            chosen, shown = dev_select(args.data)
            print(json.dumps({"selected": chosen, "grid": shown}, indent=1))
            return 0
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if not (TUNED and MU_COUNT and MU_TRUE):
        print("error: set TUNED, MU_COUNT and MU_TRUE from dev, in D12, first", file=sys.stderr)
        return 1
    labels = _labels(args.data)
    claude = json.loads(args.claude_labels.read_text("utf-8"))["agreement"]["labels"]
    claude = {p: label or MISSING for p, label in claude.items()}  # D14
    cfg = run.config(args.data, now())
    del cfg["question rates per claim-day"], cfg["session size"]  # M6's other scenarios
    cfg |= {"run": cfg["run"] + "-compare", "decision": "D12 (M7e, after M7's results)"}
    cfg |= {"scenario": "uniform", "question rate per claim-day": {RATE: QUESTION_RATES[RATE]}}
    cfg |= {"tuned": TUNED, "μ count-aware": MU_COUNT, "μ true-rate": MU_TRUE}
    cfg |= {"budget-aware μ": budget.MU, "claude labels": str(args.claude_labels)}
    cfg |= {"scheduled": list(scheduled(claude)), "grid": GRID}
    cfg["policies"] = [*CURVE, *cfg["scheduled"], *APART]
    folder = args.out / cfg["run"]
    if folder.exists():
        print(f"error: {folder} exists; a run never overwrites another", file=sys.stderr)
        return 1
    try:
        metrics = evaluate(load_all(args.data), labels, claude, cfg["seeds"])
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    text = table(metrics, cfg)  # before any file, so a failure leaves no partial folder
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps(cfg, indent=1) + "\n")
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    (folder / "table.md").write_text(text)
    print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

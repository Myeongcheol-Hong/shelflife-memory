import itertools
import json
import random
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from eval.replay import adaptive_run, budget, compare, replay, run, score
from eval.replay.replay import POLICIES, Claim, Counts, Truth, interval
from eval.replay.timelines import load_all

SMOKE = Path(__file__).parents[2] / "eval" / "data" / "smoke" / "timelines"
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
RNG = random.Random(0)


def d(month, day, year=2024):
    return date(year, month, day)


START, END = date(2024, 1, 1), date(2024, 12, 31)  # the dev split


def claim(label, created=START, end=END, project="x"):
    return Claim(project, label, created, end, ())


def test_the_dense_curve_adds_four_points():
    assert compare.DENSE == [3, 7, 14, 20, 25, 30, 40, 45, 60, 90, 180]
    assert len(compare.GRID) == 80 and (7, 30, 90) in compare.GRID


@pytest.mark.parametrize("label", ["fast", "medium", "slow"])
def test_tuned_per_class_checks_each_label_at_its_interval(label):
    truth = Truth((d(3, 1),), ("2",), "1")
    days = {"fast": 5, "medium": 21, "slow": 90}[label]
    found = compare.per_class(5, 21, 90)(claim(label), truth, RNG)
    assert found == interval(days)(claim(label), truth, RNG)
    # With the class intervals it is per-class itself.
    assert compare.per_class(7, 30, 180)(claim(label), truth, RNG) == POLICIES["per-class"](
        claim(label), truth, RNG
    )


def test_relabeled_runs_per_class_with_the_other_labels():
    policy = compare.relabeled({"x": "slow"})
    expected = POLICIES["per-class"](claim("slow"), Truth((), (), "1"), RNG)
    assert policy(claim("fast"), Truth((), (), "1"), RNG) == expected == [d(6, 29), d(12, 26)]


def test_the_count_aware_rate_counts_each_change_day_since_the_last_check():
    mu, beta = 10.0, 2 * 30  # medium: β = α × 30
    first = budget.wait(mu, 1 / beta)
    start = d(1, 1)
    one = start + timedelta(first)
    # Two changes before the first check and one on its day; the next one after it.
    changes = (start + timedelta(3), start + timedelta(5), one, one + timedelta(2))
    truth = Truth(changes, ("2", "3", "4", "5"), "1")
    checks = compare.count_aware(mu)(claim("medium"), truth, RNG)
    assert checks[0] == one
    second = budget.wait(mu, (1 + 3) / (beta + first))  # three changes seen in `first` days
    assert checks[1] == one + timedelta(second)
    seen = 3 + sum(one < c <= checks[1] for c in changes)  # the day of the check counts once
    third = budget.wait(mu, (1 + seen) / (beta + first + second))
    assert checks[2] == checks[1] + timedelta(third)


def test_a_daily_change_sends_a_count_aware_claim_to_the_cap():
    days = tuple(d(1, 1) + timedelta(k) for k in range(1, 366))
    truth = Truth(days, tuple(map(str, range(365))), "0")
    checks = compare.count_aware(budget.MU)(claim("fast"), truth, RNG)
    gaps = [(b - a).days for a, b in zip([d(1, 1), *checks], checks, strict=False)]
    assert gaps[0] == budget.wait(budget.MU, 1 / 14) and gaps[1:] == [budget.CAP]


def test_from_mu_64_both_budget_policies_are_fixed_180():
    truth = Truth((d(1, 20), d(3, 1), d(7, 9)), ("2", "3", "4"), "1")
    fixed = POLICIES["fixed 180"](claim("fast"), truth, RNG)
    assert compare.count_aware(64)(claim("fast"), truth, RNG) == fixed
    assert compare.true_rate(64)(claim("fast"), truth, RNG) == fixed


def test_the_true_rate_is_a_fixed_interval_from_the_projects_rate_in_the_split():
    start, end = replay.SPLITS["test"]
    truth = Truth(tuple(start + timedelta(30 * k) for k in range(1, 19)), ("v",) * 18, "1")
    c = claim("slow", created=start + timedelta(40), end=end)
    lam = compare.true_lambda(truth, "test")
    assert lam == pytest.approx(18 / ((end - start).days + 1), rel=1e-12)
    expected = interval(budget.wait(10, lam))(c, truth, RNG)
    assert compare.true_rate(10)(c, truth, RNG) == expected
    gaps = {(b - a).days for a, b in itertools.pairwise([c.created, *expected])}
    assert gaps == {budget.wait(10, lam)}
    quiet = Truth((), (), "1")  # no change in the split: λ = 0, the cap
    assert compare.true_rate(10)(c, quiet, RNG)[0] == c.created + timedelta(budget.CAP)
    # A dev claim takes dev's rate: the same changes over a shorter split.
    dev = claim("slow")
    rate = compare.true_lambda(truth, "dev")
    assert rate != lam and rate == pytest.approx(18 / 366, rel=1e-12)
    assert compare.true_rate(10)(dev, truth, RNG)[0] == START + timedelta(budget.wait(10, rate))


def test_the_place_on_the_curve_uses_the_dense_points():
    # One project: fixed N costs 30 / N checks per claim-month and is stale N / 200.
    projects = {
        f"fixed {n}": {"p": Counts(claims=1, days=30, checks=30 / n, stale_days=30 * n / 200)}
        for n in compare.DENSE
    }
    projects["x"] = {"p": Counts(claims=1, days=30, checks=1.35, stale_days=3)}
    found = adaptive_run.place(projects, "x", compare.CURVE)
    assert found["between"] == ["fixed 25", "fixed 20"]  # sparse: fixed 30 and fixed 14
    assert found["value"] == pytest.approx(0.1 - 0.1125)


def test_selection_takes_the_least_stale_point_within_fixed_30s_cost():
    def counts(checks, stale):  # one project, 30 claim-days
        return {"p": Counts(claims=1, days=30, checks=checks, stale_days=stale)}

    dev = {"fixed 30": counts(1, 10), "a": counts(2, 1), "b": counts(1, 5), "c": counts(0.5, 5)}
    select = adaptive_run.select
    assert select(dev, ["a", "b", "c"], "fixed 30") == "c"  # a costs too much; c is cheaper
    dev["b"] = counts(1, 4)
    assert select(dev, ["a", "b", "c"], "fixed 30") == "b"  # at most fixed 30's cost fits
    with pytest.raises(ValueError):
        select(dev, ["a"], "fixed 30")


def smoke(tmp_path):
    data = tmp_path / "data"
    for path in SMOKE.rglob("*.jsonl"):
        (data / path.relative_to(SMOKE)).parent.mkdir(parents=True, exist_ok=True)
        (data / path.relative_to(SMOKE)).write_bytes(path.read_bytes())
    labels = itertools.cycle(("fast", "medium", "slow"))
    toml = (SMOKE / "projects.toml").read_text()
    toml = re.sub('volatility = ""', lambda _: f'volatility = "{next(labels)}"', toml)
    (data / "projects.toml").write_text(toml)
    return data


def test_the_cost_pass_stops_if_mu_64_is_not_fixed_180(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "SEEDS", [0])
    monkeypatch.setattr(compare, "true_rate", lambda mu: interval(round(3 * mu)))  # 192 days at 64
    with pytest.raises(ValueError, match="fixed 180"):
        compare.dev_costs(smoke(tmp_path))


def test_the_smoke_corpus_tunes_on_dev_and_then_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run, "SEEDS", [0])
    monkeypatch.setattr(score, "RESAMPLES", 20)
    data, out = smoke(tmp_path), tmp_path / "out"
    argv = ["--data", str(data), "--out", str(out)]

    def no_outcome(*args):
        raise AssertionError("the cost pass must not compute staleness")

    with monkeypatch.context() as patch:  # costs and μ from costs alone (D12)
        patch.setattr(replay, "outcome", no_outcome)
        found = compare.dev_costs(data)
        assert compare.main([*argv, "--dev-costs"]) == 0 and not out.exists()
    assert json.loads(capsys.readouterr().out) == json.loads(json.dumps(found))
    for key in ("count-aware", "true-rate"):
        mu, halvings = found[key]["μ"], found[key]["halvings"]
        assert found[key]["grid"][64] == found[key]["fixed 180"]
        assert found[key]["fixed 30"] == found["fixed 30"]
        # μ is the cheapest step at most fixed 30's cost, and a step around it costs more.
        assert mu == min(m for m, c in halvings.items() if c <= found["fixed 30"])
        assert any(c > found["fixed 30"] for c in halvings.values())
    # No point of the real grid fits on the smoke corpus, so the selection stops.
    assert compare.main([*argv, "--dev-select"]) == 1
    monkeypatch.setattr(compare, "GRID", [(14, 45, 120), (21, 60, 120), (28, 90, 180)])
    chosen, shown = compare.dev_select(data)
    assert set(shown) == {compare.tuned_name(*p) for p in compare.GRID}
    for name in ("TUNED", "MU_COUNT", "MU_TRUE"):
        monkeypatch.setattr(compare, name, None)
    assert compare.main(argv) == 1  # nothing set yet: no run before D12 records it
    tuned = compare.GRID[[compare.tuned_name(*p) for p in compare.GRID].index(chosen)]
    other = next(p for p in compare.GRID if p != tuned)
    monkeypatch.setattr(compare, "TUNED", other)
    monkeypatch.setattr(compare, "MU_COUNT", found["count-aware"]["μ"])
    monkeypatch.setattr(compare, "MU_TRUE", found["true-rate"]["μ"])
    labels = tmp_path / "claude.json"
    projects = re.findall(r'name = "([^"]+)"', (data / "projects.toml").read_text())
    claude = dict(zip(projects, itertools.cycle(("slow", None, "fast")), strict=False))
    labels.write_text(json.dumps({"agreement": {"labels": claude}}))
    argv += ["--claude-labels", str(labels)]
    splits, projects = [], compare._projects

    def recorded(timelines, labels, split, *args):
        splits.append(split)
        return projects(timelines, labels, split, *args)

    with monkeypatch.context() as patch:  # dev runs first, and its checks stop the run
        patch.setattr(compare, "_projects", recorded)
        assert compare.main(argv, now=lambda: NOW) == 1  # not dev's choice
        monkeypatch.setattr(compare, "TUNED", tuned)
        patch.setattr(compare, "MU_COUNT", 1.0)  # costs more than fixed 30 on dev
        assert compare.main(argv, now=lambda: NOW) == 1 and not out.exists()
    assert splits == ["dev", "dev"]  # test never replayed
    assert compare.main(argv, now=lambda: NOW) == 0
    [folder] = out.iterdir()
    metrics = json.loads((folder / "metrics.json").read_text())
    config = json.loads((folder / "config.json").read_text())
    ours = [n for n in config["policies"] if n not in compare.CURVE and n not in compare.APART]
    assert len(ours) == 7 and compare.tuned_name(*tuned) in ours
    for split in ("test", "dev"):
        part = metrics[split]
        assert set(part["policies"]) == {*compare.CURVE, *ours, *compare.APART}
        for m in part["policies"].values():
            assert list(m["buckets"]) == list(run.BUCKETS)
            assert sum(b["projects"] for b in m["buckets"].values()) == m["projects"]
        for name in ours:
            for metric in adaptive_run.COST:
                a = part["policies"][name][metric]["value"]
                b = part["policies"]["fixed 30"][metric]["value"]
                assert part["minus fixed 30"][name][metric]["value"] == a - b
            assert set(part["on the dense curve"][name]) == {
                "value",
                "between",
                "ci",
                "resamples outside",
            }
        tuned_cost = part["tuned minus per-class"]["checks per claim-month"]["value"]
        cost = [part["policies"][n]["checks per claim-month"]["value"] for n in ours[:2]]
        assert ours[:2] == ["per-class", compare.tuned_name(*tuned)]
        assert tuned_cost == cost[1] - cost[0]
    assert set(metrics["dev"]["grid"]) == set(shown) and "grid" not in metrics["test"]
    # Claude's labels: per-class with them, and medium for a project with none (D14).
    filled = {p: label or "medium" for p, label in claude.items()}
    mine = adaptive_run._projects(load_all(data), filled, "test", [0], {"x": POLICIES["per-class"]})
    stale = metrics["test"]["policies"]["per-class, Claude's labels"]["stale claim-days"]
    assert stale["value"] == score.value("stale claim-days", score.total(mine["x"]))
    # Each place is on the dense curve.
    base = compare.CURVE_POLICIES | {"per-class": POLICIES["per-class"]}
    found = adaptive_run._projects(load_all(data), compare._labels(data), "test", [0], base)
    place = adaptive_run.place(found, "per-class", compare.CURVE)
    assert metrics["test"]["on the dense curve"]["per-class"] == json.loads(json.dumps(place))
    table = (folder / "table.md").read_text()
    assert "not pre-registered" in table and "### Apart: not scheduled" in table
    for block in table.split("\n\n"):
        rows = [line for line in block.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, block
    assert compare.main(argv, now=lambda: NOW) == 1  # never overwrites a run

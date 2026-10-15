import json
import math
import random
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from eval.replay import adaptive, adaptive_run, run, score
from eval.replay.replay import FIXED, Claim, Counts, Truth

SMOKE = Path(__file__).parents[2] / "eval" / "data" / "smoke" / "timelines"


@pytest.mark.parametrize(("n", "k", "t"), [(10, 3, 7), (4, 1, 30), (100, 99, 1)])
def test_with_a_flat_prior_the_rate_is_the_likelihood_maximum(n, k, t):
    # k of n checks, each t days apart, saw a change: e^(λt) = n / (n - k), which counting
    # the changed checks (k / (n t)) underestimates.
    found = adaptive.rate(1, 0, Counter({t: k}), (n - k) * t)
    assert found == pytest.approx(math.log(n / (n - k)) / t, rel=1e-9)


def test_with_no_change_seen_the_rate_is_the_prior_mode():
    assert adaptive.rate(2, 60, Counter(), 0) == pytest.approx(1 / 60, rel=1e-9)
    assert adaptive.rate(2, 60, Counter(), 40) == pytest.approx(1 / 100, rel=1e-9)
    assert adaptive.rate(1, 30, Counter(), 0) == adaptive.rate(0.5, 15, Counter(), 500) == 0
    assert adaptive.rate(0.5, 15, Counter({30: 1}), 0) > 0  # one change is enough


@pytest.mark.parametrize(
    ("lam", "cap", "days"),
    [
        (math.log(2) / 10, 365, 10),
        (math.log(2) / 10.5, 365, 11),  # half up
        (math.log(2) / 10.49, 365, 10),
        (0, 180, 180),
        (1e-9, 180, 180),
        (100, 180, 1),
    ],
)
def test_the_wait_is_whole_days_from_one_to_the_cap(lam, cap, days):
    assert adaptive.wait(0.5, lam, cap) == days


def d(month, day):
    return date(2024, month, day)


def claim(label="medium"):
    return Claim("x", label, d(1, 1), d(12, 31), ())


def checks(truth, label="medium", p=0.5, alpha=2, cap=365, label_free=False):
    policy = adaptive.policy(p, alpha, cap, label_free)
    return policy(claim(label), truth, random.Random(0))


QUIET = Truth((), (), "1.0")


def test_each_check_learns_from_what_it_saw():
    # medium, α = 2: λ starts at 1 / 60, so the first wait is ln 2 × 60 = 41.6, 42 days.
    # Nothing changed: λ = 1 / (60 + 42), the next wait ln 2 × 102 = 70.7, 71 days.
    assert checks(QUIET)[:2] == [d(2, 12), d(4, 23)]
    changed = checks(Truth((d(1, 20),), ("2.0",), "1.0"))
    # The first check saw a change 42 days on: λ is the root for one change in 42 days.
    seen = adaptive.wait(0.5, adaptive.rate(2, 60, Counter({42: 1}), 0), 365)
    assert changed[:2] == [d(2, 12), d(2, 12) + timedelta(seen)] and seen == 27
    assert all(day <= d(12, 31) for day in changed) and changed == sorted(changed)
    on_the_day = checks(Truth((d(2, 12),), ("2.0",), "1.0"))  # a check sees its own day
    assert (on_the_day[1] - on_the_day[0]).days < 42


def test_the_label_sets_the_prior_unless_label_free():
    assert checks(QUIET, "slow")[0] == d(1, 1) + timedelta(250)  # ln 2 × 360 = 249.5
    assert checks(QUIET, "slow", label_free=True) == checks(QUIET, "medium", label_free=True)
    assert checks(QUIET, "slow", label_free=True) == checks(QUIET, "medium")  # 30 days


def test_with_alpha_at_most_one_the_first_check_waits_the_cap():
    assert checks(QUIET, alpha=1, cap=180)[0] == d(6, 29)  # 180 days on
    assert checks(QUIET, alpha=0.5, cap=365) == [d(12, 31)]  # the claim's last day


def counts(cost, stale):
    # 300 claim-days, so checks per claim-month is `cost` and the stale share is `stale`.
    return Counts(claims=1, days=300, checks=10 * cost, stale_days=300 * stale)


def test_selection_takes_the_freshest_point_within_per_class_cost_ties_to_the_cheaper():
    dev = {
        "per-class": {"p": counts(1.0, 0.4)},
        "a": {"p": counts(0.9, 0.2)},
        "b": {"p": counts(1.1, 0.1)},  # fresher, but dearer than per-class
        "c": {"p": counts(0.5, 0.2)},  # as fresh as a, and cheaper
        "d": {"p": counts(1.0, 0.3)},  # at per-class's cost exactly: allowed
    }
    assert adaptive_run.select(dev, ["a", "b", "c", "d"]) == "c"
    dev["e"] = {"p": counts(1.0, 0.1)}  # the freshest, at per-class's cost exactly
    assert adaptive_run.select(dev, ["a", "c", "e"]) == "e"
    with pytest.raises(ValueError, match="no grid point"):
        adaptive_run.select(dev, ["b"])


CURVE = {3: (10, 0.0), 7: (4, 0.1), 14: (2, 0.2), 30: (1, 0.3), 60: (0.5, 0.4)}
CURVE |= {90: (0.3, 0.5), 180: (0.2, 0.6)}


def test_the_curve_gives_the_fixed_n_stale_share_at_the_same_cost():
    # Two projects: q's curve and q's point are both 0.2 and 0.3 staler than p's.
    projects = {
        f"fixed {n}": {"p": counts(*CURVE[n]), "q": counts(CURVE[n][0], CURVE[n][1] + 0.2)}
        for n in FIXED
    }
    projects["x"] = {"p": counts(1.5, 0.15), "q": counts(1.5, 0.45)}
    found = adaptive_run.place(projects, "x")
    # Halfway between fixed 30 and fixed 14 in cost, the curve is at 0.25 for p and 0.45
    # for q, so the point is 0.1 below it for p, on it for q, and 0.05 below for both.
    assert found["value"] == pytest.approx(-0.05)
    assert found["between"] == ["fixed 30", "fixed 14"]
    # p twice and q twice are each a quarter of the resamples. The curve and the point
    # come from the same resample; unpaired, q's point against p's curve would give +0.2.
    assert found["ci"] == pytest.approx((-0.1, 0.0))
    assert found["resamples outside"] == 0


def test_a_point_outside_the_curve_in_any_resample_gets_no_interval():
    projects = {f"fixed {n}": dict.fromkeys("pq", counts(*CURVE[n])) for n in FIXED}
    projects["x"] = {"p": counts(1.5, 0.15), "q": counts(0.1, 0.9)}  # q: cheaper than 180
    found = adaptive_run.place(projects, "x")
    assert found["value"] is not None and found["ci"] is None
    assert 0 < found["resamples outside"] < score.RESAMPLES  # the resamples of q twice
    projects["x"] = dict.fromkeys("pq", counts(0.1, 0.9))
    assert adaptive_run.place(projects, "x") == dict.fromkeys(found, None)


def test_the_smoke_run_writes_config_metrics_and_table(tmp_path, monkeypatch):
    # Every eval runs on the smoke corpus in CI (CLAUDE.md); the labels come from the
    # test, written outside eval/data/ (D12); one seed and few resamples keep it fast.
    monkeypatch.setattr(run, "SEEDS", [0])
    monkeypatch.setattr(score, "RESAMPLES", 20)
    data = tmp_path / "data"
    for path in SMOKE.rglob("*.jsonl"):
        (data / path.relative_to(SMOKE)).parent.mkdir(parents=True, exist_ok=True)
        (data / path.relative_to(SMOKE)).write_bytes(path.read_bytes())
    toml = (SMOKE / "projects.toml").read_text()
    (data / "projects.toml").write_text(toml.replace('volatility = ""', 'volatility = "fast"'))
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    argv = ["--data", str(data), "--out", str(tmp_path / "out")]
    assert adaptive_run.main(argv, now=lambda: now) == 0
    [folder] = (tmp_path / "out").iterdir()
    assert folder.name.endswith("-adaptive")
    config = json.loads((folder / "config.json").read_text())
    assert config["seeds"] == [0] and len(config["grid"]) == 30
    metrics = json.loads((folder / "metrics.json").read_text())
    chosen = metrics["selected"]
    assert chosen in metrics["dev grid"] and chosen.startswith("adaptive ")
    cost = metrics["dev grid"][chosen]["checks per claim-month"]
    assert cost <= metrics["per-class dev cost"]
    assert set(metrics["test"]["policies"]) == {
        chosen,
        "per-class",
        "fixed 30",
        chosen + " label-free",
    }
    for split in ("test", "dev"):
        found = metrics[split]
        pairs = {
            "selected minus per-class": (chosen, "per-class"),
            "selected minus fixed 30": (chosen, "fixed 30"),
        }
        if split == "test":
            pairs["label-free minus selected"] = (chosen + " label-free", chosen)
        assert {key for key in found if " minus " in key} == set(pairs)
        for key, (a, b) in pairs.items():
            for m in adaptive_run.COST:
                value = found["policies"][a][m]["value"] - found["policies"][b][m]["value"]
                assert found[key][m]["value"] == value
        assert set(found["on the fixed-N curve"]) == {"value", "between", "ci", "resamples outside"}
    table = (folder / "table.md").read_text()
    assert table.startswith(f"# 6.1 adaptive policy (M7), run {folder.name}")
    for block in table.split("\n\n"):
        rows = [line for line in block.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, block
    assert adaptive_run.main(argv, now=lambda: now) == 1  # never overwrites a run

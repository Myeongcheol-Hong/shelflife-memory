import itertools
import json
import math
import random
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from eval.replay import adaptive, budget, replay, run, score
from eval.replay.replay import POLICIES, Claim, Truth

SMOKE = Path(__file__).parents[2] / "eval" / "data" / "smoke" / "timelines"
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def solve(c):
    """x with g(x) = c, by plain bisection, for comparison."""
    lo, hi = 0.0, 1.0
    while budget.g(hi) < c:
        hi *= 2
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if budget.g(mid) < c else (lo, mid)
    return (lo + hi) / 2


@pytest.mark.parametrize(("label", "days"), [("fast", 35), ("medium", 44), ("slow", 92)])
def test_the_first_wait_follows_the_label_through_the_prior(label, days):
    # D12's example: μ = 10 days, and the prior's λ is 1 / (2 × the class interval).
    claim = Claim("x", label, date(2024, 1, 1), date(2024, 12, 31), ())
    checks = budget.policy(10)(claim, Truth((), (), "1"), random.Random(0))
    assert checks[0] == claim.created + timedelta(days)


def test_the_wait_is_x_over_lambda_rounded_half_up_and_capped():
    rng = random.Random(0)
    for _ in range(2000):
        lam, mu = 10 ** rng.uniform(-4, 1), 10 ** rng.uniform(-1, 2)
        if mu * lam >= 1:  # no positive frequency meets the condition
            assert budget.wait(mu, lam) == budget.CAP
            continue
        rounded = math.floor(solve(mu * lam) / lam + 0.5)
        assert budget.wait(mu, lam) == max(1, min(budget.CAP, rounded))


def test_a_claim_that_changes_too_often_waits_the_cap():
    assert budget.wait(14, 1 / 14) == budget.CAP  # μλ = 1: the optimum is no check
    assert budget.wait(10, 0.2) == budget.CAP
    # Every wait is at least 3.35 μ: at μ = 10, 33.5 days, so 34 at the shortest.
    assert min(budget.wait(10, k / 10_000) for k in range(1, 2000)) == 34


def d(month, day):
    return date(2024, month, day)


def test_from_mu_54_every_wait_is_the_cap_so_mu_64_is_fixed_180():
    assert {budget.wait(64, lam) for lam in (1e-6, 1e-3, 0.008, 0.1, 5)} == {budget.CAP}
    claim = Claim("x", "fast", d(1, 1), d(12, 31), ())
    truth = Truth((d(1, 20), d(3, 1), d(7, 9)), ("2", "3", "4"), "1")
    rng = random.Random(0)
    assert budget.policy(64)(claim, truth, rng) == POLICIES["fixed 180"](claim, truth, rng)
    assert budget.wait(53.5, 0.535 / 53.5) < budget.CAP  # just below 180 / 3.35


def test_each_check_updates_the_rate_as_in_m7b():
    claim = Claim("x", "medium", d(1, 1), d(12, 31), ())
    checks = budget.policy(10)(claim, Truth((), (), "1"), random.Random(0))
    second = budget.wait(10, adaptive.rate(2, 60, Counter(), 44))  # 44 days, nothing seen
    assert checks[:2] == [d(1, 1) + timedelta(44), d(1, 1) + timedelta(44 + second)]


def test_the_search_takes_the_bracket_end_at_most_the_target():
    mu, found = budget.search(lambda m: 1 / m, 0.1)
    assert list(found["grid"]) == budget.GRID and len(found["halvings"]) == budget.HALVINGS
    assert 1 / mu <= 0.1 and mu == pytest.approx(10, rel=1e-5)
    # Equal costs on the grid (32 and 64 both cost 0.05) are allowed: only a rise stops it.
    assert budget.search(lambda m: max(0.05, 1 / m), 0.1)[1]["grid"][32] == 0.05
    # A cost equal to the target counts as at most: ceil(μ) ≥ 10 is enough, so μ is just
    # above 9, not above 10.
    steps = budget.search(lambda m: 1 / math.ceil(m), 0.1)[0]
    assert 9 < steps < 9.0001


@pytest.mark.parametrize(
    ("cost", "target"),
    [
        (lambda m: 1 / m + (m == 8), 0.1),  # a cost that rises
        (lambda m: 1 / m, 2),  # μ = 1 already costs less
        (lambda m: 1 / m, 0.001),  # μ = 64 still costs more
    ],
)
def test_the_search_stops_rather_than_choose_another_way(cost, target):
    with pytest.raises(ValueError):
        budget.search(cost, target)


def smoke(tmp_path):
    # The smoke corpus with labels from the test, fast, medium and slow in turn, written
    # outside eval/data/ (D12).
    data = tmp_path / "data"
    for path in SMOKE.rglob("*.jsonl"):
        (data / path.relative_to(SMOKE)).parent.mkdir(parents=True, exist_ok=True)
        (data / path.relative_to(SMOKE)).write_bytes(path.read_bytes())
    labels = itertools.cycle(("fast", "medium", "slow"))
    toml = (SMOKE / "projects.toml").read_text()
    toml = re.sub('volatility = ""', lambda _: f'volatility = "{next(labels)}"', toml)
    (data / "projects.toml").write_text(toml)
    return data


def test_the_smoke_corpus_sets_mu_from_costs_and_then_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run, "SEEDS", [0])
    monkeypatch.setattr(score, "RESAMPLES", 20)
    data, out = smoke(tmp_path), tmp_path / "out"

    def no_outcome(*args):
        raise AssertionError("the cost pass must not compute staleness")

    with monkeypatch.context() as patch:  # μ is set from costs alone (D12)
        patch.setattr(replay, "outcome", no_outcome)
        found = budget.dev_costs(data)
        argv = ["--data", str(data), "--out", str(out)]
        assert budget.main([*argv, "--dev-costs"]) == 0 and not out.exists()
    assert found["grid"][budget.GRID[-1]] == found["fixed 180"]
    assert found["halvings"][found["μ"]] <= found["fixed 30"]
    assert f"μ = {found['μ']!r} days, costing" in capsys.readouterr().out
    monkeypatch.setattr(budget, "MU", None)
    assert budget.main(argv) == 1  # MU not set: no run before μ is recorded
    monkeypatch.setattr(budget, "MU", found["μ"])
    assert budget.main(argv, now=lambda: NOW) == 0
    [folder] = out.iterdir()
    assert folder.name.endswith("-budget")
    config = json.loads((folder / "config.json").read_text())
    assert config["μ"] == found["μ"] and config["seeds"] == [0]
    metrics = json.loads((folder / "metrics.json").read_text())
    ours = budget.name(found["μ"])
    for split in ("test", "dev"):
        part = metrics[split]
        assert set(part["policies"]) == {ours, "fixed 30"}
        for m in ("stale-answer rate", "stale claim-days", "checks per claim-month"):
            value = part["policies"][ours][m]["value"] - part["policies"]["fixed 30"][m]["value"]
            assert part["minus fixed 30"][m]["value"] == value
        assert set(part["on the fixed-N curve"]) == {"value", "between", "ci", "resamples outside"}
    dev_cost = metrics["dev"]["policies"][ours]["checks per claim-month"]["value"]
    assert dev_cost == pytest.approx(found["halvings"][found["μ"]], rel=1e-12)
    table = (folder / "table.md").read_text()
    assert "so not pre-registered" in table and "## Dev, where μ was set" in table
    for block in table.split("\n\n"):
        rows = [line for line in block.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, block
    assert budget.main(argv, now=lambda: NOW) == 1  # never overwrites a run

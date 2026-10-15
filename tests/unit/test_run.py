import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval.replay import run, score
from eval.replay.replay import QUESTION_RATES, SPLITS, Counts
from eval.replay.timelines import load_all

SMOKE = Path(__file__).parents[2] / "eval" / "data" / "smoke" / "timelines"


@pytest.mark.parametrize(
    ("per_year", "name"),
    [
        (0, "0 changes a year"),
        (0.1, "under 6"),
        (5.99, "under 6"),
        (6, "6 to 52"),
        (52, "6 to 52"),
        (52.01, "over 52"),
    ],
)
def test_the_change_rate_groups_follow_d12(per_year, name):
    assert run.bucket(per_year) == name


def test_the_late_labeled_four_are_left_out_of_their_line():
    timelines = load_all(SMOKE)
    labels = {t.project: "slow" for t in timelines} | {"gohugoio/hugo": "fast"}
    groups = run._groups(timelines, labels, "test")
    assert "gohugoio/hugo" not in groups["without the late-labeled four"]
    assert groups["without the late-labeled four"] == {t.project for t in timelines}
    assert groups["fast"] == {"gohugoio/hugo"} and len(groups["slow"]) == len(timelines)


@pytest.mark.parametrize(
    ("peak_hi", "stale_hi", "verdict"),
    [(-1, 0.005, True), (0, -0.01, False), (-1, 0.0051, False), (-0.5, -0.02, True)],
)
def test_jitter_helps_only_by_the_pre_registered_rule(peak_hi, stale_hi, verdict):
    found = {"peak per day": {"ci": (-9, peak_hi)}, "stale-answer rate": {"ci": (-1, stale_hi)}}
    assert run.helps(found) is verdict


def test_paired_differences_take_the_same_resamples_of_both_policies():
    # The projects differ, but per-class beats fixed 30 by the same margin in each, so
    # only paired resamples give an interval that collapses to that margin.
    on = {"p": Counts(1, 4, 2, days=10, stale_days=5, checks=3)}
    on["q"] = Counts(1, 4, 3, days=10, stale_days=7, checks=5)
    off = {"p": Counts(1, 4, 1, days=10, stale_days=2, checks=1)}
    off["q"] = Counts(1, 4, 2, days=10, stale_days=4, checks=3)
    found = run._paired(on, off, (*run.STALE, "checks per claim-month"))
    assert found == {
        "stale-answer rate": {"value": 0.25, "ci": (0.25, 0.25)},
        "stale claim-days": {"value": pytest.approx(0.3), "ci": pytest.approx((0.3, 0.3))},
        "checks per claim-month": {"value": 6.0, "ci": (6.0, 6.0)},
    }
    assert set(run._paired(on, off)) == set(run.STALE)  # what jitter reports


def test_per_class_minus_fixed_30_is_in_that_order(monkeypatch):
    # With every label fast, per-class checks every 7 days: fresher than fixed 30, and dearer.
    monkeypatch.setattr(score, "RESAMPLES", 20)
    timelines = load_all(SMOKE)
    metrics = run.run(timelines, {t.project: "fast" for t in timelines}, seeds=[0])
    for key, found in metrics[run.VERSUS].items():
        for m in (*run.STALE, "checks per claim-month"):
            a, b = metrics[key]["per-class"][m]["value"], metrics[key]["fixed 30"][m]["value"]
            assert found[m]["value"] == a - b
        assert found["stale claim-days"]["value"] < 0 < found["checks per claim-month"]["value"]
    table = run.table(metrics, "x")
    assert table.index("| test |") < table.index("| dev |")  # test is the headline


def test_the_claims_table_shows_each_rows_dropped_claims():
    metrics = {
        "dev / sessions / 1 a week": {"never": {"projects": 2, "claims": 35.6}},
        "test / uniform / 1 a week": {"never": {"projects": 3, "claims": 60.0}},
        run.VERSUS: {"test / uniform / 1 a week": {}},
        "jitter": {"primary: helps": False},
    }
    assert run._claims(metrics)[2:] == [
        "| dev / sessions / 1 a week | 2 | 35.6 | 4.4 |",
        "| test / uniform / 1 a week | 3 | 60.0 | 0.0 |",
    ]


def test_the_smoke_run_writes_config_metrics_and_table(tmp_path, monkeypatch):
    # The whole pipeline on the smoke corpus, as CI runs every eval (CLAUDE.md). The labels
    # come from the test, written outside eval/data/ (D12); fewer seeds and resamples
    # keep it fast.
    monkeypatch.setattr(run, "SEEDS", [0])
    monkeypatch.setattr(score, "RESAMPLES", 50)
    data = tmp_path / "data"
    for path in SMOKE.rglob("*.jsonl"):
        (data / path.relative_to(SMOKE)).parent.mkdir(parents=True, exist_ok=True)
        (data / path.relative_to(SMOKE)).write_bytes(path.read_bytes())
    toml = (SMOKE / "projects.toml").read_text()
    (data / "projects.toml").write_text(toml.replace('volatility = ""', 'volatility = "medium"'))
    now = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    assert run.main(["--data", str(data), "--out", str(tmp_path / "out")], now=lambda: now) == 0
    [folder] = (tmp_path / "out").iterdir()
    config = json.loads((folder / "config.json").read_text())
    assert re.fullmatch(r"2026-10-14-[0-9a-f]{7}", folder.name) and config["run"] == folder.name
    assert re.fullmatch(r"[0-9a-f]{40}", config["git sha"])
    assert re.fullmatch(r"[0-9a-f]{64}", config["dataset sha256"])
    assert config["packaging"] and config["seeds"] == [0] and config["session size"] == 10
    metrics = json.loads((folder / "metrics.json").read_text())
    combos = {f"{s} / {c} / {r}" for s in SPLITS for c in run.SCENARIOS for r in QUESTION_RATES}
    assert set(metrics) == combos | {run.VERSUS, "jitter"}
    headline = metrics["test / uniform / 1 a week"]
    assert headline["every read"]["stale-answer rate"]["value"] == 0
    assert headline["oracle"]["stale claim-days"]["value"] == 0
    assert headline["per-class"]["groups"]["medium"]["projects"] == 6  # the test's labels
    assert set(metrics[run.VERSUS]) == {f"{s} / uniform / 1 a week" for s in SPLITS}
    jitter = metrics["jitter"]
    assert jitter["primary: helps"] is run.helps(jitter["sessions / per-class"])
    assert set(jitter) == {f"{s} / {p}" for s in run.SCENARIOS for p in run.JITTERED} | {
        "primary: helps"
    }
    table = (folder / "table.md").read_text()
    assert table.startswith(f"# 6.1 replay, run {folder.name}")
    assert "Primary comparison (D12), sessions / per-class: jitter" in table
    # The jitter table shows the peak without jitter, with it, and the difference.
    sessions = metrics["test / sessions / 1 a week"]
    [primary] = [line for line in table.splitlines() if "(primary)" in line]
    peaks = [sessions[p]["peak per day"] for p in ("per-class", "per-class + jitter")]
    assert primary.split(" | ")[1:4] == [
        f"{peaks[0]:.1f}",
        f"{peaks[1]:.1f}",
        run._num(jitter["sessions / per-class"]["peak per day"]),
    ]
    assert jitter["sessions / per-class"]["peak per day"]["value"] == pytest.approx(
        peaks[1] - peaks[0]
    )
    assert "## Per-class minus fixed 30, paired (uniform, 1 a week)" in table
    assert sum(line.startswith(("| test |", "| dev |")) for line in table.splitlines()) == 2
    # Each row's claim count; the uniform scenario never drops a claim.
    claims = {line.split(" | ")[0][2:]: line for line in table.splitlines() if " / " in line}
    assert set(claims) >= combos
    assert all(claims[k].endswith("| 0.0 |") for k in combos if "uniform" in k)
    # Every row has its header's columns, so the Markdown renders.
    for block in table.split("\n\n"):
        rows = [line for line in block.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, block
    # A run never overwrites another.
    assert run.main(["--data", str(data), "--out", str(tmp_path / "out")], now=lambda: now) == 1

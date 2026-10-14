import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval.replay import run, score
from eval.replay.replay import QUESTION_RATES, SPLITS
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
    assert set(metrics) == combos | {"jitter"}
    headline = metrics["test / uniform / 1 a week"]
    assert headline["every read"]["stale-answer rate"]["value"] == 0
    assert headline["oracle"]["stale claim-days"]["value"] == 0
    assert headline["per-class"]["groups"]["medium"]["projects"] == 6  # the test's labels
    jitter = metrics["jitter"]
    assert jitter["primary: helps"] is run.helps(jitter["sessions / per-class"])
    assert set(jitter) == {f"{s} / {p}" for s in run.SCENARIOS for p in run.JITTERED} | {
        "primary: helps"
    }
    table = (folder / "table.md").read_text()
    assert table.startswith(f"# 6.1 replay, run {folder.name}")
    assert "Primary comparison (D12), sessions / per-class: jitter" in table
    # Every row has its header's columns, so the Markdown renders.
    for block in table.split("\n\n"):
        rows = [line for line in block.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, block
    # A run never overwrites another.
    assert run.main(["--data", str(data), "--out", str(tmp_path / "out")], now=lambda: now) == 1

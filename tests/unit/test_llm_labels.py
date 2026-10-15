import itertools
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval import runner
from eval.replay import adaptive_run, llm_labels, run, score
from eval.replay.replay import POLICIES
from eval.replay.timelines import LABELS, Project, load_all

SMOKE = Path(__file__).parents[2] / "eval" / "data" / "smoke" / "timelines"
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("fast", "fast"),
        (" Medium.\n", "medium"),
        ("SLOW", "slow"),
        ("fast or medium", None),
        ("none", None),
        ("", None),
    ],
)
def test_an_answer_counts_only_if_it_is_a_label(text, label):
    assert llm_labels.parse(text) == label


@pytest.mark.parametrize(
    ("answers", "label"),
    [
        (["fast", "fast", "slow"], "fast"),  # the majority
        (["slow", "fast", "medium"], "medium"),  # all differ: the middle
        (["slow", None, "fast"], "fast"),  # two that differ: the faster
        (["slow", "slow", None], "slow"),
        ([None, "medium", None], "medium"),
        ([None, None, None], None),
    ],
)
def test_a_project_label_is_the_median_of_its_valid_answers(answers, label):
    assert llm_labels.median(answers) == label


def test_the_question_names_the_project_and_nothing_else():
    pypi = llm_labels.item(Project("pypi", "attrs", "slow"))
    github = llm_labels.item(Project("github", "caddyserver/caddy", "fast", tag="^v"))
    assert pypi.id == "attrs"
    assert pypi.prompt == "How often does the latest version of the PyPI project attrs change?"
    assert "of the GitHub repository caddyserver/caddy change?" in github.prompt
    for prompt in (pypi.prompt, github.prompt):  # never the maintainer's label
        assert not any(label in prompt for label in LABELS) and "^v" not in prompt


THEIRS = {"a": "fast", "b": "medium", "c": "slow", "d": "fast", "e": "fast", "f": "medium"}
THEIRS["g"] = "medium"
THEIRS["zed-industries/zed"] = "slow"
FOUND = {
    "a": ["fast", "fast", "fast"],
    "b": ["slow", "slow", "slow"],  # slower: staler
    "c": ["medium", "fast", "slow"],  # medium: faster, more checks
    "d": [None, None, None],
    "e": ["medium", "medium", "medium"],  # slower
    "f": ["slow", None, "fast"],  # two that differ: fast, faster
    "g": ["medium", "medium", None],  # two that agree
    "zed-industries/zed": ["slow", "medium", "slow"],  # labeled late (D11)
}


def test_agreement_counts_each_direction_per_project_and_per_answer():
    found = llm_labels.agreement(FOUND, THEIRS)
    assert found["labels"] == {"a": "fast", "b": "slow", "c": "medium", "d": None} | {
        "e": "medium",
        "f": "fast",
        "g": "medium",
        "zed-industries/zed": "slow",
    }
    assert found["maintainer by Claude"]["fast"] == {"fast": 1, "medium": 1, "slow": 0, "none": 1}
    assert found["maintainer by Claude"]["medium"] == {"fast": 1, "medium": 1, "slow": 1, "none": 0}
    assert found["maintainer by Claude"]["slow"] == {"fast": 0, "medium": 1, "slow": 1, "none": 0}

    def counts(key):
        return {k: v["count"] for k, v in found[key].items() if k != "n"}

    assert counts("projects") == {
        "same": 3,
        "Claude faster (more checks)": 2,
        "Claude slower (staler)": 2,
        "invalid": 1,
    }
    assert found["projects"]["same"]["share"] == 3 / 8
    assert counts("projects without the four labeled late")["same"] == 2
    assert counts("answers") == {
        "same": 3 + 1 + 2 + 2,  # a; c's slow; zed's two slow; g's two
        "Claude faster (more checks)": 2 + 1 + 1,  # c's medium and fast; zed's medium; f's fast
        "Claude slower (staler)": 3 + 3 + 1,  # b and e; f's slow
        "invalid": 3 + 1 + 1,  # d; f's; g's
    }
    assert found["projects whose answers all agree"] == 3  # a, b and e; not d's invalid ones
    assert found["projects decided between two different answers"] == 1  # f, not g
    assert found["projects with no valid answer"] == ["d"]


def smoke(tmp_path):
    # The smoke corpus with labels from the test, fast, medium and slow in turn, written
    # outside eval/data/ (D12).
    data = tmp_path / "data"
    for path in SMOKE.rglob("*.jsonl"):
        (data / path.relative_to(SMOKE)).parent.mkdir(parents=True, exist_ok=True)
        (data / path.relative_to(SMOKE)).write_bytes(path.read_bytes())
    labels = itertools.cycle(LABELS)
    toml = (SMOKE / "projects.toml").read_text()
    toml = re.sub('volatility = ""', lambda _: f'volatility = "{next(labels)}"', toml)
    (data / "projects.toml").write_text(toml)
    return data


class Stub:
    """A model that answers from a table by project, and records what it was asked."""

    def __init__(self, replies):
        self.replies, self.asked = replies, []

    def describe(self):
        return {"model": "stub-1"}

    def __call__(self, system, prompt):
        self.asked.append((system, prompt))
        name = re.search(r"(\S+) change\?", prompt).group(1)
        repeat = sum(name in p for _, p in self.asked) - 1
        text = self.replies[name][repeat]
        return runner.Reply(text, error=None if text else "failed", served=("stub-1",))


REPLIES = {
    "smoke-backport": ["fast"] * 3,  # the maintainer's fast
    "smoke-prerelease-only": ["Slow."] * 3,  # medium
    "smoke-quiet": ["medium", "fast", "slow"],  # slow
    "smoke-org/moved-tag": ["I think fast"] * 3,  # fast
    "smoke-org/out-of-order": ["medium", "slow", "medium"],  # medium
    "smoke-org/two-products": ["slow"] * 3,  # slow
}


MEDIANS = {
    "smoke-backport": "fast",
    "smoke-prerelease-only": "slow",
    "smoke-quiet": "medium",
    "smoke-org/moved-tag": "medium",  # no valid answer
    "smoke-org/out-of-order": "medium",
    "smoke-org/two-products": "slow",
}
THEIRS_SMOKE = dict(zip(MEDIANS, itertools.cycle(LABELS), strict=False))  # as smoke() writes
per_class = POLICIES["per-class"]


def test_the_smoke_run_asks_scores_and_rescores_without_the_model(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "LATE_LABELED", {"smoke-quiet"})  # as if labeled late (D11)
    monkeypatch.setattr(run, "SEEDS", [0])
    monkeypatch.setattr(score, "RESAMPLES", 20)
    data, out = smoke(tmp_path), tmp_path / "out"
    stub = Stub(REPLIES)
    argv = ["--data", str(data), "--out", str(out)]
    assert llm_labels.main(argv, model=stub, now=lambda: NOW) == 0
    assert len(stub.asked) == 6 * runner.REPEATS
    assert {system for system, _ in stub.asked} == {llm_labels.SYSTEM}
    [folder] = out.iterdir()
    metrics = json.loads((folder / "metrics.json").read_text())
    found = metrics["agreement"]
    assert found["labels"]["smoke-org/moved-tag"] is None
    assert found["projects with no valid answer"] == ["smoke-org/moved-tag"]
    assert {k: v["count"] for k, v in found["projects"].items() if k != "n"} == {
        "same": 3,
        "Claude faster (more checks)": 1,
        "Claude slower (staler)": 1,
        "invalid": 1,
    }
    assert found["answers"]["n"] == 6 * runner.REPEATS
    ours, theirs = llm_labels.OURS, llm_labels.THEIRS
    for split in ("test", "dev"):
        part = metrics[split]
        assert set(part["policies"]) == {ours, theirs, "fixed 30"}
        cost = "checks per claim-month"  # three projects' labels differ, so the costs do
        assert part["policies"][ours][cost]["value"] != part["policies"][theirs][cost]["value"]
        for key in ("claims", "projects"):  # the same claims under both label sets
            assert part["policies"][ours][key] == part["policies"][theirs][key]
        # Claude's replay is per-class with the medians, and medium where none is valid.
        mine = adaptive_run._projects(load_all(data), MEDIANS, split, [0], {"x": per_class})
        for m in ("stale-answer rate", "stale claim-days", cost):
            assert part["policies"][ours][m]["value"] == score.value(m, score.total(mine["x"]))
        early = {}
        for who, labels in (("ours", MEDIANS), ("theirs", THEIRS_SMOKE)):
            found_p = adaptive_run._projects(load_all(data), labels, split, [0], {"x": per_class})
            early[who] = {p: c for p, c in found_p["x"].items() if p != "smoke-quiet"}
        expected = run._paired(early["ours"], early["theirs"], adaptive_run.COST)
        assert part["the same, without the four labeled late"] == json.loads(json.dumps(expected))
        pairs = {
            "Claude's labels minus the maintainer's": theirs,
            "Claude's labels minus fixed 30": "fixed 30",
        }
        for key, other in pairs.items():
            for m in ("stale-answer rate", "stale claim-days", "checks per claim-month"):
                value = part["policies"][ours][m]["value"] - part["policies"][other][m]["value"]
                assert part[key][m]["value"] == value
        assert set(part["on the fixed-N curve"]) == {"value", "between", "ci", "resamples outside"}
    table = (folder / "table.md").read_text()
    assert table.startswith(f"# 6.1 LLM-judged volatility policy (M7), run {folder.name}")
    assert llm_labels.LIMIT in table and "No valid answer, so medium: smoke-org/moved-tag" in table
    for block in table.split("\n\n"):
        rows = [line for line in block.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, block

    def no_model(system, prompt):
        raise AssertionError("scoring a finished run never calls the model")

    no_model.describe = stub.describe
    assert llm_labels.main(argv, model=no_model, now=lambda: NOW) == 0  # resumes: all done
    rescore = ["--data", str(data), "--rescore", str(folder)]
    assert llm_labels.main(rescore, model=no_model, now=lambda: NOW) == 0
    assert json.loads((folder / "metrics.json").read_text()) == metrics


def test_a_run_cut_short_is_not_scored(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "SEEDS", [0])
    data, out = smoke(tmp_path), tmp_path / "out"
    stub = Stub({name: [None] * 3 for name in REPLIES})  # every call fails
    argv = ["--data", str(data), "--out", str(out)]
    assert llm_labels.main(argv, model=stub, now=lambda: NOW) == 1
    assert len(stub.asked) == runner.STOP_AFTER
    [folder] = out.iterdir()
    assert not (folder / "metrics.json").exists()


def test_a_failed_call_anywhere_is_asked_again_before_scoring(tmp_path, monkeypatch):
    # One failure late in the run: the runner does not stop, but nothing is scored until
    # running again has asked that pair again, so the scores never depend on the reruns.
    monkeypatch.setattr(run, "SEEDS", [0])
    monkeypatch.setattr(score, "RESAMPLES", 20)
    data, out = smoke(tmp_path), tmp_path / "out"
    stub = Stub(REPLIES | {"smoke-org/two-products": ["slow", "slow", None, "slow"]})
    argv = ["--data", str(data), "--out", str(out)]
    assert llm_labels.main(argv, model=stub, now=lambda: NOW) == 1
    [folder] = out.iterdir()
    assert not (folder / "metrics.json").exists()
    asked = len(stub.asked)
    assert llm_labels.main(argv, model=stub, now=lambda: NOW) == 0
    assert len(stub.asked) == asked + 1
    metrics = json.loads((folder / "metrics.json").read_text())
    assert metrics["answers"]["smoke-org/two-products"] == ["slow"] * 3

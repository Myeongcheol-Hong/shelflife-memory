import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval import runner
from eval.runner import Claude, Item, Reply

ROOT = Path(__file__).parents[2]
# The runner's code path to `claude`, with a fake that prints what it was sent; no test
# calls a model (CLAUDE.md).
FAKE = (sys.executable, str(ROOT / "tests" / "fixtures" / "fake_claude.py"))


def fake(**kwargs):
    return Claude("claude-test-1", command=FAKE, **kwargs)


def test_each_call_runs_in_a_new_folder_outside_the_repository_with_no_customizations():
    reply = fake()("Answer in one word.", "Is it raining?")
    sent = json.loads(reply.text)
    args = sent["args"]
    assert args[:3] == ["-p", "--model", "claude-test-1"]
    assert "--safe-mode" in args and "--no-session-persistence" in args
    assert args[args.index("--tools") + 1] == ""  # no tools
    assert args[args.index("--output-format") + 1] == "json"
    assert args[args.index("--system-prompt") + 1] == "Answer in one word."
    assert "--fallback-model" not in args and "--effort" not in args
    assert sent["stdin"] == "Is it raining?"  # never an argument
    folder = Path(sent["cwd"])
    assert not folder.resolve().is_relative_to(ROOT.resolve()) and not folder.exists()
    assert reply == Reply(reply.text, None, ("claude-test-1",), 0.001, 5)


def test_effort_is_passed_and_recorded_only_when_set():
    args = json.loads(fake(effort="low")("s", "p").text)["args"]
    assert args[args.index("--effort") + 1] == "low"
    described = {"model": "claude-test-1", "effort": "low", "claude": "9.9.9 (Claude Code)"}
    assert fake(effort="low").describe() == described


@pytest.mark.parametrize(
    ("mode", "kept", "error"),
    [
        # `claude -p` prints an unknown model's error as a result with subtype success
        ("error", False, "exit 1: There's an issue with the selected model."),
        ("garbage", False, "exit 2: boom"),
        ("other", True, "served by claude-other-0"),
    ],
)
def test_a_failed_call_or_another_model_never_counts_as_an_answer(monkeypatch, mode, kept, error):
    monkeypatch.setenv("FAKE_CLAUDE", mode)
    reply = fake()("s", "p")
    assert reply.error == error and (reply.text is not None) is kept


def test_a_call_with_no_reply_in_time_is_an_error(monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE", "sleep")
    assert fake(timeout=0.5)("s", "p") == Reply(None, "no reply in 0.5 s")


class Stub:
    """Answers each prompt in upper case; the calls numbered in `fail` fail."""

    def __init__(self, fail=()):
        self.calls, self.fail = [], fail

    def describe(self):
        return {"model": "stub-1", "effort": None, "claude": "stub"}

    def __call__(self, system, prompt):
        self.calls.append(prompt)
        if len(self.calls) in self.fail:
            return Reply(None, "rate limited")
        return Reply(prompt.upper(), served=("stub-1",), cost_usd=0.01, duration_ms=7)


ITEMS = [Item("a", "first"), Item("b", "second")]


def ask(tmp_path, model, version="v1"):
    data = tmp_path / "labels.toml"
    data.write_text("x")
    now = lambda: datetime(2026, 10, 15, 9, 0, tzinfo=UTC)  # noqa: E731
    return runner.run("demo", ITEMS, "Be brief.", version, model, [data], tmp_path / "out", now=now)


def test_a_run_asks_each_item_three_times_and_keeps_every_reply(tmp_path):
    stub = Stub()
    folder = ask(tmp_path, stub)
    assert stub.calls == ["first", "second"] * 3  # one pass over the items per repeat
    assert re.fullmatch(r"2026-10-15-[0-9a-f]{7}-demo-stub-1", folder.name)
    config = json.loads((folder / "config.json").read_text())
    assert config["model"] == "stub-1" and config["prompt version"] == "v1"
    assert config["system prompt sha256"] == hashlib.sha256(b"Be brief.").hexdigest()
    assert (config["items"], config["repeats"], config["started at"]) == (
        2,
        3,
        "2026-10-15T09:00:00+00:00",
    )
    assert re.fullmatch(r"[0-9a-f]{40}", config["git sha"])
    assert re.fullmatch(r"[0-9a-f]{64}", config["dataset sha256"])
    rows = runner.rows(folder)
    assert [(r["item"], r["repeat"], r["attempt"]) for r in rows] == [
        ("a", 0, 0),
        ("b", 0, 0),
        ("a", 1, 0),
        ("b", 1, 0),
        ("a", 2, 0),
        ("b", 2, 0),
    ]
    assert rows[1] | {"at": None} == {
        "item": "b",
        "repeat": 0,
        "attempt": 0,
        "prompt sha256": hashlib.sha256(b"second").hexdigest(),
        "text": "SECOND",
        "error": None,
        "served": ["stub-1"],
        "cost usd": 0.01,
        "duration ms": 7,
        "at": None,
    }


def test_running_again_asks_only_the_pairs_that_failed(tmp_path):
    folder = ask(tmp_path, Stub(fail=(2, 5)))  # b #0 and a #2
    assert sum(a["error"] is not None for a in runner.answers(folder)) == 2
    again = Stub()
    assert ask(tmp_path, again) == folder
    assert again.calls == ["second", "first"]
    assert all(a["error"] is None for a in runner.answers(folder))
    assert len(runner.answers(folder)) == 6 and len(runner.rows(folder)) == 8  # all kept
    assert [r["attempt"] for r in runner.rows(folder)][-2:] == [1, 1]
    done = Stub()
    ask(tmp_path, done)
    assert done.calls == []


def test_a_run_folder_never_mixes_two_configs(tmp_path):
    ask(tmp_path, Stub())
    with pytest.raises(ValueError, match="another config"):
        ask(tmp_path, Stub(), version="v2")

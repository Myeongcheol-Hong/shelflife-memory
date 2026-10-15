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
    assert args[args.index("--setting-sources") + 1] == ""  # no settings file
    assert "--strict-mcp-config" in args and "--mcp-config" not in args  # no MCP server
    assert args[args.index("--tools") + 1] == ""  # no tools
    assert args[args.index("--output-format") + 1] == "json"
    assert args[args.index("--system-prompt") + 1] == "Answer in one word."
    assert "--fallback-model" not in args and "--effort" not in args
    assert sent["stdin"] == "Is it raining?"  # never an argument
    folder = Path(sent["cwd"])
    assert not folder.resolve().is_relative_to(ROOT.resolve()) and not folder.exists()
    assert reply == Reply(reply.text, None, ("claude-test-1",), 0.001, 5)


def test_variables_that_change_the_login_or_the_thinking_never_reach_claude(monkeypatch):
    for name in (*runner.DROPPED_ENV, "KEEP_ME"):
        monkeypatch.setenv(name, "1")
    assert json.loads(fake()("s", "p").text)["env"] == ["KEEP_ME"]


def test_effort_is_passed_and_recorded_only_when_set():
    args = json.loads(fake(effort="low")("s", "p").text)["args"]
    assert args[args.index("--effort") + 1] == "low"
    described = {"model": "claude-test-1", "effort": "low", "claude": "9.9.9 (Claude Code)"}
    assert fake(effort="low").describe() == described


@pytest.mark.parametrize(
    ("mode", "error"),
    [
        # `claude -p` prints an unknown model's error as a result with subtype success
        ("error", "exit 1: There's an issue with the selected model."),
        ("garbage", "exit 2: boom"),
        ("other", 'served by claude-other-0: {"args"'),
    ],
)
def test_a_failed_call_or_another_model_never_counts_as_an_answer(monkeypatch, mode, error):
    monkeypatch.setenv("FAKE_CLAUDE", mode)
    reply = fake()("s", "p")
    assert reply.text is None and reply.error.startswith(error)


@pytest.mark.parametrize(
    ("reply", "code", "error"),
    [
        ({"is_error": True, "result": "API Error: 529"}, 0, "exit 0: API Error: 529"),
        ({"is_error": False, "result": "half"}, 1, "exit 1: half"),
        ({"is_error": False, "result": None}, 0, "exit 0: None"),
    ],
)
def test_is_error_the_exit_code_and_a_missing_text_each_mark_an_error(reply, code, error):
    out = json.dumps(reply | {"modelUsage": {"m": {}}})
    assert runner.parse(out, code, "", "m") == Reply(None, error, ("m",))


def test_a_call_with_no_reply_in_time_is_an_error(monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE", "sleep")
    assert fake(timeout=0.5)("s", "p") == Reply(None, "no reply in 0.5 s")


class Stub:
    """Answers each prompt in upper case; the calls numbered in `fail` fail, and so does
    every call with a prompt in `always`."""

    def __init__(self, fail=(), always=()):
        self.calls, self.fail, self.always = [], fail, always

    def describe(self):
        return {"model": "stub-1", "effort": None, "claude": "stub"}

    def __call__(self, system, prompt):
        self.calls.append(prompt)
        if len(self.calls) in self.fail or prompt in self.always:
            return Reply(None, "rate limited")
        return Reply(
            prompt.replace("x", "\u2028").upper(), served=("stub-1",), cost_usd=0.01, duration_ms=7
        )


ITEMS = [Item("a", "first"), Item("b", "second")]


def ask(tmp_path, model, version="v1", day=15, items=ITEMS):
    data = tmp_path / "labels.toml"
    data.write_text("x")
    now = lambda: datetime(2026, 10, day, 9, 0, tzinfo=UTC)  # noqa: E731
    return runner.run("demo", items, "Be brief.", version, model, [data], tmp_path / "out", now=now)


def test_a_run_asks_each_item_three_times_and_keeps_every_reply(tmp_path):
    stub = Stub()
    folder = ask(tmp_path, stub)
    assert stub.calls == ["first", "second"] * 3  # one pass over the items per repeat
    assert re.fullmatch(r"[0-9a-f]{7}-demo-stub-1-[0-9a-f]{8}", folder.name)
    config = json.loads((folder / "config.json").read_text())
    assert config["model"] == "stub-1" and config["prompt version"] == "v1"
    assert config["system prompt sha256"] == hashlib.sha256(b"Be brief.").hexdigest()
    assert (config["items"], config["repeats"], config["started at"]) == (
        2,
        3,
        "2026-10-15T09:00:00+00:00",
    )
    assert re.fullmatch(r"[0-9a-f]{40}", config["git sha"])
    assert "uncommitted changes sha256" in config
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


def test_another_config_gets_its_own_folder_and_the_same_one_resumes(tmp_path):
    first = ask(tmp_path, Stub())
    other = Stub()
    assert ask(tmp_path, other, version="v2") != first
    assert len(other.calls) == 6 and len(runner.rows(first)) == 6
    again = Stub()
    assert ask(tmp_path, again, day=16) == first and again.calls == []  # the next day too


def test_a_run_stops_after_three_failed_calls_in_a_row(tmp_path):
    folder = ask(tmp_path, Stub(fail=(1, 2, 3)))
    assert len(runner.rows(folder)) == 3
    rest = Stub()
    ask(tmp_path, rest)
    assert len(rest.calls) == 6 and all(a["error"] is None for a in runner.answers(folder))


def test_a_pair_that_always_fails_never_stops_a_resumed_run(tmp_path):
    items = [*ITEMS, Item("c", "third")]
    # The run stops at its 3 failed calls in a row: a #2, then b #2 and c #2 at a limit.
    ask(tmp_path, Stub(fail=(8, 9), always=("first",)), items=items)
    again = Stub(always=("first",))
    folder = ask(tmp_path, again, items=items)
    assert again.calls == ["first", "first", "first", "second", "third"]
    assert sum(a["error"] is None for a in runner.answers(folder)) == 6


def test_a_reply_with_a_line_separator_stays_one_row(tmp_path):
    folder = ask(tmp_path, Stub(), items=[Item("x", "a x b")])
    assert [a["text"] for a in runner.answers(folder)] == ["A \u2028 B"] * 3


def test_a_line_cut_off_mid_write_is_asked_again(tmp_path):
    folder = ask(tmp_path, Stub())
    raw = folder / "raw.jsonl"
    raw.write_text(raw.read_text()[:-20])  # the last row lost its end
    assert len(runner.rows(folder)) == 5
    again = Stub()
    ask(tmp_path, again)
    assert again.calls == ["second"] and len(runner.answers(folder)) == 6
    assert raw.read_text().endswith("\n") and len(runner.rows(folder)) == 6


def test_item_ids_must_be_unique(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        runner.run("demo", [Item("a", "x"), Item("a", "y")], "s", "v1", Stub(), [], tmp_path)


def test_the_dataset_hash_names_files_from_the_repository_root(monkeypatch):
    # So a worktree and the main checkout give the same hash for the same files.
    toml = (ROOT / "pyproject.toml").read_bytes()
    expected = hashlib.sha256(b"pyproject.toml\0" + toml).hexdigest()
    monkeypatch.chdir(ROOT / "tests")
    assert runner._files_sha256([Path("../pyproject.toml")]) == expected

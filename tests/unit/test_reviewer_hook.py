"""The pr-reviewer agent's Bash guard (.claude/hooks/reviewer-bash.sh)."""

import json
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).parents[2] / ".claude" / "hooks" / "reviewer-bash.sh"


def run(stdin):
    return subprocess.run([HOOK], input=stdin, text=True, capture_output=True).returncode


def bash(command):
    return run(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest",
        "uv run pytest -q tests/unit/test_section.py::test_split[a-b]",
        "uv run pytest -k drop_particle -x",
    ],
)
def test_allows_the_tests(command):
    assert bash(command) == 0


@pytest.mark.parametrize(
    "command",
    [
        "git diff",
        "uv run pytestx",
        "uv run pytest; rm -rf src",
        "uv run pytest && git push",
        "uv run pytest | tee out",
        "uv run pytest > out",
        "uv run pytest $(rm -rf src)",
        "uv run pytest `rm -rf src`",
        "uv run pytest -k 'a or b'",
        "uv run pytest\nrm -rf src",
    ],
)
def test_blocks_anything_else(command):
    assert bash(command) == 2


def test_blocks_input_it_cannot_read():
    assert run("not json") == 2
    assert run(json.dumps({"tool_input": {}})) == 2

"""The shared model runner (M7, D13). Every model eval asks Claude through `claude -p`
on the maintainer's subscription (design 6.3), asks each item REPEATS times, and keeps
every reply in eval/results/<run-id>/raw.jsonl, so a scorer works from the saved
replies alone and can score them again without the model.

Each call runs in a new empty folder outside the repository, with --safe-mode and no
settings files, so no CLAUDE.md, hook, plugin, skill, MCP server or settings of the
repository or the machine reaches the model; environment variables that would change
the login or the model's thinking are dropped; and the eval's own versioned system
prompt replaces Claude Code's. Claude Code still tells the model the date.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

REPEATS = 3  # each item, so results are rates (CLAUDE.md)
TIMEOUT = 600  # seconds for one call
STOP_AFTER = 3  # failed calls in a row, most likely the subscription's limit
# An API key would bill the API instead of the subscription; the others change every
# reply while config.json says the CLI's default.
DROPPED_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_EFFORT",
    "MAX_THINKING_TOKENS",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
)


@dataclass(frozen=True)
class Item:
    """One question of an eval: an id and the user message."""

    id: str
    prompt: str


@dataclass(frozen=True)
class Reply:
    text: str | None  # the answer; None whenever there is an error
    error: str | None = None
    served: tuple[str, ...] = ()  # the models that answered, from the reply's modelUsage
    cost_usd: float | None = None
    duration_ms: int | None = None


class Model(Protocol):
    def __call__(self, system: str, prompt: str) -> Reply: ...

    def describe(self) -> dict: ...


class Claude:
    """`claude -p --model <model>`, one process per call (D13). `command` is the
    executable, replaced by a fake in the tests."""

    def __init__(
        self,
        model: str,
        effort: str | None = None,
        command: tuple[str, ...] = ("claude",),
        timeout: float = TIMEOUT,
    ):
        self.model, self.effort, self.command, self.timeout = model, effort, command, timeout

    def describe(self) -> dict:
        version = subprocess.run([*self.command, "--version"], capture_output=True, text=True)
        return {"model": self.model, "effort": self.effort, "claude": version.stdout.strip()}

    def __call__(self, system: str, prompt: str) -> Reply:
        args = [*self.command, "-p", "--model", self.model, "--safe-mode", "--setting-sources", ""]
        args += ["--tools", "", "--no-session-persistence", "--output-format", "json"]
        args += ["--system-prompt", system, *(["--effort", self.effort] if self.effort else [])]
        env = {k: v for k, v in os.environ.items() if k not in DROPPED_ENV}
        # The prompt goes on stdin: one argument stops at 128 KiB on Linux, and a page
        # can be longer.
        with tempfile.TemporaryDirectory(prefix="shelflife-eval-") as folder:
            try:
                done = subprocess.run(
                    args,
                    input=prompt,
                    cwd=folder,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                return Reply(None, f"no reply in {self.timeout:g} s")
        return parse(done.stdout, done.returncode, done.stderr, self.model)


def parse(stdout: str, returncode: int, stderr: str, model: str) -> Reply:
    """A reply of `claude -p --output-format json`. A failed call (an unknown model, an
    API error) still prints a result, with subtype "success" and its error message as
    the text: is_error and the exit code decide, so an error is never an answer. Nor is
    a reply from any model but the requested one; its text is kept in the error."""
    try:
        out = json.loads(stdout)
    except json.JSONDecodeError:
        return Reply(None, f"exit {returncode}: {(stderr or stdout).strip()[:300]}")
    served = tuple(sorted(out.get("modelUsage") or {}))
    meta = {
        "served": served,
        "cost_usd": out.get("total_cost_usd"),
        "duration_ms": out.get("duration_ms"),
    }
    text = out.get("result")
    if returncode or out.get("is_error") or not isinstance(text, str):
        return Reply(None, f"exit {returncode}: {str(text)[:300]}", **meta)
    if served != (model,):  # never set --fallback-model; this catches any other switch
        return Reply(None, f"served by {', '.join(served) or 'no model'}: {text[:300]}", **meta)
    return Reply(text, **meta)


def run(
    eval_name: str,
    items: list[Item],
    system: str,
    prompt_version: str,
    model: Model,
    dataset: Iterable[Path],
    out: Path = Path("eval/results"),
    repeats: int = REPEATS,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path:
    """Ask every item `repeats` times, one pass over the items per repeat, and append
    each reply to raw.jsonl as it comes; stop after STOP_AFTER failed calls in a row.
    The folder is named after the config's hash, so running again with the same config
    continues the run: a pair (item, repeat) whose last attempt has no error is not
    asked again, one that failed is. Returns the folder."""
    if len({i.id for i in items}) != len(items):
        raise ValueError("item ids must be unique")
    diff = _git("diff", "HEAD")
    cfg = {
        "eval": eval_name,
        **model.describe(),
        "prompt version": prompt_version,
        "system prompt sha256": _sha256(system.encode()),
        "items": len(items),
        "items sha256": _sha256(json.dumps([[i.id, i.prompt] for i in items]).encode()),
        "repeats": repeats,
        "git sha": _git("rev-parse", "HEAD"),
        "uncommitted changes sha256": _sha256(diff.encode()) if diff else None,
        "dataset sha256": _files_sha256(dataset),
        "python": platform.python_version(),
    }
    key = _sha256(json.dumps(cfg, sort_keys=True).encode())[:8]
    folder = out / f"{cfg['git sha'][:7]}-{eval_name}-{cfg['model']}-{key}"
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "config.json").exists():
        cfg_out = cfg | {"started at": now().isoformat(timespec="seconds")}
        (folder / "config.json").write_text(json.dumps(cfg_out, indent=1) + "\n", "utf-8")
    raw = folder / "raw.jsonl"
    text = raw.read_text("utf-8") if raw.exists() else ""
    if not text.endswith("\n"):  # empty, or the last line was cut off mid-write
        raw.write_text(text[: text.rfind("\n") + 1], "utf-8")
    last = {(r["item"], r["repeat"]): r for r in rows(folder)}
    failed = 0
    with raw.open("a", encoding="utf-8") as lines:
        for repeat in range(repeats):
            for item in items:
                before = last.get((item.id, repeat))
                if before and before["error"] is None:
                    continue
                reply = model(system, item.prompt)
                row = {
                    "item": item.id,
                    "repeat": repeat,
                    "attempt": before["attempt"] + 1 if before else 0,
                    "prompt sha256": _sha256(item.prompt.encode()),
                    "text": reply.text,
                    "error": reply.error,
                    "served": list(reply.served),
                    "cost usd": reply.cost_usd,
                    "duration ms": reply.duration_ms,
                    "at": now().isoformat(timespec="seconds"),
                }
                lines.write(json.dumps(row, ensure_ascii=False) + "\n")
                lines.flush()
                print(f"{folder.name}: {item.id} #{repeat}: {reply.error or 'ok'}", file=sys.stderr)
                failed = failed + 1 if reply.error else 0
                if failed == STOP_AFTER:
                    print(f"stopped after {failed} failed calls in a row", file=sys.stderr)
                    return folder
    return folder


def rows(folder: Path) -> list[dict]:
    """Every attempt in raw.jsonl, in the order they were made. A last line without its
    newline was cut off mid-write and is left out; its pair is asked again."""
    raw = folder / "raw.jsonl"
    text = raw.read_text("utf-8") if raw.exists() else ""
    return [json.loads(line) for line in text[: text.rfind("\n") + 1].splitlines()]


def answers(folder: Path) -> list[dict]:
    """What a scorer reads: each pair's last attempt, failed ones included (with text
    None), so it can count them."""
    return list({(r["item"], r["repeat"]): r for r in rows(folder)}.values())


def _files_sha256(paths: Iterable[Path]) -> str:
    """Over each file's bytes and its path from the repository root, so a worktree and
    the main checkout give the same hash."""
    root = Path(_git("rev-parse", "--show-toplevel")).resolve()
    digest = hashlib.sha256()
    for path in sorted(Path(p).resolve() for p in paths):
        name = path.relative_to(root) if path.is_relative_to(root) else path
        digest.update(name.as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()

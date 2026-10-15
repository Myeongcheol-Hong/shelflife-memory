"""The shared model runner (M7, D13). Every model eval asks Claude through `claude -p`
on the maintainer's subscription (design 6.3), asks each item REPEATS times, and keeps
every reply in eval/results/<run-id>/raw.jsonl, so a scorer works from the saved
replies alone and can score them again without the model.

Each call runs in a new empty folder outside the repository, with --safe-mode, so no
CLAUDE.md, hook, plugin, skill or MCP server of the repository or the machine reaches
the model, and the eval's own versioned system prompt replaces Claude Code's.
"""

from __future__ import annotations

import hashlib
import json
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


@dataclass(frozen=True)
class Item:
    """One question of an eval: an id and the user message."""

    id: str
    prompt: str


@dataclass(frozen=True)
class Reply:
    text: str | None  # None when the call failed; kept when another model answered
    error: str | None = None  # a reply with an error never counts as an answer
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
        args = [*self.command, "-p", "--model", self.model, "--safe-mode", "--tools", ""]
        args += ["--no-session-persistence", "--output-format", "json", "--system-prompt", system]
        args += ["--effort", self.effort] if self.effort else []
        # The prompt goes on stdin: one argument stops at 128 KiB on Linux, and a page
        # can be longer.
        with tempfile.TemporaryDirectory(prefix="shelflife-eval-") as folder:
            try:
                done = subprocess.run(
                    args,
                    input=prompt,
                    cwd=folder,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                return Reply(None, f"no reply in {self.timeout:g} s")
        return parse(done.stdout, done.returncode, done.stderr, self.model)


def parse(stdout: str, returncode: int, stderr: str, model: str) -> Reply:
    """A reply of `claude -p --output-format json`. A failed call (an unknown model, an
    API error) still prints a result, with subtype "success" and its error message as
    the text: is_error and the exit code decide, so an error is never an answer."""
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
    if returncode or out.get("is_error") or not isinstance(out.get("result"), str):
        return Reply(None, f"exit {returncode}: {str(out.get('result'))[:300]}", **meta)
    if served != (model,):  # never set --fallback-model; this catches any other switch
        return Reply(out["result"], f"served by {', '.join(served) or 'no model'}", **meta)
    return Reply(out["result"], **meta)


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
    each reply to raw.jsonl as it comes. Running again with the same config continues
    the run: a pair (item, repeat) whose last attempt has no error is not asked again,
    one that failed is. A run folder never mixes two configs. Returns the folder."""
    cfg = {
        "eval": eval_name,
        **model.describe(),
        "prompt version": prompt_version,
        "system prompt sha256": _sha256(system.encode()),
        "items": len(items),
        "items sha256": _sha256(json.dumps([[i.id, i.prompt] for i in items]).encode()),
        "repeats": repeats,
        "git sha": _git("rev-parse", "HEAD"),
        "uncommitted changes": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "dataset sha256": _files_sha256(dataset),
        "python": platform.python_version(),
    }
    folder = out / f"{now():%Y-%m-%d}-{cfg['git sha'][:7]}-{eval_name}-{cfg['model']}"
    if folder.exists():
        old = json.loads((folder / "config.json").read_text())
        if {k: v for k, v in old.items() if k != "started at"} != cfg:
            raise ValueError(f"{folder} holds a run with another config; it is never mixed")
    else:
        folder.mkdir(parents=True)
        cfg_out = cfg | {"started at": now().isoformat(timespec="seconds")}
        (folder / "config.json").write_text(json.dumps(cfg_out, indent=1) + "\n")
    last = {(r["item"], r["repeat"]): r for r in rows(folder)}
    with (folder / "raw.jsonl").open("a") as raw:
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
                raw.write(json.dumps(row, ensure_ascii=False) + "\n")
                raw.flush()
                done = "ok" if reply.error is None else reply.error
                print(f"{folder.name}: {item.id} #{repeat}: {done}", file=sys.stderr)
    return folder


def rows(folder: Path) -> list[dict]:
    """Every attempt in raw.jsonl, in the order they were made."""
    raw = folder / "raw.jsonl"
    return [json.loads(line) for line in raw.read_text().splitlines()] if raw.exists() else []


def answers(folder: Path) -> list[dict]:
    """What a scorer reads: each pair's last attempt, failed ones included, so it can
    count them."""
    return list({(r["item"], r["repeat"]): r for r in rows(folder)}.values())


def _files_sha256(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(p) for p in paths):
        digest.update(path.as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()

"""M7's LLM-judged volatility policy (D14; design 6.1 and 6.0-3).

    uv run python -m eval.replay.llm_labels [--model claude-opus-5-5] [--out eval/results]
    uv run python -m eval.replay.llm_labels --rescore eval/results/<run-id>

Claude says how often each project's latest version changes, fast, medium or slow, the
maintainer's own question (D11), through the shared runner (D13), REPEATS times each,
seeing only the project's source and name. A project's label is the median of its valid
answers. One run is one model; D14 sets four, Opus 5.5 the primary. The replay then runs
per-class with Claude's labels next to per-class with the maintainer's and fixed 30, in
the uniform scenario at 1 question a week, 5 seeds, test and dev; nothing is tuned.
Running again resumes the run; once every answer is in, it scores from raw.jsonl alone,
and --rescore scores a finished run again without the model.

Both label sets use present-day knowledge of the projects' 2025-2026 releases, so the
comparison is of label quality, not foresight (D13).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from eval import runner
from eval.replay import adaptive_run, run
from eval.replay.replay import POLICIES, Counts
from eval.replay.timelines import LABELS, Project, Timeline, load_all, load_projects

# Four conditions that differ only in the model (D14); the first is the primary one, set
# before any call, and none is picked afterwards for doing best.
MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5", "claude-fable-5-1")
PROMPT_VERSION = "v2"
# The maintainer's own question and definitions when labeling (D11); per-class maps the
# classes to checks every 7, 30 or 180 days in code, not in the prompt.
SYSTEM = (
    "You say how often the latest version of a software project changes, from your own"
    " knowledge. The classes:\n"
    "- fast: the latest version changes about weekly or more often\n"
    "- medium: about monthly\n"
    "- slow: a few times a year or less\n"
    "Answer with one word: fast, medium or slow."
)
MISSING = "medium"  # a project with no valid answer: 30 days, as the label-free prior (D12)
OURS, THEIRS = "per-class, Claude's labels", "per-class, the maintainer's labels"
LIMIT = (
    "Both label sets use present-day knowledge of the projects' 2025-2026 releases, so this"
    " compares label quality, not foresight (D13)."
)


def item(project: Project) -> runner.Item:
    """The question about one project: its source and name, nothing from its timeline."""
    what = "PyPI project" if project.source == "pypi" else "GitHub repository"
    return runner.Item(
        project.name, f"How often does the latest version of the {what} {project.name} change?"
    )


def parse(text: str) -> str | None:
    """A label, if the answer is one after lowercasing and dropping surrounding space and
    a final period; otherwise None."""
    word = text.strip().lower().removesuffix(".").strip()
    return word if word in LABELS else None


def median(answers: list[str | None]) -> str | None:
    """The median of the valid answers on fast < medium < slow: with three, the majority
    when two agree and medium when all differ; of two, the faster (labeling fast as slow
    is the costlier error, design 6.0-2). None with no valid answer."""
    valid = sorted((a for a in answers if a), key=LABELS.index)
    return valid[(len(valid) - 1) // 2] if valid else None


class Unfinished(Exception):
    """Some pair (project, repeat) was never asked, or its last call failed."""


def answers(folder: Path, names: list[str], repeats: int) -> dict[str, list[str | None]]:
    """Each project's parsed answers by repeat, from raw.jsonl. A failed call is not an
    answer: until every pair's last attempt succeeded, Unfinished, and running again asks
    the missing and failed pairs (D13). So the scores never depend on how often it ran."""
    last = {(r["item"], r["repeat"]): r for r in runner.answers(folder)}
    pairs = [(n, k) for n in names for k in range(repeats)]
    if todo := [pair for pair in pairs if pair not in last or last[pair]["error"]]:
        raise Unfinished(f"{len(todo)} answers missing or failed, the first {todo[0]}")
    return {n: [parse(last[n, k]["text"]) for k in range(repeats)] for n in names}


def agreement(found: dict[str, list[str | None]], theirs: dict[str, str]) -> dict:
    """Claude's labels against the maintainer's, per project and per answer."""
    ours = {n: median(a) for n, a in found.items()}
    table = {m: {c: 0 for c in (*LABELS, "none")} for m in LABELS}
    for n, label in ours.items():
        table[theirs[n]][label or "none"] += 1
    late = [(theirs[n], ours[n]) for n in ours if n not in run.LATE_LABELED]
    return {
        "labels": ours,
        "maintainer by Claude": table,
        "projects": _shares([(theirs[n], label) for n, label in ours.items()]),
        "projects without the four labeled late": _shares(late),
        "answers": _shares([(theirs[n], a) for n, ans in found.items() for a in ans]),
        "projects whose answers all agree": sum(
            len(set(a)) == 1 and a[0] is not None for a in found.values()
        ),
        # Two valid answers that differ: the faster wins (median), which favours Claude.
        "projects decided between two different answers": sum(
            len(v := [x for x in a if x]) == 2 and v[0] != v[1] for a in found.values()
        ),
        "projects with no valid answer": sorted(n for n, label in ours.items() if not label),
    }


def _shares(pairs: list[tuple[str, str | None]]) -> dict:
    def rank(label: str) -> int:
        return LABELS.index(label)

    counts = {
        "same": sum(c == m for m, c in pairs),
        "Claude faster (more checks)": sum(c is not None and rank(c) < rank(m) for m, c in pairs),
        "Claude slower (staler)": sum(c is not None and rank(c) > rank(m) for m, c in pairs),
        "invalid": sum(c is None for _, c in pairs),
    }
    return {
        "n": len(pairs),
        **{k: {"count": v, "share": v / len(pairs)} for k, v in counts.items()},
    }


def evaluate(timelines: list[Timeline], theirs: dict, ours: dict, seeds: list[int]) -> dict:
    """Per split: the three policies; paired, Claude's labels minus the maintainer's (also
    without the four projects labeled late, D11) and minus fixed 30; and Claude's place on
    the fixed-N curve. The claims do not depend on the labels, so the replays share them."""
    base = {n: POLICIES[n] for n in ("per-class", *adaptive_run.CURVE)}
    out = {}
    for split in ("test", "dev"):
        projects: dict[str, dict[str, Counts]] = adaptive_run._projects(
            timelines, theirs, split, seeds, base
        )
        projects[THEIRS] = projects.pop("per-class")
        filled = {n: label or MISSING for n, label in ours.items()}
        mine = adaptive_run._projects(
            timelines, filled, split, seeds, {OURS: POLICIES["per-class"]}
        )
        projects |= mine
        early = {
            n: {p: c for p, c in projects[n].items() if p not in run.LATE_LABELED}
            for n in (OURS, THEIRS)
        }
        out[split] = {
            "policies": {n: run._metrics(projects[n]) for n in (OURS, THEIRS, "fixed 30")},
            "Claude's labels minus the maintainer's": run._paired(
                projects[OURS], projects[THEIRS], adaptive_run.COST
            ),
            "the same, without the four labeled late": run._paired(
                early[OURS], early[THEIRS], adaptive_run.COST
            ),
            "Claude's labels minus fixed 30": run._paired(
                projects[OURS], projects["fixed 30"], adaptive_run.COST
            ),
            "on the fixed-N curve": adaptive_run.place(projects, OURS),
        }
    return out


def score(folder: Path, data: Path, now: datetime) -> dict:
    """metrics.json of a finished run, from its raw.jsonl and the timelines alone."""
    cfg = json.loads((folder / "config.json").read_text("utf-8"))
    projects = load_projects(data / "projects.toml")
    theirs = {p.name: p.volatility for p in projects}
    found = answers(folder, [p.name for p in projects], cfg["repeats"])
    labels = agreement(found, theirs)
    replay = run.config(data, now)
    keep = ("git sha", "uncommitted changes", "dataset sha256", "python", "packaging")
    keep += ("seeds", "resamples")
    return {
        "scored": {k: replay[k] for k in keep}
        | {"at": replay["ran at"], "rate": adaptive_run.RATE},
        "answers": found,
        "agreement": labels,
        **evaluate(load_all(data), theirs, labels["labels"], replay["seeds"]),
    }


def table(metrics: dict, cfg: dict, run_id: str) -> str:
    """table.md: the labels against the maintainer's, then the replay in test and dev."""
    found = metrics["agreement"]
    lines = [f"# 6.1 LLM-judged volatility policy (M7), run {run_id}", ""]
    who = f"Claude ({cfg['model']}, prompt {cfg['prompt version']})"
    how = f"{who} said {cfg['repeats']} times how often each project's latest version changes,"
    how += " from its source and name alone. A project's label is the median of its valid"
    how += " answers, and per-class checks it every 7, 30 or 180 days (D14)."
    lines += [f"{how} {LIMIT}"]
    lines += ["", "## Labels", ""]
    header = ["Maintainer \\ Claude", *LABELS, "no valid answer"]
    rows = [[m, *map(str, found["maintainer by Claude"][m].values())] for m in LABELS]
    lines += [*run._table(header, rows), ""]
    for key in ("projects", "projects without the four labeled late", "answers"):
        shares = found[key]
        parts = [
            f"{k} {v['count']} ({100 * v['share']:.0f}%)" for k, v in shares.items() if k != "n"
        ]
        lines += [f"- {key.capitalize()}, {shares['n']}: " + ", ".join(parts) + "."]
    agree, none = found["projects whose answers all agree"], found["projects with no valid answer"]
    two = found["projects decided between two different answers"]
    lines += [f"- Projects whose answers all agree: {agree}; decided between two: {two}."]
    lines += [f"- No valid answer, so {MISSING}: {', '.join(none) or 'none'}.", ""]
    for split in ("test", "dev"):
        part = metrics[split]
        seeds = len(metrics["scored"]["seeds"])
        where = f"uniform, {adaptive_run.RATE}, seeds: {seeds}, 95% intervals over projects"
        lines += [f"## {split.capitalize()} ({where})", ""]
        lines += [*adaptive_run._policies(part["policies"]), ""]
        rows = [[k, *adaptive_run._differences(part[k])] for k in part if " minus " in k]
        header = ["Paired, on the same claims", "Stale-answer rate", "Stale claim-days"]
        lines += [*run._table([*header, "Checks per claim-month"], rows), ""]
        lines += [adaptive_run._curve_line(OURS, part["on the fixed-N curve"]), ""]
    return "\n".join(lines[:-1]) + "\n"


def main(
    argv: list[str] | None = None,
    model: runner.Model | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = argparse.ArgumentParser(prog="llm_labels", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("eval/data/timelines"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    parser.add_argument("--model", default=MODELS[0], help="the primary condition by default")
    parser.add_argument("--rescore", type=Path, help="score a finished run again; no model")
    args = parser.parse_args(argv)
    folder = args.rescore
    if folder is None:
        projects = load_projects(args.data / "projects.toml")
        items = [item(p) for p in projects]
        model = model or runner.Claude(args.model)
        dataset = [args.data / "projects.toml"]
        folder = runner.run(
            "llm-labels", items, SYSTEM, PROMPT_VERSION, model, dataset, args.out, now=now
        )
    try:
        metrics = score(folder, args.data, now())
    except Unfinished as error:
        print(f"{folder}: {error}; run again to ask them", file=sys.stderr)
        return 1
    cfg = json.loads((folder / "config.json").read_text("utf-8"))
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n", "utf-8")
    (folder / "table.md").write_text(table(metrics, cfg, folder.name), "utf-8")
    print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

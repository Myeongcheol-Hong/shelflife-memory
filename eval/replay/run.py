"""Run the 6.1 replay and write eval/results/<run-id>/ (M6, D12).

    uv run python -m eval.replay.run [--out eval/results]

Every split, creation scenario and question rate, all policies, 5 seeds. It writes
config.json (git SHA, dataset hash, Python and packaging versions, the D12 parameters),
metrics.json (each metric with its 95% interval) and table.md. The same code and data
give the same numbers, so the per-claim rows are not kept (D12).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from eval.replay import score
from eval.replay.replay import (
    CLAIMS_PER_PROJECT,
    FIXED,
    JITTERED,
    POLICIES,
    QUESTION_RATES,
    SESSION,
    SPLITS,
    Counts,
    Row,
    changes_per_year,
    replay,
    truth,
)
from eval.replay.timelines import LABELS, Timeline, load_all, load_projects

SEEDS = [0, 1, 2, 3, 4]
SCENARIOS = ("uniform", "sessions")
HEADLINE = ("test", "uniform", "1 a week")
LATE_LABELED = {"gohugoio/hugo", "jesseduffield/lazygit", "starship/starship", "zed-industries/zed"}
NOT_WORSE = 0.005  # the stale-answer rate may rise this much at its interval's upper end
BUCKETS = ("0 changes a year", "under 6", "6 to 52", "over 52")
ROWS = ("oracle", "every read", *(f"fixed {n}" for n in FIXED))


def run(timelines: list[Timeline], labels: dict[str, str], seeds: list[int] = SEEDS) -> dict:
    """metrics.json: every split, scenario and question rate, then jitter's comparisons."""
    out: dict[str, Any] = {}
    jitter_rows = {}
    for split in SPLITS:
        groups = _groups(timelines, labels, split)
        for scenario in SCENARIOS:
            for rate, per_day in QUESTION_RATES.items():
                rows = replay(timelines, labels, split, seeds, per_day, scenario=scenario)
                headline = (split, rate) == (HEADLINE[0], HEADLINE[2])
                out[f"{split} / {scenario} / {rate}"] = _summary(
                    rows, split, groups if headline else {}
                )
                if headline:
                    jitter_rows[scenario] = rows
    out["jitter"] = _jitter(jitter_rows, HEADLINE[0])
    return out


def _groups(timelines: list[Timeline], labels: dict[str, str], split: str) -> dict[str, set[str]]:
    """The subsets reported on their own: each label, each observed change rate (D12), and
    all projects but the four labeled after the first collection run (D11)."""
    rates = {t.project: bucket(changes_per_year(truth(t, split), split)) for t in timelines}
    groups = {label: {p for p, x in labels.items() if x == label} for label in LABELS}
    groups |= {name: {p for p, b in rates.items() if b == name} for name in BUCKETS}
    groups["without the late-labeled four"] = set(labels) - LATE_LABELED
    return groups


def bucket(per_year: float) -> str:
    """D12's change-rate group: 0, under 6, 6 to 52, or over 52 changes a year."""
    if per_year == 0:
        return BUCKETS[0]
    return BUCKETS[1] if per_year < 6 else BUCKETS[2] if per_year <= 52 else BUCKETS[3]


def _summary(rows: list[Row], split: str, groups: dict[str, set[str]]) -> dict:
    out = {}
    for name in POLICIES:
        projects = score.per_project(rows, name)
        peak, to_mean = score.peak(rows, name, split)
        out[name] = _metrics(projects) | {"peak per day": peak, "peak to mean": to_mean}
        if groups:
            out[name]["groups"] = {
                group: _metrics({p: c for p, c in projects.items() if p in members})
                for group, members in groups.items()
            }
    return out


def _metrics(projects: dict[str, Counts]) -> dict:
    total = score.total(projects)
    found = {"projects": len(projects), "claims": total.claims}
    for metric in score.METRICS:
        found[metric] = {"value": score.value(metric, total), "ci": score.ci(metric, projects)}
    return found


def _jitter(rows_by_scenario: dict[str, list[Row]], split: str) -> dict:
    """Each policy with jitter minus without, paired. The primary comparison (D12):
    per-class in the sessions scenario; jitter helps if the peak's difference lies below
    zero and the stale-answer rate's rises at most NOT_WORSE at its interval's upper end."""
    out: dict[str, Any] = {}
    for scenario, rows in rows_by_scenario.items():
        for name in JITTERED:
            on, off = score.per_project(rows, f"{name} + jitter"), score.per_project(rows, name)
            peaks = (
                score.peak(rows, f"{name} + jitter", split)[0] - score.peak(rows, name, split)[0]
            )
            found = {
                "peak per day": {
                    "value": peaks,
                    "ci": score.peak_ci(rows, f"{name} + jitter", split, name),
                }
            }
            for metric in ("stale-answer rate", "stale claim-days"):
                value = score.value(metric, score.total(on)) - score.value(metric, score.total(off))
                found[metric] = {"value": value, "ci": score.ci(metric, on, minus=off)}
            out[f"{scenario} / {name}"] = found
    out["primary: helps"] = helps(out["sessions / per-class"])
    return out


def helps(found: dict) -> bool:
    """D12's rule: the peak's paired difference lies below zero, and the stale-answer
    rate's rises at most NOT_WORSE at its interval's upper end."""
    return found["peak per day"]["ci"][1] < 0 and found["stale-answer rate"]["ci"][1] <= NOT_WORSE


def table(metrics: dict, run_id: str) -> str:
    """table.md: the headline, every read across question rates, jitter, the breakdowns."""
    head, dev = metrics[" / ".join(HEADLINE)], metrics["dev / uniform / 1 a week"]
    lines = [f"# 6.1 replay, run {run_id}", "", _caption(*HEADLINE, head), "", *_policies(head)]
    lines += ["", "## Every read at each question rate (test, uniform)", "", *_every_read(metrics)]
    lines += ["", "## Jitter, with minus without, paired (test, 1 a week)", ""]
    lines += _jitter_table(metrics["jitter"])
    lines += ["", "## By label and by observed change rate (test, uniform, 1 a week)", ""]
    lines += _groups_table(head)
    lines += ["", "## Dev split (not compared with test: dev claims live shorter)", ""]
    lines += [_caption("dev", "uniform", "1 a week", dev), "", *_policies(dev)]
    lines += ["", "## Claims in each results row (per seed, averaged over the seeds)", ""]
    lines += [*_claims(metrics), "", "Projects counts those with a claim in the split."]
    return "\n".join(lines) + "\n"


def _claims(metrics: dict) -> list[str]:
    """Each row's projects and claims, and the claims no session could take (D12)."""
    rows = []
    for key, summary in metrics.items():
        if key != "jitter":
            projects, claims = summary["never"]["projects"], summary["never"]["claims"]
            dropped = CLAIMS_PER_PROJECT * projects - claims
            rows.append([key, str(projects), f"{claims:.1f}", f"{dropped:.1f}"])
    header = ["Split / scenario / questions", "Projects", "Claims", "Dropped (of 20 a project)"]
    return _table(header, rows)


def _every_read(metrics: dict) -> list[str]:
    checks, _, days, detect, _ = COLUMNS
    header = [
        "Questions",
        "Checks per claim-month",
        "Stale claim-days",
        "Days to detect (undetected)",
    ]
    rows = []
    for rate in QUESTION_RATES:
        m = metrics[f"test / uniform / {rate}"]["every read"]
        rows.append([rate, checks(m), days(m), detect(m)])
    return _table(header, rows)


def _jitter_table(jitter: dict) -> list[str]:
    rows = [
        [
            key + (" (primary)" if key == "sessions / per-class" else " (exploratory)"),
            _num(v["peak per day"]),
            _pct(v["stale-answer rate"]),
            _pct(v["stale claim-days"]),
        ]
        for key, v in jitter.items()
        if isinstance(v, dict)
    ]
    verdict = "helps" if jitter["primary: helps"] else "does not help"
    header = ["Scenario / policy", "Peak per day", "Stale-answer rate", "Stale claim-days"]
    return [
        *_table(header, rows),
        "",
        f"Primary comparison (D12), sessions / per-class: jitter {verdict}.",
    ]


def _groups_table(head: dict) -> list[str]:
    checks, _, days, _, _ = COLUMNS
    header = ["Group", "Projects", "Per-class: stale claim-days", "Checks per claim-month"]
    header += ["Fixed 30: stale claim-days", "Checks per claim-month"]
    rows = []
    for g in [*LABELS, *BUCKETS]:
        a, b = head["per-class"]["groups"][g], head["fixed 30"]["groups"][g]
        rows.append([g, str(a["projects"]), days(a), checks(a), days(b), checks(b)])
    return _table(header, rows)


def _caption(split: str, scenario: str, rate: str, summary: dict) -> str:
    claims, projects = summary["never"]["claims"], summary["never"]["projects"]
    return (
        f"{split.capitalize()} split, {scenario} scenario, questions {rate} per claim;"
        f" {claims:.0f} claims about {projects} projects per seed. 95%"
        " intervals over resampled projects (D12). Days to detect counts only the changes"
        " found; the share left undetected follows it."
    )


def _policies(summary: dict) -> list[str]:
    rows = [[name, *(f(summary[name]) for f in COLUMNS)] for name in (*ROWS, "per-class")]
    if late := summary["per-class"].get("groups", {}).get("without the late-labeled four"):
        rows.append(
            ["per-class without lazygit, starship, zed, hugo", *(f(late) for f in COLUMNS[:4]), "-"]
        )
    rows.append(["never", *(f(summary["never"]) for f in COLUMNS)])
    header = ["Policy", "Checks per claim-month", "Stale-answer rate", "Stale claim-days"]
    return _table([*header, "Days to detect (undetected)", "Peak per day (to mean)"], rows)


def _num(m: dict, ci: bool = True) -> str:
    if m["value"] is None:
        return "-"
    return f"{m['value']:.2f}" + (
        f" ({m['ci'][0]:.2f} to {m['ci'][1]:.2f})" if ci and m["ci"] else ""
    )


def _pct(m: dict, ci: bool = True) -> str:
    if m["value"] is None:
        return "-"
    text = f"{100 * m['value']:.1f}%"
    return text + (f" ({100 * m['ci'][0]:.1f} to {100 * m['ci'][1]:.1f})" if ci and m["ci"] else "")


COLUMNS: list[Callable[[dict], str]] = [
    lambda m: _num(m["checks per claim-month"]),
    lambda m: _pct(m["stale-answer rate"]),
    lambda m: _pct(m["stale claim-days"]),
    lambda m: (
        f"{_num(m['mean days to detect'], ci=False)} ({_pct(m['undetected share'], ci=False)})"
    ),
    lambda m: f"{m['peak per day']:.0f} (x{m['peak to mean']:.1f})",
]


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(row) + " |" for row in rows]


def config(timelines_dir: Path, now: datetime) -> dict:
    """What ran: enough to tell two runs apart and to run this one again."""
    sha = _git("rev-parse", "HEAD")
    digest = hashlib.sha256()  # over the files load_projects() and load_all() read
    for path in [timelines_dir / "projects.toml", *sorted(timelines_dir.glob("*/*.jsonl"))]:
        digest.update(path.relative_to(timelines_dir).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return {
        "run": f"{now:%Y-%m-%d}-{sha[:7]}",
        "ran at": now.isoformat(timespec="seconds"),
        "git sha": sha,
        "uncommitted changes": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "dataset sha256": digest.hexdigest(),
        "python": platform.python_version(),
        "packaging": version("packaging"),
        "decision": "D12",
        "seeds": SEEDS,
        "claims per project": CLAIMS_PER_PROJECT,
        "question rates per claim-day": QUESTION_RATES,
        "session size": SESSION,
        "splits": {name: [str(day) for day in days] for name, days in SPLITS.items()},
        "policies": list(POLICIES),
        "resamples": score.RESAMPLES,
    }


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def main(
    argv: list[str] | None = None, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> int:
    parser = argparse.ArgumentParser(prog="run", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("eval/data/timelines"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    args = parser.parse_args(argv)
    labels = {p.name: p.volatility for p in load_projects(args.data / "projects.toml")}
    cfg = config(args.data, now())
    folder = args.out / cfg["run"]
    if folder.exists():
        print(f"error: {folder} exists; a run never overwrites another", file=sys.stderr)
        return 1
    metrics = run(load_all(args.data), labels, cfg["seeds"])
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps(cfg, indent=1) + "\n")
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")
    (folder / "table.md").write_text(table(metrics, cfg["run"]))
    print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

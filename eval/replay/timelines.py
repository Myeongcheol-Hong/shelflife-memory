"""Release timelines, the ground truth of the 6.1 replay (M5a, D11).

A timeline is one project's releases as `collect_timelines` stored them: every PyPI
version with its first upload, or every published GitHub release. `latest_on()` says what
the source showed as the latest version on a given day, by the rules the pypi and
github_release verifiers read, and `changes()` lists the days that answer changed. No
network here: tests and CI run it on eval/data/smoke/.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from packaging.version import InvalidVersion, Version

from shelflife.verifiers import github_release, pypi

SOURCES = ("pypi", "github")
LABELS = ("fast", "medium", "slow")  # the maintainer's volatility labels; "" until labeled
# The split (design 6.1, D11): tune on dev, report on test. By time only: each replayed
# claim starts with no history, so nothing a policy learns in dev carries into test.
DEV = (date(2024, 1, 1), date(2024, 12, 31))
TEST = (date(2025, 1, 1), date(2026, 9, 30))


@dataclass(frozen=True)
class Project:
    source: str  # pypi | github
    name: str  # a PyPI project name, or owner/repo
    volatility: str  # the maintainer's label, "" until labeled

    @property
    def path(self) -> str:
        """Where its timeline is stored, relative to the timelines folder."""
        return f"{self.source}/{self.name.replace('/', '__')}.jsonl"


@dataclass(frozen=True)
class Release:
    version: str  # the PyPI version or the GitHub tag, as the source writes it
    published: datetime  # UTC: PyPI's first upload of the version, GitHub's published_at
    yanked: bool = False  # PyPI: every file of the version was yanked by collection time
    prerelease: bool = False  # GitHub's flag; PyPI's comes from the version (PEP 440)
    created: datetime | None = None  # GitHub's created_at, which orders "latest"


@dataclass(frozen=True)
class Timeline:
    source: str
    project: str
    collected_at: datetime
    latest_at_collection: str | None  # what the source called latest when collected
    releases: tuple[Release, ...]


def latest_on(timeline: Timeline, day: date) -> str | None:
    """The version the source showed as latest at the end of `day` (UTC), or None.

    PyPI, as its `info.version`: the highest version by PEP 440 among those uploaded by
    then and not yanked, leaving out pre-releases unless there is nothing else; a version
    PEP 440 cannot read is left out. GitHub, as `/releases/latest`: among releases
    published by then and not marked pre-release, the one created last.
    """
    end = datetime.combine(day, time.max, UTC)
    out = [r for r in timeline.releases if r.published <= end]
    if timeline.source == "github":
        stable = [r for r in out if not r.prerelease]
        if not stable:
            return None
        return max(stable, key=lambda r: (r.created or r.published, r.published)).version
    versions = []
    for r in out:
        if r.yanked:
            continue
        try:
            versions.append((Version(r.version), r.version))
        except InvalidVersion:
            continue
    stable = [v for v in versions if not v[0].is_prerelease]
    pool = stable or versions
    return max(pool)[1] if pool else None


def changes(timeline: Timeline, start: date, end: date) -> list[tuple[date, str | None]]:
    """The days in [start, end] on which latest_on() changed, each with the new latest.

    The latest can change only on a day a release was published: a yank's date is not
    known, so a yanked version never counts.
    """
    days = sorted({r.published.date() for r in timeline.releases})
    current = latest_on(timeline, start - timedelta(days=1))
    found = []
    for day in (d for d in days if start <= d <= end):
        latest = latest_on(timeline, day)
        if latest != current:
            found.append((day, latest))
            current = latest
    return found


def split_of(day: date) -> str | None:
    """ "dev", "test", or None for a day outside both."""
    for name, (first, last) in (("dev", DEV), ("test", TEST)):
        if first <= day <= last:
            return name
    return None


def problems(timeline: Timeline) -> list[str]:
    """What does not add up: the rules disagree with what the source called latest when
    it was collected (a GitHub release marked latest by hand, a version PEP 440 cannot
    read), or GitHub tags that look like several packages' (a monorepo)."""
    found = []
    ours = latest_on(timeline, timeline.collected_at.date())
    if ours != timeline.latest_at_collection:
        found.append(
            f"latest by our rules is {ours}, the source said {timeline.latest_at_collection}"
        )
    if timeline.source == "github":
        prefixes = {_tag_prefix(r.version) for r in timeline.releases}
        if len(prefixes) > 1:
            found.append(f"tags with several prefixes (per-package tags?): {sorted(prefixes)[:5]}")
    return found


def _tag_prefix(tag: str) -> str:
    """The part of a tag before its version number: "graphiti-" in "graphiti-0.3.1"."""
    m = re.match(r"(.*?)v?\d", tag)
    return m[1].lower() if m else tag.lower()


def load_projects(path: Path) -> list[Project]:
    """projects.toml: `pypi` and `github` lists of {name, volatility} tables. Raises
    ValueError on an unknown key, a malformed name, an unknown label or a duplicate."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if unknown := set(data) - set(SOURCES):
        raise ValueError(f"{path}: unknown keys {sorted(unknown)}")
    projects, seen = [], set()
    for source in SOURCES:
        for entry in data.get(source, []):
            name, label = entry.get("name", ""), entry.get("volatility", "")
            valid = pypi.NAME if source == "pypi" else github_release.REPO
            if not isinstance(name, str) or not valid.fullmatch(name):
                raise ValueError(f"{path}: not a {source} name: {name!r}")
            if label not in ("", *LABELS):
                raise ValueError(f"{path}: {name}: volatility must be one of {LABELS} or empty")
            key = (source, re.sub(r"[-_.]+", "-", name.lower()))  # PEP 503 for PyPI
            if key in seen:
                raise ValueError(f"{path}: {name} is listed twice")
            seen.add(key)
            projects.append(Project(source, name, label))
    return projects


def load(path: Path) -> Timeline:
    """One timeline file: a header line, then one release per line (JSON Lines)."""
    try:
        header, *rows = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
        if header["source"] not in SOURCES:
            raise ValueError(f"unknown source {header['source']!r}")
        releases = tuple(
            Release(
                version=row["version"],
                published=_utc(row["published"]),
                yanked=bool(row.get("yanked", False)),
                prerelease=bool(row.get("prerelease", False)),
                created=_utc(row["created"]) if row.get("created") else None,
            )
            for row in rows
        )
        return Timeline(
            header["source"],
            header["project"],
            _utc(header["collected_at"]),
            header["latest_at_collection"],
            releases,
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"{path}: {e}") from None


def load_all(folder: Path) -> list[Timeline]:
    return [load(p) for p in sorted(folder.glob("*/*.jsonl"))]


def _utc(text: str) -> datetime:
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError(f"time without a time zone: {text!r}")
    return moment.astimezone(UTC)

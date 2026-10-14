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
from collections import Counter
from collections.abc import Callable
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
    tag: str | None = None  # GitHub: a regex a release's tag must match, else ignored

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
    # GitHub's created_at, which orders "latest", as of collection: it moves with its tag,
    # so it can be later than `published` (replayed as `published`, _created())
    created: datetime | None = None


@dataclass(frozen=True)
class Timeline:
    source: str
    project: str
    collected_at: datetime
    latest_at_collection: str | None  # what the source called latest when collected
    releases: tuple[Release, ...]
    tag: str | None = None  # the project's tag pattern when it was collected


def counted(timeline: Timeline) -> list[Release]:
    """The releases the rules read: all of them, or with a tag pattern only those whose
    tag matches it (`re.search`), so a repository's other products are left out."""
    if timeline.tag is None:
        return list(timeline.releases)
    return [r for r in timeline.releases if re.search(timeline.tag, r.version)]


def latest_on(timeline: Timeline, day: date) -> str | None:
    """The version the source showed as latest at the end of `day` (UTC), or None.

    PyPI, as its `info.version`: the highest version by PEP 440 among those uploaded by
    then and not yanked, leaving out pre-releases unless there is nothing else; a version
    PEP 440 cannot read is left out. GitHub, as `/releases/latest`: among releases
    published by then and not marked pre-release, the one created last (_created()).
    Releases outside the tag pattern never count (counted()).
    """
    end = datetime.combine(day, time.max, UTC)
    out = [r for r in counted(timeline) if r.published <= end]
    if timeline.source == "github":
        return _created_last(out, _created)
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
    days = sorted({r.published.date() for r in counted(timeline)})
    current = latest_on(timeline, start - timedelta(days=1))
    found = []
    for day in (d for d in days if start <= d <= end):
        latest = latest_on(timeline, day)
        if latest != current:
            found.append((day, latest))
            current = latest
    return found


def problems(timeline: Timeline) -> list[str]:
    """What the collector reports for the maintainer to look at:
    - the rules disagree with what the source called latest when it was collected (a
      version PEP 440 cannot read, a GitHub release marked latest by hand), or the
      source's latest is outside the tag pattern (the github_release verifier reads it);
    - the first release comes after the replay starts (a young project, or a release
      list cut short);
    - GitHub tags with several prefixes (a monorepo's per-package tags);
    - GitHub days in the replay when the release created last, which the rule picks, is
      not the one published last. GitHub marks a newly published release latest by
      default (`make_latest`), so on those days a backport may have been the latest.
    """
    found = []
    if timeline.source == "github":  # GitHub read created_at as it was then, not clamped
        ours = _created_last(counted(timeline), lambda r: r.created or r.published)
    else:
        ours = latest_on(timeline, timeline.collected_at.date())
    theirs = timeline.latest_at_collection
    if timeline.tag and theirs and not re.search(timeline.tag, theirs):
        found.append(f"the source's latest, {theirs}, is outside the tag pattern {timeline.tag}")
    elif ours != theirs:
        found.append(f"latest by our rules is {ours}, the source said {theirs}")
    releases = counted(timeline)
    if releases and (first := min(r.published for r in releases)).date() > DEV[0]:
        found.append(f"first release on {first.date()}, after the replay starts")
    if timeline.source == "github":
        prefixes = {tag_prefix(r.version) for r in releases}
        if len(prefixes) > 1:
            found.append(f"tags with several prefixes (per-package tags?): {sorted(prefixes)[:5]}")
        if twice := sorted(v for v, n in Counter(r.version for r in releases).items() if n > 1):
            found.append(f"tags listed more than once: {twice[:5]}")
        disputed = [
            day
            for day in _publish_days(timeline)
            if _published_last(timeline, day) != latest_on(timeline, day)
        ]
        if disputed:
            found.append(
                f"{len(disputed)} days when the release created last was not the one published"
                f" last, first {disputed[0]}: GitHub may have shown the other as latest"
            )
    return found


def _publish_days(timeline: Timeline) -> list[date]:
    """The days in the replay (DEV to TEST) on which a release was published."""
    days = {r.published.date() for r in counted(timeline)}
    return sorted(d for d in days if DEV[0] <= d <= TEST[1])


def _published_last(timeline: Timeline, day: date) -> str | None:
    end = datetime.combine(day, time.max, UTC)
    stable = [r for r in counted(timeline) if r.published <= end and not r.prerelease]
    if not stable:
        return None
    return max(stable, key=lambda r: (r.published, _created(r), r.version)).version  # ties


def _created(r: Release) -> datetime:
    """A GitHub release's created_at for replaying a past day: no later than its publish
    time. The stored created_at is today's and moves with the tag, so a later one is a
    timestamp from after the release (ollama's v0.40.0 was published 2026-09-25 and
    shows 2026-10-06)."""
    return min(r.created, r.published) if r.created else r.published


def _created_last(releases: list[Release], created: Callable[[Release], datetime]) -> str | None:
    """The stable release created last; a tie goes to the one published last, then to the
    larger tag, so the answer never depends on the order of the rows."""
    stable = [r for r in releases if not r.prerelease]
    if not stable:
        return None
    return max(stable, key=lambda r: (created(r), r.published, r.version)).version


def tag_prefix(tag: str) -> str:
    """The part of a tag before its version number: "graphiti-" in "graphiti-0.3.1"."""
    m = re.match(r"(.*?)v?\d", tag)
    return m[1].lower() if m else tag.lower()


def load_projects(path: Path) -> list[Project]:
    """projects.toml: `pypi` and `github` lists of {name, volatility, tag} tables, `tag`
    only for GitHub. Raises ValueError on an unknown key, a malformed name, an unknown
    label, a tag pattern that is empty or not a regular expression, or a duplicate."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if unknown := set(data) - set(SOURCES):
        raise ValueError(f"{path}: unknown keys {sorted(unknown)}")
    projects, seen = [], set()
    for source in SOURCES:
        for entry in data.get(source, []):
            if unknown := set(entry) - {"name", "volatility", "tag"}:
                raise ValueError(f"{path}: {entry.get('name')}: unknown keys {sorted(unknown)}")
            name, label, tag = entry.get("name", ""), entry.get("volatility", ""), entry.get("tag")
            valid = pypi.NAME if source == "pypi" else github_release.REPO
            if not isinstance(name, str) or not valid.fullmatch(name):
                raise ValueError(f"{path}: not a {source} name: {name!r}")
            if label not in ("", *LABELS):
                raise ValueError(f"{path}: {name}: volatility must be one of {LABELS} or empty")
            if tag is not None:
                bad_tag = f"{path}: {name}: tag must be a regular expression, for GitHub"
                if source != "github" or not isinstance(tag, str) or not tag:
                    raise ValueError(bad_tag)
                try:
                    re.compile(tag)
                except re.error:
                    raise ValueError(bad_tag) from None
            folded = re.sub(r"[-_.]+", "-", name.lower()) if source == "pypi" else name.lower()
            key = (source, folded)  # PyPI names compare under PEP 503, GitHub's ignore case
            if key in seen:
                raise ValueError(f"{path}: {name} is listed twice")
            seen.add(key)
            projects.append(Project(source, name, label, tag))
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
                published=parse_utc(row["published"]),
                yanked=bool(row.get("yanked", False)),
                prerelease=bool(row.get("prerelease", False)),
                created=parse_utc(row["created"]) if row.get("created") else None,
            )
            for row in rows
        )
        return Timeline(
            header["source"],
            header["project"],
            parse_utc(header["collected_at"]),
            header["latest_at_collection"],
            releases,
            header.get("tag"),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"{path}: {e}") from None


def load_all(folder: Path) -> list[Timeline]:
    return [load(p) for p in sorted(folder.glob("*/*.jsonl"))]


def utc_text(moment: datetime) -> str:
    """A time as the timeline files write it: UTC to the second ("2024-11-25T20:41:56Z")."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime:
    """A source's or a file's ISO time as UTC; ValueError without a time zone."""
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError(f"time without a time zone: {text!r}")
    return moment.astimezone(UTC)

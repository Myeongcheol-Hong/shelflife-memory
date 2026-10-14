"""Collect the release timelines from PyPI and GitHub (M5a, D11).

Runs on the maintainer's Mac, because cloud sessions cannot call the GitHub API for
repositories not attached to them:

    uv run python -m eval.replay.collect_timelines [FOLDER]

FOLDER (default eval/data/timelines) holds projects.toml. Each project's timeline is
written next to it, as pypi/<name>.jsonl or github/<owner>__<repo>.jsonl: a header line,
then one line per release with only its version, dates and flags. It refuses to run
while a project has no volatility label, so the labels are made before any data is seen.
GITHUB_TOKEN, if set, raises GitHub's limit of 60 requests an hour.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.replay.timelines import Project, load, load_projects, problems
from shelflife.verifiers import Fetch, FetchError, http_get

SCRIPT_VERSION = "t1"
PER_PAGE = 100  # GitHub's largest page
GITHUB_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def collect_pypi(name: str, fetch: Fetch) -> tuple[str, str | None, list[dict[str, Any]]]:
    """(url, latest, releases) from PyPI's JSON API. A version's date is its first file's
    upload; a version with no files is left out (it was never installable); it is yanked
    when all its files are."""
    url = f"https://pypi.org/pypi/{name}/json"
    data = json.loads(fetch(url, {}))
    releases = [
        {
            "version": version,
            "published": min(_iso(f["upload_time_iso_8601"]) for f in files),
            "yanked": all(f.get("yanked", False) for f in files),
        }
        for version, files in data["releases"].items()
        if files
    ]
    return url, data["info"]["version"], releases


def collect_github(
    repo: str, fetch: Fetch, token: str | None
) -> tuple[str, str | None, list[dict[str, Any]]]:
    """(url, latest, releases) from GitHub's REST API, page by page. Drafts and releases
    never published are left out."""
    headers = GITHUB_HEADERS | ({"Authorization": f"Bearer {token}"} if token else {})
    base = f"https://api.github.com/repos/{repo}/releases"
    releases = []
    for page in itertools.count(1):
        batch = json.loads(fetch(f"{base}?per_page={PER_PAGE}&page={page}", headers))
        releases += [
            {
                "version": r["tag_name"],
                "published": _iso(r["published_at"]),
                "created": _iso(r["created_at"]),
                "prerelease": bool(r["prerelease"]),
            }
            for r in batch
            if not r.get("draft") and r.get("published_at")
        ]
        if len(batch) < PER_PAGE:
            break
    try:
        latest = json.loads(fetch(f"{base}/latest", headers))["tag_name"]
    except FetchError as e:
        if e.status != 404:  # 404: no release is marked latest
            raise
        latest = None
    return base, latest, releases


def write(
    folder: Path,
    project: Project,
    url: str,
    latest: str | None,
    releases: list[dict[str, Any]],
    now: datetime,
) -> Path:
    """The timeline file: a header line, then the releases oldest first."""
    header = {
        "source": project.source,
        "project": project.name,
        "url": url,
        "collected_at": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_at_collection": latest,
        "script": SCRIPT_VERSION,
    }
    rows = sorted(releases, key=lambda r: (r["published"], r["version"]))
    path = folder / project.path
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(header, ensure_ascii=False)]
    lines += [json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(
    argv: list[str] | None = None,
    fetch: Fetch = http_get,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = argparse.ArgumentParser(prog="collect_timelines", description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=Path("eval/data/timelines"))
    args = parser.parse_args(argv)
    projects = load_projects(args.folder / "projects.toml")
    if unlabeled := [p.name for p in projects if not p.volatility]:
        print(
            f"error: {len(unlabeled)} projects have no volatility label (first: "
            f"{unlabeled[0]}). Label every project before collecting.",
            file=sys.stderr,
        )
        return 1
    token = os.environ.get("GITHUB_TOKEN")
    failed = 0
    for project in projects:
        try:
            if project.source == "pypi":
                url, latest, releases = collect_pypi(project.name, fetch)
            else:
                url, latest, releases = collect_github(project.name, fetch, token)
            path = write(args.folder, project, url, latest, releases, now())
        except (FetchError, KeyError, TypeError, ValueError) as e:
            print(f"error: {project.source} {project.name}: {e}", file=sys.stderr)
            failed += 1
            continue
        print(f"{project.source} {project.name}: {len(releases)} releases")
        for problem in problems(load(path)):
            print(f"  check: {problem}")
    return 1 if failed else 0


def _iso(text: str) -> str:
    """A source's timestamp as UTC to the second ("2024-11-25T20:41:56Z")."""
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError(f"time without a time zone: {text!r}")
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    sys.exit(main())

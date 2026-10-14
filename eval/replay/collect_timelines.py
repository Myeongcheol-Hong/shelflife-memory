"""Collect the release timelines from PyPI and GitHub (M5a, D11).

Runs on the maintainer's Mac, because cloud sessions cannot call the GitHub API for
repositories not attached to them:

    uv run python -m eval.replay.collect_timelines [FOLDER]

FOLDER (default eval/data/timelines) holds projects.toml. Each project's timeline is
written next to it, as pypi/<name>.jsonl or github/<owner>__<repo>.jsonl: a header line,
then one line per release with only its version, dates and flags. It refuses to run
while a project has no volatility label, so the labels are made before any data is seen.
A GitHub project with a tag pattern keeps only the releases whose tag matches it.
GITHUB_TOKEN, if set, raises GitHub's limit of 60 requests an hour.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.replay.timelines import (
    Project,
    load,
    load_projects,
    parse_utc,
    problems,
    tag_prefix,
    utc_text,
)
from shelflife.verifiers import Fetch, FetchError, TooLarge, http_get

SCRIPT_VERSION = "t1"
PER_PAGE = 100  # GitHub's largest page
MIN_PER_PAGE = 10  # the smallest page tried when a page is over the size cap
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
            "published": utc_text(min(parse_utc(f["upload_time_iso_8601"]) for f in files)),
            "yanked": all(f.get("yanked", False) for f in files),
        }
        for version, files in data["releases"].items()
        if files
    ]
    return url, data["info"]["version"], releases


def collect_github(
    repo: str, fetch: Fetch, token: str | None
) -> tuple[str, str | None, list[dict[str, Any]]]:
    """(url, latest, releases) from GitHub's REST API, page by page. Drafts are left out
    (a token with push access would list them). Each release lists its assets, so a page
    can be over the 10 MB cap (caddy's): then the listing starts again from page 1 with
    half the page size, down to MIN_PER_PAGE, so the page offsets stay consistent."""
    headers = GITHUB_HEADERS | ({"Authorization": f"Bearer {token}"} if token else {})
    base = f"https://api.github.com/repos/{repo}/releases"
    per_page = PER_PAGE
    while True:
        try:
            releases = _all_pages(base, per_page, fetch, headers)
            break
        except TooLarge:
            if per_page <= MIN_PER_PAGE:
                raise
            per_page = max(per_page // 2, MIN_PER_PAGE)
    try:
        latest = json.loads(fetch(f"{base}/latest", headers))["tag_name"]
    except FetchError as e:
        if e.status != 404:  # 404: no release is marked latest
            raise
        latest = None
    return base, latest, releases


def _all_pages(
    base: str, per_page: int, fetch: Fetch, headers: dict[str, str]
) -> list[dict[str, Any]]:
    releases, page = [], 1
    while True:
        batch = json.loads(fetch(f"{base}?per_page={per_page}&page={page}", headers))
        releases += [
            {
                "version": r["tag_name"],
                "published": utc_text(parse_utc(r["published_at"])),
                "created": utc_text(parse_utc(r["created_at"])),
                "prerelease": bool(r["prerelease"]),
            }
            for r in batch
            if not r["draft"]
        ]
        if len(batch) < per_page:
            return releases
        page += 1


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
        "collected_at": utc_text(now),
        "latest_at_collection": latest,
        "script": SCRIPT_VERSION,
    } | ({"tag": project.tag} if project.tag else {})
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
            tag = project.tag
            outside = [r["version"] for r in releases if tag and not re.search(tag, r["version"])]
            releases = [r for r in releases if r["version"] not in outside]
            path = write(args.folder, project, url, latest, releases, now())
        except (FetchError, KeyError, TypeError, ValueError) as e:
            print(f"error: {project.source} {project.name}: {e}", file=sys.stderr)
            failed += 1
            continue
        print(f"{project.source} {project.name}: {len(releases)} releases")
        if outside:
            prefixes = sorted({tag_prefix(v) for v in outside})
            print(f"  left out {len(outside)} outside {tag}, tag prefixes {prefixes[:5]}")
        for problem in problems(load(path)):
            print(f"  check: {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

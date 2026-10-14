import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from eval.replay import collect_timelines
from eval.replay.collect_timelines import collect_github, collect_pypi, main
from eval.replay.timelines import latest_on, load, problems
from shelflife.verifiers import FetchError, TooLarge

FIXTURES = Path(__file__).parents[1] / "fixtures" / "timelines"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def fetcher(routes):
    """A Fetch that serves bodies (or raises) by URL and records each call."""

    def fetch(url, headers):
        fetch.calls.append((url, dict(headers)))
        route = routes[url]
        if isinstance(route, Exception):
            raise route
        return route if isinstance(route, bytes) else json.dumps(route).encode()

    fetch.calls = []
    return fetch


def gh_release(tag, day, *, created=None, prerelease=False, draft=False):
    return {
        "tag_name": tag,
        "created_at": f"{created or day}T08:00:00Z",
        "published_at": f"{day}T09:00:00Z",
        "prerelease": prerelease,
        "draft": draft,
    }


def test_pypi_from_a_recorded_response():
    # PyPI's JSON for mcp, trimmed to the fields read (tests/fixtures/README.md).
    body = (FIXTURES / "pypi-mcp.json").read_bytes()
    url, latest, releases = collect_pypi("mcp", fetcher({"https://pypi.org/pypi/mcp/json": body}))
    assert (url, latest) == ("https://pypi.org/pypi/mcp/json", "2.3.0")
    files = json.loads(body)["releases"]
    assert len(releases) == len(files)
    first = min(f["upload_time_iso_8601"] for f in files["1.0.0"])
    assert {"version": "1.0.0", "published": first[:19] + "Z", "yanked": False} in releases


def test_pypi_dates_a_version_by_its_first_file_and_yanks_it_only_when_all_files_are():
    body = {
        "info": {"version": "1.1"},
        "releases": {
            "1.0": [
                {"upload_time_iso_8601": "2024-01-02T10:00:00.5Z", "yanked": True},
                {"upload_time_iso_8601": "2024-01-01T23:59:59.9Z", "yanked": False},
            ],
            "1.1": [{"upload_time_iso_8601": "2024-02-01T00:00:00Z", "yanked": True}],
            "1.2": [],  # no files: never installable
        },
    }
    _, _, releases = collect_pypi("x", fetcher({"https://pypi.org/pypi/x/json": body}))
    assert releases == [
        {"version": "1.0", "published": "2024-01-01T23:59:59Z", "yanked": False},
        {"version": "1.1", "published": "2024-02-01T00:00:00Z", "yanked": True},
    ]


def test_github_reads_every_page_and_leaves_out_drafts(monkeypatch):
    monkeypatch.setattr(collect_timelines, "PER_PAGE", 2)
    base = "https://api.github.com/repos/o/r/releases"
    fetch = fetcher(
        {
            f"{base}?per_page=2&page=1": [
                gh_release("v1.1", "2024-03-01"),
                gh_release("v1.1-rc1", "2024-02-01", prerelease=True),
            ],
            f"{base}?per_page=2&page=2": [
                gh_release("v1.2", "2024-04-01", draft=True),
                gh_release("v1.0", "2024-05-01", created="2023-12-01"),
            ],
            f"{base}?per_page=2&page=3": [],
            f"{base}/latest": {"tag_name": "v1.1"},
        }
    )
    url, latest, releases = collect_github("o/r", fetch, token="t")
    assert (url, latest) == (base, "v1.1")
    assert [r["version"] for r in releases] == ["v1.1", "v1.1-rc1", "v1.0"]
    assert releases[2] == {
        "version": "v1.0",
        "published": "2024-05-01T09:00:00Z",
        "created": "2023-12-01T08:00:00Z",
        "prerelease": False,
    }
    assert all(h["Authorization"] == "Bearer t" for _, h in fetch.calls)


def test_github_stops_at_a_short_page_and_reads_no_latest_as_none():
    base = "https://api.github.com/repos/o/r/releases"
    fetch = fetcher(
        {
            f"{base}?per_page=100&page=1": [gh_release("v1.0", "2024-01-01", prerelease=True)],
            f"{base}/latest": FetchError("HTTP 404", status=404),
        }
    )
    _, latest, releases = collect_github("o/r", fetch, token=None)
    assert latest is None and len(releases) == 1
    assert len(fetch.calls) == 2 and "Authorization" not in fetch.calls[0][1]
    fetch = fetcher(
        {
            f"{base}?per_page=100&page=1": [],
            f"{base}/latest": FetchError("HTTP 403", status=403),
        }
    )
    with pytest.raises(FetchError):
        collect_github("o/r", fetch, token=None)


def test_github_starts_again_with_half_the_page_size_when_a_page_is_too_large(monkeypatch):
    # Each release lists its assets, so a page of caddy's releases is over the 10 MB cap.
    monkeypatch.setattr(collect_timelines, "PER_PAGE", 4)
    monkeypatch.setattr(collect_timelines, "MIN_PER_PAGE", 2)
    base = "https://api.github.com/repos/o/r/releases"

    def page(*tags):
        return [gh_release(tag, "2024-01-01") for tag in tags]

    fetch = fetcher(
        {
            f"{base}?per_page=4&page=1": page("v6", "v5", "v4", "v3"),
            f"{base}?per_page=4&page=2": TooLarge("response larger than 10 MB"),
            f"{base}?per_page=2&page=1": page("v6", "v5"),
            f"{base}?per_page=2&page=2": page("v4", "v3"),
            f"{base}?per_page=2&page=3": page("v2"),
            f"{base}/latest": {"tag_name": "v6"},
        }
    )
    _, _, releases = collect_github("o/r", fetch, token=None)
    assert [r["version"] for r in releases] == ["v6", "v5", "v4", "v3", "v2"]  # each once


def test_github_halves_the_page_size_down_to_10_then_gives_up():
    base = "https://api.github.com/repos/o/r/releases"
    tried = [f"{base}?per_page={n}&page=1" for n in (100, 50, 25, 12, 10)]
    fetch = fetcher({url: TooLarge("response larger than 10 MB") for url in tried})
    with pytest.raises(TooLarge):
        collect_github("o/r", fetch, token=None)
    assert [url for url, _ in fetch.calls] == tried


def write_projects(folder, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "projects.toml").write_text(text)


def test_main_refuses_while_a_project_has_no_label(tmp_path, capsys):
    write_projects(tmp_path, 'pypi = [{ name = "mcp", volatility = "fast" }, { name = "x" }]')
    assert main([str(tmp_path)], fetch=fetcher({}), now=lambda: NOW) == 1
    assert "1 projects have no volatility label (first: x)" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == [tmp_path / "projects.toml"]


def test_main_writes_each_timeline_and_reports_failures(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    write_projects(
        tmp_path,
        'pypi = [{ name = "mcp", volatility = "fast" }, { name = "gone", volatility = "slow" }]\n'
        'github = [{ name = "o/r", volatility = "medium" }]\n',
    )
    base = "https://api.github.com/repos/o/r/releases"
    fetch = fetcher(
        {
            "https://pypi.org/pypi/mcp/json": (FIXTURES / "pypi-mcp.json").read_bytes(),
            "https://pypi.org/pypi/gone/json": FetchError("HTTP 404 from pypi", status=404),
            f"{base}?per_page=100&page=1": [
                gh_release("pkg-a-v1.0", "2024-01-01"),
                gh_release("pkg-b-v2.0", "2024-02-01"),
            ],
            f"{base}/latest": {"tag_name": "pkg-b-v2.0"},
        }
    )
    assert main([str(tmp_path)], fetch=fetch, now=lambda: NOW) == 1  # one project failed
    out, err = capsys.readouterr()
    assert "error: pypi gone: HTTP 404 from pypi" in err
    assert "check: tags with several prefixes" in out  # a monorepo shows up
    mcp = load(tmp_path / "pypi" / "mcp.jsonl")
    assert (mcp.collected_at, mcp.latest_at_collection) == (NOW, "2.3.0")
    # The rules give what PyPI called the latest on the day it was recorded.
    assert latest_on(mcp, date(2026, 10, 14)) == "2.3.0"
    assert problems(mcp) == ["first release on 2024-11-20, after the replay starts"]
    lines = (tmp_path / "pypi" / "mcp.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["script"] == collect_timelines.SCRIPT_VERSION
    published = [json.loads(line)["published"] for line in lines[1:]]
    assert published == sorted(published)  # oldest first, one release per line
    assert not (tmp_path / "pypi" / "gone.jsonl").exists()
    assert load(tmp_path / "github" / "o__r.jsonl").latest_at_collection == "pkg-b-v2.0"


def test_main_keeps_the_tag_pattern_in_the_header(tmp_path, capsys):
    write_projects(tmp_path, r"""github = [{ name = "o/r", volatility = "slow", tag = '^v\d' }]""")
    base = "https://api.github.com/repos/o/r/releases"
    fetch = fetcher(
        {
            f"{base}?per_page=100&page=1": [
                gh_release("v1.0", "2023-01-01"),
                gh_release("mcp-v1.0", "2024-02-01"),
                gh_release("vscode-typescript/v1.0.1", "2024-03-01"),
            ],
            f"{base}/latest": {"tag_name": "mcp-v1.0"},  # GitHub's, stored as it is
        }
    )
    assert main([str(tmp_path)], fetch=fetch, now=lambda: NOW) == 0
    out = capsys.readouterr().out
    # What was left out is named by its tag prefixes, for the maintainer to look over.
    assert (
        "github o/r: 1 releases\n"
        "  left out 2 outside ^v\\d, tag prefixes ['mcp-', 'vscode-typescript/']\n"
    ) in out
    assert "check: the source's latest, mcp-v1.0, is outside the tag pattern ^v\\d" in out
    timeline = load(tmp_path / "github" / "o__r.jsonl")
    assert (timeline.tag, [r.version for r in timeline.releases]) == (r"^v\d", ["v1.0"])

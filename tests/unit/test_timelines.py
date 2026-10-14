from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from eval.replay.timelines import (
    DEV,
    TEST,
    Project,
    Release,
    Timeline,
    changes,
    latest_on,
    load,
    load_all,
    load_projects,
    problems,
    split_of,
)

ROOT = Path(__file__).parents[2]
SMOKE = ROOT / "eval" / "data" / "smoke" / "timelines"
REAL = ROOT / "eval" / "data" / "timelines"


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def timeline(source, *releases, latest=None):
    return Timeline(source, "x", at("2026-09-30T12:00:00"), latest, tuple(releases))


# --- the "latest" rules (D11) -----------------------------------------------------------


def test_pypi_latest_is_the_highest_stable_version_not_the_newest_upload():
    t = timeline(
        "pypi",
        Release("1.0.0", at("2023-11-01T09:00")),
        Release("2.0.0", at("2024-03-01T09:00")),
        Release("1.0.1", at("2024-05-01T09:00")),  # a backport
        Release("2.1.0rc1", at("2024-06-01T09:00")),  # a pre-release
        Release("2.1.1", at("2024-07-01T09:00"), yanked=True),
        Release("2.2.x", at("2024-07-02T09:00")),  # PEP 440 cannot read it
    )
    assert latest_on(t, date(2023, 10, 31)) is None
    assert latest_on(t, date(2024, 5, 1)) == "2.0.0"
    assert latest_on(t, date(2024, 7, 2)) == "2.0.0"


def test_pypi_falls_back_to_pre_releases_when_there_is_nothing_else():
    t = timeline(
        "pypi", Release("0.1.0a1", at("2024-02-01T09:00")), Release("0.1.0b1", at("2024-09-01"))
    )
    assert latest_on(t, date(2024, 8, 31)) == "0.1.0a1"
    assert latest_on(t, date(2024, 9, 1)) == "0.1.0b1"
    t = timeline("pypi", Release("0.1.0a1", at("2024-02-01")), Release("0.1.0", at("2024-03-01")))
    assert latest_on(t, date(2024, 3, 1)) == "0.1.0"


def test_a_release_counts_from_the_end_of_its_utc_day():
    t = timeline("pypi", Release("1.0", at("2024-08-15T23:30")))
    assert (latest_on(t, date(2024, 8, 14)), latest_on(t, date(2024, 8, 15))) == (None, "1.0")


def test_github_latest_is_the_stable_release_created_last():
    t = timeline(
        "github",
        Release("v1.0.0", at("2024-01-10T09:00"), created=at("2024-01-10T08:00")),
        # Published later but created earlier, as a backport is: not the latest.
        Release("v0.9.1", at("2024-04-02T09:00"), created=at("2023-11-20T08:00")),
        Release("v1.1.0-beta.1", at("2024-10-01"), created=at("2024-10-01"), prerelease=True),
    )
    assert latest_on(t, date(2024, 1, 9)) is None
    assert latest_on(t, date(2024, 4, 2)) == "v1.0.0"
    assert latest_on(t, date(2024, 10, 1)) == "v1.0.0"


def test_changes_lists_only_the_days_the_latest_moved():
    t = timeline(
        "pypi",
        Release("1.0.0", at("2023-11-01")),
        Release("2.0.0", at("2024-03-01")),
        Release("1.0.1", at("2024-05-01")),
        Release("3.0.0", at("2025-06-10")),
    )
    assert changes(t, *DEV) == [(date(2024, 3, 1), "2.0.0")]
    assert changes(t, *TEST) == [(date(2025, 6, 10), "3.0.0")]
    assert changes(t, date(2024, 3, 2), date(2024, 12, 31)) == []  # 2.0.0 was already latest


@pytest.mark.parametrize(
    ("day", "split"),
    [
        (date(2023, 12, 31), None),
        (date(2024, 1, 1), "dev"),
        (date(2024, 12, 31), "dev"),
        (date(2025, 1, 1), "test"),
        (date(2026, 9, 30), "test"),
        (date(2026, 10, 1), None),
    ],
)
def test_the_split_is_by_time(day, split):
    assert split_of(day) == split


def test_problems_names_a_disagreement_and_mixed_tag_prefixes():
    t = timeline("pypi", Release("1.0", at("2024-01-01")), latest="1.1")
    assert problems(t) == ["latest by our rules is 1.0, the source said 1.1"]
    t = timeline(
        "github",
        Release("pkg-a-v1.0", at("2024-01-01"), created=at("2024-01-01")),
        Release("pkg-b-v2.0", at("2024-01-02"), created=at("2024-01-02")),
        latest="pkg-b-v2.0",
    )
    assert problems(t) == ["tags with several prefixes (per-package tags?): ['pkg-a-', 'pkg-b-']"]
    t = timeline("github", Release("v1.0", at("2024-01-01")), latest="v1.0")
    assert problems(t) == []


# --- files ------------------------------------------------------------------------------


def test_projects_toml_is_read_and_checked(tmp_path):
    path = tmp_path / "projects.toml"
    path.write_text(
        'pypi = [{ name = "mcp", volatility = "fast" }]\n'
        'github = [{ name = "getzep/graphiti", volatility = "" }]\n'
    )
    assert load_projects(path) == [
        Project("pypi", "mcp", "fast"),
        Project("github", "getzep/graphiti", ""),
    ]
    assert Project("github", "getzep/graphiti", "").path == "github/getzep__graphiti.jsonl"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('npm = [{ name = "x" }]', "unknown keys"),
        ('pypi = [{ name = "../x" }]', "not a pypi name"),
        ('github = [{ name = "graphiti" }]', "not a github name"),
        ('pypi = [{ name = "mcp", volatility = "none" }]', "volatility must be one of"),
        ('pypi = [{ name = "Foo_Bar" }, { name = "foo-bar" }]', "listed twice"),
    ],
)
def test_projects_toml_refuses(tmp_path, text, message):
    path = tmp_path / "projects.toml"
    path.write_text(text)
    with pytest.raises(ValueError, match=message):
        load_projects(path)


@pytest.mark.parametrize(
    "lines",
    [
        ['{"source": "npm", "project": "x", "collected_at": "2026-01-01T00:00:00Z"}'],
        ['{"source": "pypi", "project": "x"}'],
        [
            '{"source": "pypi", "project": "x", "collected_at": "2026-01-01T00:00:00Z",'
            ' "latest_at_collection": "1.0"}',
            '{"version": "1.0", "published": "2025-01-01T00:00:00"}',  # no time zone
        ],
    ],
)
def test_a_bad_timeline_file_names_itself(tmp_path, lines):
    path = tmp_path / "x.jsonl"
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="x.jsonl"):
        load(path)


# --- the smoke corpus and the collected data (CI) ---------------------------------------


def test_the_smoke_corpus_matches_its_projects_and_has_no_problems():
    timelines = load_all(SMOKE)
    listed = {(p.source, p.name) for p in load_projects(SMOKE / "projects.toml")}
    assert {(t.source, t.project) for t in timelines} == listed
    assert [problems(t) for t in timelines] == [[]] * len(timelines)


def test_the_smoke_corpus_gives_the_changes_it_was_built_for():
    found = {t.project: (changes(t, *DEV), changes(t, *TEST)) for t in load_all(SMOKE)}
    assert found == {
        "smoke-backport": (
            [(date(2024, 3, 1), "2.0.0"), (date(2024, 8, 15), "2.1.0")],
            [(date(2025, 6, 10), "3.0.0")],
        ),
        "smoke-prerelease-only": (
            [(date(2024, 2, 1), "0.1.0a1"), (date(2024, 9, 1), "0.1.0b1")],
            [],
        ),
        "smoke-quiet": ([], []),
        "smoke-org/out-of-order": ([(date(2024, 1, 10), "v1.0.0")], [(date(2025, 3, 5), "v1.1.0")]),
    }


def test_the_collected_timelines_load_and_match_projects_toml():
    # Before the maintainer collects the data there are no timeline files, and this
    # only reads projects.toml.
    projects = {(p.source, p.name) for p in load_projects(REAL / "projects.toml")}
    for t in load_all(REAL):
        assert (t.source, t.project) in projects

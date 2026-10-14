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
)

ROOT = Path(__file__).parents[2]
SMOKE = ROOT / "eval" / "data" / "smoke" / "timelines"
REAL = ROOT / "eval" / "data" / "timelines"


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def timeline(source, *releases, latest=None, tag=None):
    return Timeline(source, "x", at("2026-09-30T12:00:00"), latest, tuple(releases), tag)


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


def test_a_tag_pattern_leaves_out_the_releases_of_other_products():
    releases = (
        Release("v1.0.0", at("2024-01-10"), created=at("2024-01-10")),
        Release("mcp-v1.1.0", at("2024-02-01"), created=at("2024-02-01")),
        Release("vscode-typescript/v1.0.1", at("2024-03-01"), created=at("2024-03-01")),
        Release("v1.1.0", at("2024-04-01"), created=at("2024-04-01")),
    )
    t = timeline("github", *releases, tag=r"^v\d")
    assert [latest_on(t, date(2024, m, 1)) for m in (2, 3)] == ["v1.0.0", "v1.0.0"]
    assert changes(t, *DEV) == [(date(2024, 1, 10), "v1.0.0"), (date(2024, 4, 1), "v1.1.0")]
    # Without the pattern each product's release takes its turn as the latest.
    assert latest_on(timeline("github", *releases), date(2024, 3, 1)) == "vscode-typescript/v1.0.1"
    # A bare "v" is not enough: it matches "vscode-typescript/v1.0.1" too.
    assert latest_on(timeline("github", *releases, tag="^v"), date(2024, 3, 1)) == (
        "vscode-typescript/v1.0.1"
    )


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


def test_problems_names_a_disagreement_a_late_start_and_mixed_tag_prefixes():
    t = timeline("pypi", Release("1.0", at("2023-01-01")), latest="1.1")
    assert problems(t) == ["latest by our rules is 1.0, the source said 1.1"]
    t = timeline("pypi", Release("1.0", at("2024-01-02")), latest="1.0")
    assert problems(t) == ["first release on 2024-01-02, after the replay starts"]
    t = timeline(
        "github",
        Release("pkg-a-v1.0", at("2023-01-01"), created=at("2023-01-01")),
        Release("pkg-b-v2.0", at("2023-01-02"), created=at("2023-01-02")),
        latest="pkg-b-v2.0",
    )
    assert problems(t) == ["tags with several prefixes (per-package tags?): ['pkg-a-', 'pkg-b-']"]
    t = timeline("github", Release("v1.0", at("2024-01-01")), latest="v1.0")
    assert problems(t) == []


def test_problems_reads_only_the_releases_inside_the_tag_pattern():
    t = timeline(
        "github",
        Release("mcp-v0.1", at("2023-06-01"), created=at("2023-06-01")),
        Release("v1.0", at("2024-01-02"), created=at("2024-01-02")),
        Release("mcp-v0.2", at("2024-03-01"), created=at("2023-12-01")),
        latest="mcp-v0.2",
        tag=r"^v\d",
    )
    # GitHub's latest is another product's: the github_release verifier would read it.
    # The late start counts from v1.0, not mcp-v0.1; the mcp- tags are not a second
    # prefix, and mcp-v0.2, published last with an old commit, is no disputed day.
    late = "first release on 2024-01-02, after the replay starts"
    assert problems(t) == [
        "the source's latest, mcp-v0.2, is outside the tag pattern ^v\\d",
        late,
    ]
    t = timeline("github", *t.releases, latest="v0.9", tag=r"^v\d")
    assert problems(t) == ["latest by our rules is v1.0, the source said v0.9", late]
    t = timeline("github", *t.releases, latest=None, tag=r"^v\d")  # none marked latest
    assert problems(t) == ["latest by our rules is v1.0, the source said None", late]


def test_the_disputed_days_read_only_the_releases_inside_the_tag_pattern():
    t = timeline(
        "github",
        Release("v1.0", at("2023-06-01"), created=at("2023-06-01")),
        Release("v2.0", at("2024-01-10T09:00"), created=at("2024-01-10")),
        Release("mcp-v0.1", at("2024-01-10T12:00"), created=at("2023-12-01")),  # later that day
        Release("v1.1", at("2024-02-01"), created=at("2023-08-01")),  # a backport: disputed
        Release("mcp-v0.2", at("2024-03-01"), created=at("2024-03-01")),
        latest="v2.0",
        tag=r"^v\d",
    )
    # Neither mcp- release is published last on 2024-01-10, nor adds 2024-03-01.
    assert problems(t) == [
        "1 days when the release created last was not the one published last, first"
        " 2024-02-01: GitHub may have shown the other as latest"
    ]


def test_problems_counts_the_days_github_may_have_shown_a_backport_as_latest():
    # GitHub marks a newly published release latest by default (make_latest), so after
    # v2.9.1 is published the source may have shown it, while the rule keeps v3.0.0:
    # v2.9.1's commit (its created_at) is older than v3.0.0's.
    t = timeline(
        "github",
        Release("v2.9.0", at("2023-06-01"), created=at("2023-06-01")),
        Release("v1.9.1", at("2023-08-01"), created=at("2023-05-01")),  # before the replay
        Release("v3.0.0", at("2024-02-01"), created=at("2024-02-01")),
        Release("v2.9.1", at("2024-03-01"), created=at("2024-01-20")),
        Release("v2.9.2", at("2024-04-01"), created=at("2024-01-25")),
        Release("v3.0.1", at("2024-05-01"), created=at("2024-05-01")),
        latest="v3.0.1",
    )
    assert problems(t) == [
        "2 days when the release created last was not the one published last, first"
        " 2024-03-01: GitHub may have shown the other as latest"
    ]


# --- files ------------------------------------------------------------------------------


def test_projects_toml_is_read_and_checked(tmp_path):
    path = tmp_path / "projects.toml"
    path.write_text(
        'pypi = [{ name = "mcp", volatility = "fast" }]\n'
        r"""github = [{ name = "getzep/graphiti", volatility = "", tag = '^v\d' }]"""
    )
    assert load_projects(path) == [
        Project("pypi", "mcp", "fast"),
        Project("github", "getzep/graphiti", "", r"^v\d"),
    ]
    assert Project("github", "getzep/graphiti", "").path == "github/getzep__graphiti.jsonl"
    # PEP 503 folding is for PyPI names only: these are two GitHub repositories.
    path.write_text('github = [{ name = "o/my.repo" }, { name = "o/my-repo" }]')
    assert len(load_projects(path)) == 2


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('npm = [{ name = "x" }]', "unknown keys"),
        ('pypi = [{ name = "../x" }]', "not a pypi name"),
        ('github = [{ name = "graphiti" }]', "not a github name"),
        ('pypi = [{ name = "mcp", volatility = "none" }]', "volatility must be one of"),
        ('pypi = [{ name = "Foo_Bar" }, { name = "foo-bar" }]', "listed twice"),
        ('github = [{ name = "O/R" }, { name = "o/r" }]', "listed twice"),
        ('github = [{ name = "o/r", tags = "^v" }]', "unknown keys"),
        ('pypi = [{ name = "mcp", tag = "^v" }]', "tag must be a regular expression, for GitHub"),
        ('github = [{ name = "o/r", tag = "(v" }]', "tag must be a regular expression"),
        ('github = [{ name = "o/r", tag = 1 }]', "tag must be a regular expression"),
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


def test_the_smoke_corpus_matches_its_projects_and_flags_what_it_was_built_to():
    timelines = load_all(SMOKE)
    listed = {(p.source, p.name, p.tag) for p in load_projects(SMOKE / "projects.toml")}
    assert {(t.source, t.project, t.tag) for t in timelines} == listed
    assert {t.project: problems(t) for t in timelines} == {
        "smoke-backport": [],
        "smoke-prerelease-only": ["first release on 2024-02-01, after the replay starts"],
        "smoke-quiet": [],
        "smoke-org/out-of-order": [
            "2 days when the release created last was not the one published last, first"
            " 2024-04-02: GitHub may have shown the other as latest"
        ],
        "smoke-org/two-products": [
            "the source's latest, mcp-v1.1.0, is outside the tag pattern ^v\\d"
        ],
    }


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
        "smoke-org/two-products": (
            [(date(2024, 3, 1), "v1.1.0"), (date(2024, 9, 1), "v1.2.0")],
            [(date(2025, 5, 1), "v1.3.0")],
        ),
    }


def test_the_collected_timelines_load_and_match_projects_toml():
    # Before the maintainer collects the data there are no timeline files, and this
    # only reads projects.toml. After, every listed project has its timeline, collected
    # with the tag pattern it has now.
    projects = {(p.source, p.name, p.tag) for p in load_projects(REAL / "projects.toml")}
    if timelines := load_all(REAL):
        assert {(t.source, t.project, t.tag) for t in timelines} == projects

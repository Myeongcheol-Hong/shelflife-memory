import urllib.error
from pathlib import Path

import pytest

from shelflife.models import CheckResult
from shelflife.verifiers import (
    FetchError,
    compare_version,
    github_release,
    http_get,
    parse_version,
    pypi,
    same_version,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
PYPI_MCP = "https://pypi.org/pypi/mcp/json"
GITHUB_GRAPHITI = "https://api.github.com/repos/getzep/graphiti/releases/latest"
GITHUB_HINDSIGHT = "https://api.github.com/repos/vectorize-io/hindsight/releases/latest"


def fetcher(routes):
    """A Fetch that serves fixture files (or raises) by URL and records each call."""

    def fetch(url, headers):
        fetch.calls.append((url, dict(headers)))
        route = routes[url]
        if isinstance(route, Exception):
            raise route
        return route if isinstance(route, bytes) else (FIXTURES / route).read_bytes()

    fetch.calls = []
    return fetch


# --- pypi -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("claimed", "result"),
    [
        ("2.3.0", CheckResult.SAME),
        ("v2.3.0", CheckResult.SAME),
        ("2.3", CheckResult.SAME),  # equal under PEP 440
        ("2.2.0", CheckResult.CHANGED),
    ],
)
def test_pypi_compares_with_the_latest_version(claimed, result):
    outcome = pypi.check("mcp", claimed, fetcher({PYPI_MCP: "pypi/mcp.json"}))
    assert (outcome.result, outcome.new_value, outcome.evidence) == (result, "2.3.0", "2.3.0")


def test_pypi_without_a_claimed_value_cannot_tell():
    outcome = pypi.check("mcp", None, fetcher({PYPI_MCP: "pypi/mcp.json"}))
    assert (outcome.result, outcome.new_value) == (CheckResult.CANNOT_TELL, "2.3.0")


@pytest.mark.parametrize(
    ("route", "evidence"),
    [
        (FetchError("HTTP 404 from https://pypi.org/pypi/mcp/json"), "HTTP 404"),
        (b"<html>not json</html>", "unexpected response"),
        (b'{"info": {}}', "unexpected response"),
        (b'{"info": null}', "unexpected response"),
    ],
)
def test_pypi_reports_fetch_and_format_errors(route, evidence):
    outcome = pypi.check("mcp", "2.3.0", fetcher({PYPI_MCP: route}))
    assert outcome.result is CheckResult.ERROR
    assert evidence in outcome.evidence


@pytest.mark.parametrize(
    "body",
    [
        b'{"info": {"version": "2\\u002e3.0"}}',  # parses to 2.3.0, which is not in the body
        b'{"info": {"version": ""}}',
        b'{"info": {"version": 2}}',
    ],
)
def test_pypi_cannot_tell_without_a_verbatim_version(body):
    outcome = pypi.check("mcp", "2.3.0", fetcher({PYPI_MCP: body}))
    assert (outcome.result, outcome.evidence) == (CheckResult.CANNOT_TELL, None)


def test_pypi_rejects_a_bad_name_without_fetching():
    fetch = fetcher({})
    assert pypi.check("../etc", "1.0", fetch).result is CheckResult.ERROR
    assert fetch.calls == []


# --- github_release -------------------------------------------------------------------


def test_github_release_compares_with_the_latest_tag(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    fetch = fetcher({GITHUB_GRAPHITI: "github/getzep__graphiti.json"})
    assert github_release.check("getzep/graphiti", "v0.30.2", fetch).result is CheckResult.SAME
    outcome = github_release.check("getzep/graphiti", "v0.30.1", fetch)
    assert (outcome.result, outcome.new_value) == (CheckResult.CHANGED, "v0.30.2")
    assert "Authorization" not in fetch.calls[0][1]
    assert fetch.calls[0][1]["Accept"] == "application/vnd.github+json"


@pytest.mark.parametrize(
    ("url", "fixture", "tag", "name"),
    [
        (GITHUB_GRAPHITI, "github/getzep__graphiti.json", "v0.30.2", "v0.30.2 - FalkorDB updates"),
        (GITHUB_HINDSIGHT, "github/vectorize-io__hindsight.json", "v0.10.3", "v0.10.3"),
    ],
)
def test_github_release_compares_tag_name_never_name(url, fixture, tag, name):
    repo = url.split("/repos/")[1].removesuffix("/releases/latest")
    fetch = fetcher({url: fixture})
    outcome = github_release.check(repo, tag, fetch)
    assert (outcome.result, outcome.new_value, outcome.evidence) == (CheckResult.SAME, tag, tag)
    if name != tag:
        outcome = github_release.check(repo, name, fetch)
        assert (outcome.result, outcome.new_value) == (CheckResult.CHANGED, tag)


def test_github_release_ignores_a_name_that_looks_like_a_version():
    body = b'{"tag_name": "v2.0.0", "name": "v1.0.0"}'
    outcome = github_release.check("getzep/graphiti", "v1.0.0", fetcher({GITHUB_GRAPHITI: body}))
    assert (outcome.result, outcome.new_value) == (CheckResult.CHANGED, "v2.0.0")


def test_github_release_sends_the_token_when_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    fetch = fetcher({GITHUB_GRAPHITI: "github/getzep__graphiti.json"})
    github_release.check("getzep/graphiti", "v0.30.2", fetch)
    assert fetch.calls[0][1]["Authorization"] == "Bearer t0ken"


def test_github_release_reports_a_repository_without_releases():
    fetch = fetcher({GITHUB_GRAPHITI: FetchError(f"HTTP 404 from {GITHUB_GRAPHITI}")})
    outcome = github_release.check("getzep/graphiti", "v0.30.2", fetch)
    assert (outcome.result, outcome.evidence) == (
        CheckResult.ERROR,
        f"HTTP 404 from {GITHUB_GRAPHITI}",
    )


@pytest.mark.parametrize("body", [b"<html>rate limited</html>", b"{}", b"[]", b"null"])
def test_github_release_reports_format_errors(body):
    outcome = github_release.check("getzep/graphiti", "v0.30.2", fetcher({GITHUB_GRAPHITI: body}))
    assert outcome.result is CheckResult.ERROR
    assert "unexpected response" in outcome.evidence


def test_github_release_cannot_tell_without_a_verbatim_tag():
    body = b'{"tag_name": "v0\\u002e30.2"}'  # parses to v0.30.2, which is not in the body
    outcome = github_release.check("getzep/graphiti", "v0.30.2", fetcher({GITHUB_GRAPHITI: body}))
    assert outcome.result is CheckResult.CANNOT_TELL


def test_github_release_rejects_a_bad_repo_without_fetching():
    fetch = fetcher({})
    assert github_release.check("not a repo", "v1", fetch).result is CheckResult.ERROR
    assert fetch.calls == []


# --- shared ---------------------------------------------------------------------------


def test_evidence_must_appear_verbatim_in_the_fetched_body():
    assert compare_version("1.0", "1.0", body="{}").result is CheckResult.CANNOT_TELL
    assert compare_version("1.0", "1.0", body='{"version": "1.0"}').result is CheckResult.SAME


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("2.3.0", "2.3.0"),
        ("v0.10.3", "0.10.3"),
        ("V1.0", " v1.0 "),
        ("1.0", "1.0.0"),  # trailing zeros (PEP 440)
        ("2024.01.05", "2024.1.5"),  # leading zeros (PEP 440)
        ("1.0.0-rc1", "1.0rc1"),  # separator before the suffix (PEP 440)
        ("release-1.0", "1.0"),  # a tag prefix on one side
        ("graphiti-v0.3", "v0.3"),
        ("vnext", "VNext"),  # not versions: exact, ignoring case and spaces
    ],
)
def test_same_version(a, b):
    assert same_version(a, b) and same_version(b, a)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("2.2.0", "2.3.0"),
        ("1.1", "1.10"),
        ("1.0rc1", "1.0"),
        ("1.0-1", "1.0.1"),
        ("pkg-a-v1.0", "pkg-b-v1.0"),  # releases of two packages in one repository
        ("v0.30.2 - FalkorDB updates", "v0.30.2"),  # not a version: exact
        ("vnext", "next"),
    ],
)
def test_different_versions(a, b):
    assert not same_version(a, b) and not same_version(b, a)


@pytest.mark.parametrize("text", ["3.9+", "1.0.", "1..0", "$300", "Python 3.9", "", "v", "r123"])
def test_parse_version_rejects_what_is_not_a_version(text):
    assert parse_version(text) is None


def test_http_get_returns_the_body_and_sends_the_headers(monkeypatch):
    sent = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"ok"

    def urlopen(request, timeout):
        sent.update(request.header_items())
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert http_get("https://example.org/x", {"Authorization": "Bearer t"}) == b"ok"
    assert sent["Authorization"] == "Bearer t"
    assert "shelflife" in sent["User-agent"]


@pytest.mark.parametrize(
    ("raised", "message"),
    [
        (urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None), "HTTP 503 from"),
        (urllib.error.URLError("blocked"), "cannot reach"),
        (TimeoutError("timed out"), "cannot reach"),
    ],
)
def test_http_get_turns_failures_into_fetch_errors(monkeypatch, raised, message):
    def urlopen(request, timeout):
        assert timeout > 0 and request.get_header("User-agent")
        raise raised

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    with pytest.raises(FetchError, match=message):
        http_get("https://example.org/x", {})

import urllib.error
from pathlib import Path

import pytest

from shelflife.models import CheckResult
from shelflife.verifiers import FetchError, compare_version, github_release, http_get, pypi

FIXTURES = Path(__file__).parents[1] / "fixtures"
PYPI_MCP = "https://pypi.org/pypi/mcp/json"
GITHUB_GRAPHITI = "https://api.github.com/repos/getzep/graphiti/releases/latest"


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
    [("2.3.0", CheckResult.SAME), ("v2.3.0", CheckResult.SAME), ("2.2.0", CheckResult.CHANGED)],
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
    ],
)
def test_pypi_reports_fetch_and_format_errors(route, evidence):
    outcome = pypi.check("mcp", "2.3.0", fetcher({PYPI_MCP: route}))
    assert outcome.result is CheckResult.ERROR
    assert evidence in outcome.evidence


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


def test_github_release_rejects_a_bad_repo_without_fetching():
    fetch = fetcher({})
    assert github_release.check("not a repo", "v1", fetch).result is CheckResult.ERROR
    assert fetch.calls == []


# --- shared ---------------------------------------------------------------------------


def test_evidence_must_appear_verbatim_in_the_fetched_body():
    assert compare_version("1.0", "1.0", body="{}").result is CheckResult.CANNOT_TELL
    assert compare_version("1.0", "1.0", body='{"version": "1.0"}').result is CheckResult.SAME


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

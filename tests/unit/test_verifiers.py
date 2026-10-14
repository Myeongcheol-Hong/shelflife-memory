import urllib.error
import urllib.request
from pathlib import Path

import pytest

from shelflife import verifiers
from shelflife.models import CheckResult
from shelflife.verifiers import (
    FetchError,
    TooLarge,
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
    assert (outcome.result, outcome.evidence) == (
        CheckResult.CANNOT_TELL,
        "version not found verbatim",
    )


@pytest.mark.parametrize("name", ["../etc", "mcp/../x", "mcp-", "mcp/json"])
def test_pypi_rejects_a_bad_name_without_fetching(name):
    fetch = fetcher({})
    assert pypi.check(name, "1.0", fetch).result is CheckResult.ERROR
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


@pytest.mark.parametrize(
    "repo", ["not a repo", "getzep/graphiti/../../x", "getzep/graphiti/releases"]
)
def test_github_release_rejects_a_bad_repo_without_fetching(repo):
    fetch = fetcher({})
    assert github_release.check(repo, "v1", fetch).result is CheckResult.ERROR
    assert fetch.calls == []


# --- shared ---------------------------------------------------------------------------


def test_evidence_must_appear_verbatim_in_the_fetched_body():
    outcome = compare_version("1.0", "1.0", body="{}")
    assert (outcome.result, outcome.evidence) == (
        CheckResult.CANNOT_TELL,
        "version not found verbatim",
    )
    assert compare_version("1.0", "1.0", body='{"version": "1.0"}').result is CheckResult.SAME


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("2.3.0", "2.3.0"),
        ("v0.10.3", "0.10.3"),
        ("V1.0", "1.0.0"),  # the V must parse: the exact fallback would fail here
        (" v1.0 ", "1.0.0"),
        ("Release-1.0RC1", "release-1.0rc1"),  # prefix and suffix ignore case
        ("1.0", "1.0.0"),  # trailing zeros (PEP 440)
        ("2024.01.05", "2024.1.5"),  # leading zeros (PEP 440)
        ("1.0.0-rc1", "1.0rc1"),  # separator before the suffix (PEP 440)
        ("release-1.0", "1.0"),  # a tag prefix on one side
        ("graphiti-v0.3", "v0.3"),
        ("@scope/pkg@1.2.3", "1.2.3"),  # a scoped npm tag
        ("@scope/pkg@1.2.3", "@scope/pkg@v1.2.3"),
        ("v1.0.0-1", "1.0.0-1"),  # "v1.0.0" is not a tag prefix
        ("v1.2.3-beta-1", "1.2.3-beta-1"),
        ("vnext", " VNext "),  # not versions: exact, ignoring case and spaces
        # PEP 440's other spellings
        ("1.0c1", "1.0rc1"),
        ("1.0pre1", "1.0rc1"),
        ("1.0preview1", "1.0rc1"),
        ("1.0alpha1", "1.0a1"),
        ("1.0beta2", "1.0b2"),
        ("1.0-1", "1.0.post1"),  # an implicit post-release
        ("1.0rev1", "1.0.post1"),
        ("1.0r1", "1.0.post1"),
        ("1.0-post-1", "1.0.post1"),
        ("1.0rc", "1.0rc0"),  # a missing number is 0
        ("1.0.post", "1.0.post0"),
        ("1.0dev", "1.0.dev0"),
        ("1.0RC01", "1.0rc1"),  # leading zeros
        ("v1.0.0-beta.1", "1.0b1"),  # a semver tag
        ("1.0a1.post2.dev3", "1.0alpha-1-2_dev_3"),
        ("1.0+ubuntu-1", "1.0+Ubuntu_1"),  # a local version's separators and case
        ("1.0+01", "1.0+1"),  # a local version's numbers
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
        ("@a/pkg@1.0", "@b/pkg@1.0"),
        ("v1.0.0-1", "1"),
        ("v0.30.2 - FalkorDB updates", "v0.30.2"),  # not a version: exact
        ("vnext", "next"),
        ("1.0a1", "1.0b1"),
        ("1.0b1", "1.0b2"),
        ("1.0-1", "1.0rc1"),
        ("1.0.post1", "1.0.dev1"),
        ("1.0c1", "1.0.post1"),
        ("1.0+local", "1.0"),
        ("1.0_1", "1.0-1"),  # only "-" makes an implicit post-release (PEP 440)
    ],
)
def test_different_versions(a, b):
    assert not same_version(a, b) and not same_version(b, a)


@pytest.mark.parametrize("text", ["3.9+", "1.0.", "1..0", "$300", "Python 3.9", "", "v", "r123"])
def test_parse_version_rejects_what_is_not_a_version(text):
    assert parse_version(text) is None


class Response:
    def __init__(self, body=b"ok", limit=None):
        self.body, self.limit = body, limit

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n=-1):
        # Never more than the limit is held in memory.
        assert n == (self.limit or verifiers.MAX_BYTES) + 1
        return self.body[:n]


def opened(monkeypatch, result):
    """Replace the network step of http_get's opener; returns the requests and handlers."""
    seen = []

    def open(self, request, timeout):
        assert timeout > 0 and request.get_header("User-agent")
        seen.append((request, self.handlers))
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", open)
    return seen


def test_http_get_returns_the_body_and_sends_the_headers(monkeypatch):
    seen = opened(monkeypatch, Response(b"ok"))
    assert http_get("https://example.org/x", {"Authorization": "Bearer t"}) == b"ok"
    [(request, handlers)] = seen
    assert request.get_header("Authorization") == "Bearer t"
    assert "shelflife" in request.get_header("User-agent")
    assert any(isinstance(h, verifiers._SameOriginAuthorization) for h in handlers)


def test_http_get_refuses_a_body_over_the_limit(monkeypatch):
    monkeypatch.setattr(verifiers, "MAX_BYTES", 12)
    opened(monkeypatch, Response(b"x" * 12))
    assert http_get("https://example.org/x", {}) == b"x" * 12
    opened(monkeypatch, Response(b"x" * 13))
    with pytest.raises(TooLarge, match="larger than"):
        http_get("https://example.org/x", {})


def test_pypi_gets_its_own_larger_limit(monkeypatch):
    monkeypatch.setattr(verifiers, "MAX_BYTES", 12)
    monkeypatch.setattr(verifiers, "PYPI_MAX_BYTES", 20)
    pypi_json = "https://pypi.org/pypi/grpcio/json"
    opened(monkeypatch, Response(b"x" * 20, limit=20))
    assert http_get(pypi_json, {}) == b"x" * 20
    opened(monkeypatch, Response(b"x" * 21, limit=20))
    with pytest.raises(FetchError, match="larger than"):
        http_get(pypi_json, {})
    # Any other host keeps the smaller limit, even with pypi.org in its path.
    opened(monkeypatch, Response(b"x" * 13))
    with pytest.raises(FetchError, match="larger than"):
        http_get("https://api.github.com/repos/pypi.org/x", {})


@pytest.mark.parametrize(
    ("newurl", "kept"),
    [
        ("https://api.github.com/repositories/1/releases/latest", True),  # same origin
        ("https://API.github.com:443/x", True),  # the default port, other case
        ("https://objects.githubusercontent.com/x", False),  # another host
        ("http://api.github.com/x", False),  # another scheme
        ("https://api.github.com:8443/x", False),  # another port
    ],
)
def test_a_redirect_to_another_origin_drops_the_authorization(newurl, kept):
    request = urllib.request.Request(
        "https://api.github.com/repos/a/b/releases/latest",
        headers={"Authorization": "Bearer t", "Accept": "application/json"},
    )
    handler = verifiers._SameOriginAuthorization()
    new = handler.redirect_request(request, None, 302, "Found", {}, newurl)
    assert new.has_header("Authorization") is kept
    assert new.get_header("Accept") == "application/json"  # other headers still follow


@pytest.mark.parametrize(
    ("raised", "message"),
    [
        (urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None), "HTTP 503 from"),
        (urllib.error.URLError("blocked"), "cannot reach"),
        (TimeoutError("timed out"), "cannot reach"),
    ],
)
def test_http_get_turns_failures_into_fetch_errors(monkeypatch, raised, message):
    opened(monkeypatch, raised)
    with pytest.raises(FetchError, match=message) as error:
        http_get("https://example.org/x", {})
    assert error.value.status == (503 if isinstance(raised, urllib.error.HTTPError) else None)

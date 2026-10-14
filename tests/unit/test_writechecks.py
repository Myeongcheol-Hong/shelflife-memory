"""The four write checks of design 6.0-1 (D10.7) and their CLI."""

import json
from pathlib import Path

import pytest

from shelflife import cli, writechecks
from shelflife.cli import read_jsonl
from shelflife.verifiers import FetchError
from shelflife.verifiers.web_page import Page

FIXTURES = Path(__file__).parents[1] / "fixtures"
SEED = Path(__file__).parents[2] / "examples" / "seed_claims.jsonl"
PAGES = {
    entry["url"]: FIXTURES / "pages" / f"{name}.html"
    for name, entry in json.loads((FIXTURES / "pages" / "index.json").read_text()).items()
}


def fetch(url, headers):
    """PyPI and GitHub API answers from the recorded fixtures."""
    routes = {f"https://pypi.org/pypi/{p.stem}/json": p for p in (FIXTURES / "pypi").glob("*")}
    for p in (FIXTURES / "github").glob("*.json"):
        repo = p.stem.replace("__", "/")
        routes[f"https://api.github.com/repos/{repo}"] = p
        routes[f"https://api.github.com/repos/{repo}/releases/latest"] = p
    if url not in routes:
        raise FetchError(f"HTTP 404 from {url}", status=404)
    return routes[url].read_bytes()


def get_page(url):
    """The recorded seed pages; any other URL is gone, like the developer-mode page."""
    if url not in PAGES:
        raise FetchError(f"HTTP 404 from {url}", status=404)
    return Page(url, url, 200, "text/html", None, PAGES[url].read_bytes())


def failing(status):
    def fail(*args):
        raise FetchError(f"HTTP {status}" if status else "cannot reach", status=status)

    return fail


P, F, S, B, J = "pass", "fail", "skip", "blocked", "needs_judgment"


def test_the_seed_claims():
    rows = writechecks.run(read_jsonl(SEED), fetch, get_page)
    found = {}
    for row in rows:
        found.setdefault(row["id"], []).append(row["status"])
    assert found == {
        # The source_quote proposals are copied from the recorded pages (D10.7).
        "seed-claude-cert-eligibility": [P, P, P, J],
        "seed-claude-cert-fee": [P, P, P, J],
        "seed-aws-aip-c01-fee": [P, P, P, J],
        "seed-databricks-genai-fee": [P, P, P, J],
        "seed-ai-102-retired": [S, S, S, S],
        "seed-chatgpt-dev-mode-mcp": [S, S, F, J],  # the page is gone (D10)
        "seed-metagenomicsbench-top": [P, P, P, J],
        "seed-pypi-mcp": [S, S, P, P],
        "seed-pypi-claude-agent-sdk": [S, S, P, P],
        "seed-gh-hindsight": [S, S, P, P],
        "seed-gh-graphiti": [S, S, P, P],
        "seed-memguard-no-eval": [S, S, S, S],  # check_method none, set on purpose (D10)
        "seed-decision-focus": [S, S, S, S],
        "seed-pref-english": [S, S, S, S],
    }


AWS = "https://aws.amazon.com/certification/certified-generative-ai-developer-professional/"
RECORD = {
    "id": "c1",
    "value": "$300",
    "source_url": AWS,
    "source_quote": "300 USD.  Visit Exam pricing",  # normalized before it is looked for
    "check_method": "web_page",
    "check_target": AWS,
}


def test_quote_on_source():
    assert writechecks.quote_on_source(RECORD, get_page) == (P, None)
    other = RECORD | {"source_quote": "300 USD. Visit our pricing"}
    assert writechecks.quote_on_source(other, get_page) == (F, "quote not on the page")
    assert writechecks.quote_on_source(RECORD, failing(503)) == (B, "HTTP 503")
    assert writechecks.quote_on_source(RECORD, failing(404)) == (F, "HTTP 404")  # gone
    assert writechecks.quote_on_source(RECORD | {"source_url": None}, get_page)[0] == S


def test_a_page_that_cannot_be_decoded_blocks_check_1():
    def undecodable(url):
        return Page(url, url, 200, "text/html", None, b'<meta charset="undefined"><p>x</p>')

    assert writechecks.quote_on_source(RECORD, undecodable)[0] == B


def test_value_in_quote_uses_the_record_check_matcher():
    assert writechecks.value_in_quote(RECORD) == (P, None)  # $300 is 300 USD
    assert writechecks.value_in_quote(RECORD | {"value": "$30"})[0] == F
    assert writechecks.value_in_quote(RECORD | {"value": None})[0] == S


@pytest.mark.parametrize(
    ("status", "found"), [(404, F), (410, F), (403, B), (429, B), (503, B), (None, B)]
)
def test_target_exists_fails_only_when_the_target_is_gone(status, found):
    assert writechecks.target_exists(RECORD, fetch, failing(status))[0] == found
    pypi = RECORD | {"check_method": "pypi", "check_target": "mcp"}
    assert writechecks.target_exists(pypi, failing(status), get_page)[0] == found


def test_target_exists_asks_pypi_and_github_for_the_project():
    asked = []

    def record_url(url, headers):
        asked.append(url)
        return b"{}"

    for method, target in (("pypi", "mcp"), ("github_release", "getzep/graphiti")):
        record = {"check_method": method, "check_target": target}
        assert writechecks.target_exists(record, record_url, get_page) == (P, None)
    assert asked == [
        "https://pypi.org/pypi/mcp/json",
        "https://api.github.com/repos/getzep/graphiti",
    ]


def test_verifies_same():
    pypi = {"check_method": "pypi", "check_target": "mcp", "value": "2.3.0"}
    assert writechecks.verifies_same(pypi, fetch) == (P, None)
    status, detail = writechecks.verifies_same(pypi | {"value": "2.2.0"}, fetch)
    assert (status, detail) == (F, "changed: 2.3.0")
    assert writechecks.verifies_same(pypi, failing(503))[0] == B
    # A repository with no latest release: GitHub answers 404, so verify never says same.
    github = {"check_method": "github_release", "check_target": "o/r", "value": "v1"}
    assert writechecks.verifies_same(github, failing(404))[0] == F
    assert writechecks.verifies_same(RECORD, fetch) == (J, None)
    assert writechecks.verifies_same(pypi | {"value": None}, fetch)[0] == S


def rows_for(*statuses):
    return [
        {"n": n, "check": c, "status": s}
        for n, record in enumerate(statuses)
        for c, s in zip(writechecks.CHECKS, record, strict=True)
    ]


def test_any_failed_check_counts_against_the_rate():
    # D10.7: a record with any fail is applied and failing, all four passes is passing,
    # and the rest are left out.
    summary = writechecks.summarize(
        rows_for(
            [P, P, P, P],  # passing
            [P, F, P, P],  # failing
            [P, P, B, P],  # left out: blocked, nothing failed
            [P, P, F, B],  # failing: check 3 failed, so check 4 could not run
            [S, S, F, J],  # failing, though other checks did not apply
        )
    )
    assert (summary["applied"], summary["passed_all"], summary["rate"]) == (4, 1, 0.25)
    assert summary["counts"]["target_exists"] == {P: 2, F: 2, S: 0, B: 1, J: 0}
    assert writechecks.summarize([])["rate"] is None


def test_records_without_ids_are_counted_one_by_one():
    page = Page(
        "https://example.com/news",
        "https://example.com/news",
        200,
        "text/html",
        None,
        b"<p>mcp 2.3.0 is out now</p><p>mcp 2.2.0 was released</p>",
    )
    pypi = {"source_url": page.url, "check_method": "pypi", "check_target": "mcp"}
    good = pypi | {"value": "2.3.0", "source_quote": "mcp 2.3.0 is out now"}
    stale = pypi | {"value": "2.2.0", "source_quote": "mcp 2.2.0 was released"}
    rows = writechecks.run([good, stale], fetch, lambda url: page)
    summary = writechecks.summarize(rows)
    assert (summary["applied"], summary["passed_all"], summary["rate"]) == (2, 1, 0.5)


@pytest.mark.parametrize(
    ("method", "target", "detail"),
    [
        ("pypi", "mcp/2.3.0", "not a PyPI project name"),  # PyPI would answer this URL
        ("github_release", "getzep/graphiti/releases", "not an owner/repo"),
        ("web_page", "ftp://example.com/fees", "not a full http(s) URL"),
    ],
)
def test_a_malformed_target_fails_check_3(method, target, detail):
    record = {"check_method": method, "check_target": target}
    status, found = writechecks.target_exists(record, fetch, get_page)
    assert (status, found.split(":")[0]) == (F, detail)


def test_a_host_name_idna_refuses_fails_check_3():
    def bad_host(url):
        raise UnicodeError("label empty or too long")

    record = {"check_method": "web_page", "check_target": "https://a..example.com/fees"}
    assert writechecks.target_exists(record, fetch, bad_host)[0] == F


def test_a_field_that_is_not_a_string_fails_every_check():
    rows = writechecks.run([RECORD | {"value": 300}], fetch, get_page)
    assert {(r["status"], r["detail"]) for r in rows} == {(F, "value must be a string")}


def test_fields_are_read_as_remember_reads_them():
    assert writechecks.value_in_quote(RECORD | {"value": "   "})[0] == S  # empty means missing


def test_the_cli_prints_json_lines_and_stores_nothing(tmp_path, monkeypatch, capsys):
    db = tmp_path / "never.db"
    monkeypatch.setenv("SHELFLIFE_DB", str(db))
    monkeypatch.setattr(cli, "http_get", fetch)
    monkeypatch.setattr(cli, "fetch_page", get_page)
    claims = tmp_path / "claims.jsonl"
    claims.write_text(json.dumps(RECORD) + "\n")
    assert cli.main(["check-writes", str(claims)]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(line["check"], line["status"]) for line in lines[:4]] == [
        ("quote_on_source", P),
        ("value_in_quote", P),
        ("target_exists", P),
        ("verifies_same", J),
    ]
    assert lines[4]["summary"]["rate"] is None
    assert not db.exists()

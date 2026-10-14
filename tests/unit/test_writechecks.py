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
    assert writechecks.quote_on_source(RECORD | {"source_url": None}, get_page)[0] == S


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
    assert writechecks.verifies_same(RECORD, fetch) == (J, None)
    assert writechecks.verifies_same(pypi | {"value": None}, fetch)[0] == S


def test_the_rate_counts_only_records_where_all_four_checks_applied():
    rows = [
        {"id": i, "check": c, "status": s}
        for i, statuses in (("a", [P, P, P, P]), ("b", [P, F, P, P]), ("c", [P, P, B, P]))
        for c, s in zip(writechecks.CHECKS, statuses, strict=True)
    ]
    summary = writechecks.summarize(rows)
    assert (summary["applied"], summary["passed_all"], summary["rate"]) == (2, 1, 0.5)
    assert summary["counts"]["value_in_quote"] == {P: 2, F: 1, S: 0, B: 0, J: 0}
    assert writechecks.summarize([])["rate"] is None


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

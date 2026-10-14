"""The four automatic write checks of design 6.0-1 (D10.7).

Pure functions over records with the fields `remember` stores, with the network injected,
so the M8 write eval runs them without a database. A record is a line of
examples/seed_claims.jsonl or a stored claim's to_dict(): the checks read check_method
and check_target as given, so for what Claude passed to `remember`, store it first (an
in-memory Store fills them in by rule) and check the result. They never run inside
`remember`; `shelflife-memory check-writes` runs them over a JSONL file and stores
nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from shelflife.models import CheckMethod, CheckResult
from shelflife.store import is_http_url
from shelflife.verifiers import Fetch, FetchError, github_release, pypi, verifier_for
from shelflife.verifiers.judgment import value_in
from shelflife.verifiers.web_page import Page, extract, normalize, page_text

PASS, FAIL, SKIP, BLOCKED = "pass", "fail", "skip", "blocked"
NEEDS_JUDGMENT = "needs_judgment"  # check 4 for web_page, left out of the rate until M5b
CHECKS = ("quote_on_source", "value_in_quote", "target_exists", "verifies_same")
FIELDS = ("value", "source_url", "source_quote", "check_method", "check_target")
GONE = (404, 410)  # a target that is gone fails check 3; network trouble is blocked

Record = Mapping[str, Any]
Result = tuple[str, str | None]  # status, detail
GetPage = Callable[[str], Page]


def quote_on_source(record: Record, get_page: GetPage) -> Result:
    """1. The source_quote appears verbatim, after normalize(), in the source page's text.
    A source page that is gone (HTTP 404 or 410) fails, as in check 3."""
    quote, url = _field(record, "source_quote"), _field(record, "source_url")
    if not quote or not url:
        return SKIP, "no source_quote" if not quote else "no source_url"
    try:
        text = normalize(page_text(extract(get_page(url).text())))
    except FetchError as e:
        return (FAIL if e.status in GONE else BLOCKED), str(e)
    except UnicodeError as e:  # a charset that cannot be used
        return BLOCKED, str(e)
    return (PASS, None) if normalize(quote) in text else (FAIL, "quote not on the page")


def value_in_quote(record: Record) -> Result:
    """2. The value appears inside the source_quote, as record_check matches values (D10)."""
    value, quote = _field(record, "value"), _field(record, "source_quote")
    if not value or not quote:
        return SKIP, "no value" if not value else "no source_quote"
    return (PASS, None) if value_in(value, quote) else (FAIL, "value not in the quote")


def target_exists(record: Record, fetch: Fetch, get_page: GetPage) -> Result:
    """3. The check_target exists: the PyPI project, the GitHub repository or the page.
    A malformed target or HTTP 404 or 410 fails; a network or access problem outside our
    control is blocked (D10.7)."""
    method, target = _method(record), _field(record, "check_target")
    if method in (None, CheckMethod.NONE) or not target:
        return SKIP, "no check_method or check_target"
    malformed = {
        CheckMethod.PYPI: (pypi.NAME.fullmatch, "not a PyPI project name"),
        CheckMethod.GITHUB_RELEASE: (github_release.REPO.fullmatch, "not an owner/repo"),
        CheckMethod.WEB_PAGE: (is_http_url, "not a full http(s) URL"),
    }
    well_formed, problem = malformed[method]
    if not well_formed(target):
        return FAIL, f"{problem}: {target!r}"
    try:
        if method is CheckMethod.PYPI:
            fetch(f"https://pypi.org/pypi/{target}/json", {})
        elif method is CheckMethod.GITHUB_RELEASE:
            fetch(f"https://api.github.com/repos/{target}", {})
        else:
            get_page(target)
    except FetchError as e:
        return (FAIL if e.status in GONE else BLOCKED), str(e)
    except UnicodeError as e:  # a host name IDNA cannot encode
        return FAIL, f"not a valid host name: {e}"
    return PASS, None


def verifies_same(record: Record, fetch: Fetch) -> Result:
    """4. Verifying right after the write gives same. A web_page claim needs a judgment.
    A verifier error from a source that is gone (HTTP 404 or 410, such as a repository with
    no latest release) fails; other errors are blocked."""
    method, value = _method(record), _field(record, "value")
    if method in (None, CheckMethod.NONE) or not value:
        return SKIP, "no check_method or value"
    verifier = verifier_for(method)
    if verifier is None:
        return NEEDS_JUDGMENT, None
    statuses: list[int | None] = []  # the verifier's Outcome drops a FetchError's status

    def noting(url: str, headers: Mapping[str, str]) -> bytes:
        try:
            return fetch(url, headers)
        except FetchError as e:
            statuses.append(e.status)
            raise

    outcome = verifier(_field(record, "check_target") or "", value, noting)
    if outcome.result is CheckResult.SAME:
        return PASS, None
    if outcome.result is CheckResult.ERROR:
        return (FAIL if statuses and statuses[-1] in GONE else BLOCKED), outcome.evidence
    return FAIL, f"{outcome.result}: {outcome.new_value or outcome.evidence}"


def run(records: Iterable[Record], fetch: Fetch, get_page: GetPage) -> list[dict[str, Any]]:
    """Every check on every record: one row per record and check. `n` is the record's
    position in the input, which the rate groups by (records need no id). A field that is
    not a string fails all four checks."""
    rows = []
    for n, record in enumerate(records):
        wrong = [f for f in FIELDS if record.get(f) is not None and not isinstance(record[f], str)]
        if wrong:
            results: Iterable[Result] = [(FAIL, f"{wrong[0]} must be a string")] * len(CHECKS)
        else:
            results = (
                quote_on_source(record, get_page),
                value_in_quote(record),
                target_exists(record, fetch, get_page),
                verifies_same(record, fetch),
            )
        for check, (status, detail) in zip(CHECKS, results, strict=True):
            rows.append(
                {"n": n, "id": record.get("id"), "check": check, "status": status, "detail": detail}
            )
    return rows


def summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts per check and status, and the write integrity rate (D10.7): a record with any
    failed check counts as applied and failing, one that passed all four as passing, and
    the rest (skipped, blocked or needing judgment, with no fail) are left out."""
    counts = {
        check: dict.fromkeys((PASS, FAIL, SKIP, BLOCKED, NEEDS_JUDGMENT), 0) for check in CHECKS
    }
    by_record: dict[int, list[str]] = {}
    for row in rows:
        counts[row["check"]][row["status"]] += 1
        by_record.setdefault(row["n"], []).append(row["status"])
    failed = sum(FAIL in s for s in by_record.values())
    passed = sum(all(x == PASS for x in s) for s in by_record.values())
    applied = failed + passed
    return {
        "counts": counts,
        "applied": applied,
        "passed_all": passed,
        "rate": passed / applied if applied else None,
    }


def _field(record: Record, name: str) -> str | None:
    """A field as remember reads it: stripped, and empty means missing."""
    value = record.get(name)
    return value.strip() or None if isinstance(value, str) else None


def _method(record: Record) -> CheckMethod | None:
    try:
        return CheckMethod(_field(record, "check_method") or "none")
    except ValueError:
        return None

"""The four automatic write checks of design 6.0-1 (D10.7).

Pure functions over records with the fields `remember` takes (a line of
examples/seed_claims.jsonl, or a stored claim's to_dict()), with the network injected, so
the M8 write eval runs them without a database. They never run inside `remember`;
`shelflife-memory check-writes` runs them over a JSONL file and stores nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from shelflife.models import CheckMethod, CheckResult
from shelflife.verifiers import Fetch, FetchError, verifier_for
from shelflife.verifiers.judgment import value_in
from shelflife.verifiers.web_page import Page, extract, normalize, page_text

PASS, FAIL, SKIP, BLOCKED = "pass", "fail", "skip", "blocked"
NEEDS_JUDGMENT = "needs_judgment"  # check 4 for web_page, left out of the rate until M5
CHECKS = ("quote_on_source", "value_in_quote", "target_exists", "verifies_same")
GONE = (404, 410)  # the only answers that fail check 3; anything else is blocked

Record = Mapping[str, Any]
Result = tuple[str, str | None]  # status, detail
GetPage = Callable[[str], Page]


def quote_on_source(record: Record, get_page: GetPage) -> Result:
    """1. The source_quote appears verbatim, after normalize(), in the source page's text."""
    quote, url = record.get("source_quote"), record.get("source_url")
    if not quote or not url:
        return SKIP, "no source_quote" if not quote else "no source_url"
    try:
        text = normalize(page_text(extract(get_page(url).text())))
    except FetchError as e:
        return BLOCKED, str(e)
    return (PASS, None) if normalize(quote) in text else (FAIL, "quote not on the page")


def value_in_quote(record: Record) -> Result:
    """2. The value appears inside the source_quote, as record_check matches values (D10)."""
    value, quote = record.get("value"), record.get("source_quote")
    if not value or not quote:
        return SKIP, "no value" if not value else "no source_quote"
    return (PASS, None) if value_in(value, quote) else (FAIL, "value not in the quote")


def target_exists(record: Record, fetch: Fetch, get_page: GetPage) -> Result:
    """3. The check_target exists: the PyPI project, the GitHub repository or the page.
    Only HTTP 404 or 410 fails; any other error is blocked (D10.7)."""
    method, target = _method(record), record.get("check_target")
    if method in (None, CheckMethod.NONE) or not target:
        return SKIP, "no check_method or check_target"
    try:
        if method is CheckMethod.PYPI:
            fetch(f"https://pypi.org/pypi/{target}/json", {})
        elif method is CheckMethod.GITHUB_RELEASE:
            fetch(f"https://api.github.com/repos/{target}", {})
        else:
            get_page(target)
    except FetchError as e:
        return (FAIL if e.status in GONE else BLOCKED), str(e)
    return PASS, None


def verifies_same(record: Record, fetch: Fetch) -> Result:
    """4. Verifying right after the write gives same. A web_page claim needs a judgment."""
    method, value = _method(record), record.get("value")
    if method in (None, CheckMethod.NONE) or not value:
        return SKIP, "no check_method or value"
    verifier = verifier_for(method)
    if verifier is None:
        return NEEDS_JUDGMENT, None
    outcome = verifier(record.get("check_target") or "", value, fetch)
    if outcome.result is CheckResult.SAME:
        return PASS, None
    if outcome.result is CheckResult.ERROR:
        return BLOCKED, outcome.evidence
    return FAIL, f"{outcome.result}: {outcome.new_value or outcome.evidence}"


def run(records: Iterable[Record], fetch: Fetch, get_page: GetPage) -> list[dict[str, Any]]:
    """Every check on every record: one row per record and check."""
    rows = []
    for record in records:
        results = (
            quote_on_source(record, get_page),
            value_in_quote(record),
            target_exists(record, fetch, get_page),
            verifies_same(record, fetch),
        )
        for check, (status, detail) in zip(CHECKS, results, strict=True):
            rows.append(
                {"id": record.get("id"), "check": check, "status": status, "detail": detail}
            )
    return rows


def summarize(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts per check and status, and the write integrity rate: the share of records
    passing all four checks, over the records where all four gave pass or fail."""
    counts = {
        check: dict.fromkeys((PASS, FAIL, SKIP, BLOCKED, NEEDS_JUDGMENT), 0) for check in CHECKS
    }
    by_record: dict[Any, list[str]] = {}
    for row in rows:
        counts[row["check"]][row["status"]] += 1
        by_record.setdefault(row["id"], []).append(row["status"])
    applied = [s for s in by_record.values() if all(x in (PASS, FAIL) for x in s)]
    passed = sum(all(x == PASS for x in s) for s in applied)
    return {
        "counts": counts,
        "applied": len(applied),
        "passed_all": passed,
        "rate": passed / len(applied) if applied else None,
    }


def _method(record: Record) -> CheckMethod | None:
    try:
        return CheckMethod(record.get("check_method") or "none")
    except ValueError:
        return None

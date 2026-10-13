"""pypi verifier: is the claimed version still the latest release on PyPI?"""

from __future__ import annotations

import json
import re

from shelflife.models import CheckResult
from shelflife.verifiers import Fetch, FetchError, Outcome, compare_version, http_get

# Project names as PyPI accepts them (PEP 508); anything else never reaches a URL.
NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")


def check(package: str, claimed: str | None, fetch: Fetch = http_get) -> Outcome:
    """Compare `claimed` with `info.version` from PyPI's JSON API (the latest release)."""
    if not NAME.fullmatch(package):
        return Outcome(CheckResult.ERROR, evidence=f"not a PyPI project name: {package!r}")
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        body = fetch(url, {}).decode("utf-8")
        latest = json.loads(body)["info"]["version"]
    except FetchError as e:
        return Outcome(CheckResult.ERROR, evidence=str(e))
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        return Outcome(CheckResult.ERROR, evidence=f"unexpected response from {url}")
    return compare_version(claimed, latest, body)

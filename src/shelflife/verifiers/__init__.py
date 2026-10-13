"""Rule-based verifiers: fetch the source and compare it with the claim's value.

Network access goes through a `Fetch` function, so tests pass recorded fixtures instead of
calling the live network.
"""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from shelflife.models import CheckResult

TIMEOUT_SECONDS = 15
USER_AGENT = "shelflife-memory (+https://github.com/Myeongcheol-Hong/shelflife-memory)"

# (url, extra headers) -> response body. Raises FetchError.
Fetch = Callable[[str, Mapping[str, str]], bytes]


class FetchError(Exception):
    """The source could not be fetched (HTTP error, network error, timeout)."""


@dataclass(frozen=True)
class Outcome:
    result: CheckResult
    new_value: str | None = None  # the value found at the source
    evidence: str | None = None  # text quoted verbatim from the fetched content, or the error


def http_get(url: str, headers: Mapping[str, str]) -> bytes:
    """The real `Fetch`: a GET with a timeout and a User-Agent."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} from {url}") from None
    except (OSError, http.client.HTTPException) as e:  # URLError and timeouts are OSErrors
        raise FetchError(f"cannot reach {url}: {e}") from None


def normalize_version(version: str) -> str:
    """Compare "v0.10.3" and "0.10.3" as equal; versions are otherwise compared exactly."""
    version = version.strip().lower()
    return version[1:] if version[:1] == "v" and version[1:2].isdigit() else version


def compare_version(claimed: str | None, found: object, body: str) -> Outcome:
    """Compare a claimed version with the one found in a fetched body.

    The found version is the evidence, and it must appear verbatim in the fetched content
    (CLAUDE.md); otherwise nothing can be concluded.
    """
    if not isinstance(found, str) or not found or found not in body:
        return Outcome(CheckResult.CANNOT_TELL)
    if claimed is None:
        return Outcome(CheckResult.CANNOT_TELL, new_value=found, evidence=found)
    same = normalize_version(claimed) == normalize_version(found)
    result = CheckResult.SAME if same else CheckResult.CHANGED
    return Outcome(result, new_value=found, evidence=found)

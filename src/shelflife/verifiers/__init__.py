"""Rule-based verifiers: fetch the source and compare it with the claim's value.

Network access goes through a `Fetch` function, so tests pass recorded fixtures instead of
calling the live network.
"""

from __future__ import annotations

import http.client
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from shelflife.models import CheckMethod, CheckResult

TIMEOUT_SECONDS = 15
MAX_BYTES = 10 * 2**20  # the largest response body read
USER_AGENT = "shelflife-memory (+https://github.com/Myeongcheol-Hong/shelflife-memory)"

# (url, extra headers) -> response body. Raises FetchError.
Fetch = Callable[[str, Mapping[str, str]], bytes]


class FetchError(Exception):
    """The source could not be fetched (HTTP error, network error, timeout, refused URL)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status  # the HTTP status, for an HTTP error


@dataclass(frozen=True)
class Outcome:
    result: CheckResult
    new_value: str | None = None  # the value found at the source
    evidence: str | None = None  # text quoted verbatim from the fetched content, or the error


# (check_target, claimed value, fetch) -> outcome.
Verifier = Callable[[str, str | None, Fetch], Outcome]


def http_get(url: str, headers: Mapping[str, str]) -> bytes:
    """The real `Fetch`: a GET with a timeout and a User-Agent. A body over MAX_BYTES is
    refused, and a redirect to another origin drops the Authorization header."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        opener = urllib.request.build_opener(_SameOriginAuthorization)
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} from {url}", status=e.code) from None
    except (OSError, http.client.HTTPException) as e:  # URLError and timeouts are OSErrors
        raise FetchError(f"cannot reach {url}: {e}") from None
    if len(body) > MAX_BYTES:
        raise FetchError(f"response larger than {MAX_BYTES // 2**20} MB from {url}")
    return body


class _SameOriginAuthorization(urllib.request.HTTPRedirectHandler):
    """Follows redirects as urllib does, which copies every header, but drops
    Authorization when a redirect changes the scheme, host or port, so a GitHub token
    is never sent to another server."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and _origin(new.full_url) != _origin(req.full_url):
            new.remove_header("Authorization")
        return new


def _origin(url: str) -> tuple[str, str | None, int | None]:
    parts = urllib.parse.urlsplit(url)
    default = {"http": 80, "https": 443}.get(parts.scheme)
    return parts.scheme, parts.hostname, parts.port or default


# A version as packages and release tags write it: an optional tag prefix ending in a
# separator ("release-", "graphiti-", "@scope/pkg@"), an optional "v", the numeric release
# segments, then an optional suffix ("rc1", "-beta.1", "+local"). The parse without a
# prefix is tried first, so "v1.0.0-1" is release 1.0.0 with suffix 1, not prefix
# "v1.0.0". The release never gives digits back to the suffix, so "3.9+" and "1.0." are
# not versions.
VERSION = re.compile(
    r"(?:(?P<prefix>@?[a-z][\w.@/=-]*?)[-_/@=]+)??v?(?P<release>\d++(?:\.\d++)*+)"
    r"(?P<suffix>[-_.+]?[a-z0-9][\w.+-]*)?",
    re.IGNORECASE,
)


def parse_version(text: str) -> tuple[str | None, str, str] | None:
    """(tag prefix, release, suffix) of a version string; None if it is not one.

    As in PEP 440, the release drops leading zeros in each segment and trailing ".0"
    segments ("1.0" and "1.0.0" give the same release), and the suffix drops a leading
    "-", "_" or "." ("1.0-rc1" and "1.0rc1" give the same suffix).
    """
    m = VERSION.fullmatch(text.strip())
    if m is None:
        return None
    segments = [s.lstrip("0") or "0" for s in m["release"].split(".")]
    while len(segments) > 1 and segments[-1] == "0":
        segments.pop()
    prefix = m["prefix"].lower() if m["prefix"] else None
    suffix = (m["suffix"] or "").lower()
    return prefix, ".".join(segments), suffix[1:] if suffix[:1] in "-_." else suffix


def same_version(a: str, b: str) -> bool:
    """Whether two version strings name the same version.

    Equivalent forms are equal: "v0.10.3" and "0.10.3", "1.0" and "1.0.0", "release-1.0"
    and "1.0". Two different tag prefixes are not ("pkg-a-v1.0" and "pkg-b-v1.0" name
    releases of different packages in one repository). Anything that is not a version
    string is compared exactly, ignoring case and surrounding spaces.
    """
    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        return a.strip().lower() == b.strip().lower()
    prefixes_agree = pa[0] is None or pb[0] is None or pa[0] == pb[0]
    return prefixes_agree and pa[1:] == pb[1:]


def compare_version(claimed: str | None, found: object, body: str) -> Outcome:
    """Compare a claimed version with the one found in a fetched body.

    The found version is the evidence, and it must appear verbatim in the fetched content
    (CLAUDE.md); otherwise nothing can be concluded, and the evidence says so.
    """
    if not isinstance(found, str) or not found or found not in body:
        return Outcome(CheckResult.CANNOT_TELL, evidence="version not found verbatim")
    if claimed is None:
        return Outcome(CheckResult.CANNOT_TELL, new_value=found, evidence=found)
    result = CheckResult.SAME if same_version(claimed, found) else CheckResult.CHANGED
    return Outcome(result, new_value=found, evidence=found)


def verifier_for(method: CheckMethod) -> Verifier | None:
    """The rule-based verifier for a check method; None for web_page, which Claude judges
    in the conversation (D4), and for none."""
    from shelflife.verifiers import github_release, pypi  # both modules import this one

    return {CheckMethod.PYPI: pypi.check, CheckMethod.GITHUB_RELEASE: github_release.check}.get(
        method
    )

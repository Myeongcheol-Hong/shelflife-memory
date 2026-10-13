"""github_release verifier: is the claimed tag still the repository's latest release?"""

from __future__ import annotations

import json
import os
import re

from shelflife.models import CheckResult
from shelflife.verifiers import Fetch, FetchError, Outcome, compare_version, http_get

REPO = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")


def check(repo: str, claimed: str | None, fetch: Fetch = http_get) -> Outcome:
    """Compare `claimed` with `tag_name` of the latest release (GitHub REST API).

    The API's "latest" release skips drafts and pre-releases. A repository without
    releases answers 404, which is reported as an error. Set GITHUB_TOKEN to raise the
    unauthenticated limit of 60 requests an hour.
    """
    if not REPO.fullmatch(repo):
        return Outcome(CheckResult.ERROR, evidence=f"not an owner/repo: {repo!r}")
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    try:
        body = fetch(url, headers).decode("utf-8")
        tag = json.loads(body)["tag_name"]
    except FetchError as e:
        return Outcome(CheckResult.ERROR, evidence=str(e))
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        return Outcome(CheckResult.ERROR, evidence=f"unexpected response from {url}")
    return compare_version(claimed, tag, body)

"""Re-record the verifier fixtures from the live APIs. Not a test; run it by hand:

    uv run python tests/fixtures/record.py

Responses are trimmed to the field each verifier reads plus a few for context (see
README.md), so the files stay small. The GitHub API needs network access to
api.github.com (set GITHUB_TOKEN to avoid the unauthenticated rate limit). Cloud sessions
may block it; run it on your own machine.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from shelflife.verifiers import FetchError, http_get

HERE = Path(__file__).parent
PYPI = ["mcp", "claude-agent-sdk"]
GITHUB = ["vectorize-io/hindsight", "getzep/graphiti"]
GITHUB_FIELDS = ["tag_name", "name", "html_url", "published_at", "draft", "prerelease"]


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(HERE)}")


def main() -> int:
    failed = 0
    for package in PYPI:
        try:
            info = json.loads(http_get(f"https://pypi.org/pypi/{package}/json", {}))["info"]
        except FetchError as e:
            print(f"skipped {package}: {e}", file=sys.stderr)
            failed += 1
            continue
        save(HERE / "pypi" / f"{package}.json", {"info": {k: info[k] for k in ("name", "version")}})

    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    for repo in GITHUB:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            release = json.loads(http_get(url, headers))
        except FetchError as e:
            print(f"skipped {repo}: {e}", file=sys.stderr)
            failed += 1
            continue
        save(
            HERE / "github" / f"{repo.replace('/', '__')}.json",
            {k: release[k] for k in GITHUB_FIELDS},
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

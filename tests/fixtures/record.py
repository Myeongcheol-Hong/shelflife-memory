"""Re-record the verifier fixtures from the live sources. Not a test; run it by hand:

    uv run python tests/fixtures/record.py [pypi] [github] [pages]

With no arguments it records all three. Responses are trimmed to what the code reads plus
a little context (see README.md), so the files stay small. The GitHub API needs network
access to api.github.com (set GITHUB_TOKEN to avoid the unauthenticated rate limit). Cloud
sessions may block it; run it on your own machine.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

from shelflife.verifiers import FetchError, http_get
from shelflife.verifiers.web_page import extract, fetch_page

HERE = Path(__file__).parent
PYPI = ["mcp", "claude-agent-sdk"]
GITHUB = ["vectorize-io/hindsight", "getzep/graphiti"]
GITHUB_FIELDS = ["tag_name", "name", "html_url", "published_at", "draft", "prerelease"]
# The seed web_page claims' pages: name -> (url, keep scripts). One page keeps its scripts
# so the test that script text is never extracted runs on real input.
PAGES = {
    "skilljar-faq": ("https://anthropic-partners.skilljar.com/page/faq-certifications", False),
    "skilljar-partner": (
        "https://anthropic-partners.skilljar.com/page/partner-certifications",
        False,
    ),
    "aws-aip-c01": (
        "https://aws.amazon.com/certification/certified-generative-ai-developer-professional/",
        True,
    ),
    "databricks-genai": (
        "https://www.databricks.com/learn/certification/genai-engineer-associate",
        False,
    ),
    "benchmarks-metagenomics": ("https://benchmarks.bio/metagenomics", False),
}
# Attributes the extractor reads; every other attribute is dropped from page fixtures.
KEPT_ATTRIBUTES = {"hidden", "aria-hidden", "style", "charset", "http-equiv", "content"}


class _Slim(HTMLParser):
    """Re-serializes HTML without comments, SVG, attributes the extractor ignores and,
    unless kept, scripts and styles. Text and entity references are copied as they are."""

    def __init__(self, keep_scripts: bool) -> None:
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.drop = {"svg"} | (set() if keep_scripts else {"script", "style", "noscript"})
        self.skip: str | None = None
        self.depth = 0

    def tag(self, tag: str, attrs: list[tuple[str, str | None]], close: str) -> str:
        kept = "".join(
            f" {k}" if v is None else f' {k}="{html.escape(v)}"'
            for k, v in attrs
            if k in KEPT_ATTRIBUTES
            and (k != "style" or any(s in v.replace(" ", "").lower() for s in HIDING))
        )
        return f"<{tag}{kept}{close}>"

    def handle_starttag(self, tag, attrs):
        if self.skip:
            self.depth += tag == self.skip
        elif tag in self.drop:
            self.skip, self.depth = tag, 1
        else:
            self.out.append(self.tag(tag, attrs, ""))

    def handle_startendtag(self, tag, attrs):
        if not self.skip and tag not in self.drop:
            self.out.append(self.tag(tag, attrs, "/"))

    def handle_endtag(self, tag):
        if self.skip:
            self.depth -= tag == self.skip
            if self.depth == 0:
                self.skip = None
        else:
            self.out.append(f"</{tag}>")

    def emit(self, text: str) -> None:
        if not self.skip:
            self.out.append(text)

    def handle_data(self, data):
        self.emit(data)

    def handle_entityref(self, name):
        self.emit(f"&{name};")

    def handle_charref(self, name):
        self.emit(f"&#{name};")

    def handle_decl(self, decl):
        self.emit(f"<!{decl}>")


HIDING = ("display:none", "visibility:hidden")


def slim(page: str, keep_scripts: bool) -> str:
    parser = _Slim(keep_scripts)
    parser.feed(page)
    parser.close()
    return "".join(parser.out)


def record_pages() -> int:
    failed = 0
    index = {}
    for name, (url, keep_scripts) in PAGES.items():
        try:
            page = fetch_page(url)
        except FetchError as e:
            print(f"skipped {name}: {e}", file=sys.stderr)
            failed += 1
            continue
        original = page.text()
        slimmed = slim(original, keep_scripts)
        if extract(slimmed) != extract(original):
            raise SystemExit(f"{name}: the slimmed page does not extract to the same text")
        path = HERE / "pages" / f"{name}.html"
        path.write_text(slimmed, encoding="utf-8")
        print(f"wrote {path.relative_to(HERE)}")
        index[name] = {
            "url": url,
            "final_url": page.final_url,
            "status": page.status,
            "content_type": page.content_type,
            "charset": page.charset,
            "recorded_on": datetime.date.today().isoformat(),
            "sha256": page.sha256,
            "bytes": len(page.body),
            "scripts_kept": keep_scripts,
        }
    save(HERE / "pages" / "index.json", index)
    return failed


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(HERE)}")


def main(argv: list[str]) -> int:
    parts = set(argv) or {"pypi", "github", "pages"}
    failed = record_pages() if "pages" in parts else 0
    for package in PYPI if "pypi" in parts else []:
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
    for repo in GITHUB if "github" in parts else []:
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
    sys.exit(main(sys.argv[1:]))

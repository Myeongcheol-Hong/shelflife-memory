"""Write-time rules for the volatility and check_method a caller leaves empty (M2).

Rules only fill empty fields, and the claim records `rule` as their source. A value the
caller gave is never replaced (D5). Claude sets volatility only through `remember` (D4),
so these rules are the only classifier on the server. They are heuristics, approved by
the owner on 2026-10-13; design 6.0-3 measures their impact.
"""

from __future__ import annotations

import re

from shelflife.models import CheckMethod, Volatility
from shelflife.verifiers import parse_version

HANGUL = "가-힣"

# Words that mark how fast a fact changes (design 4.2), matched in the attribute first,
# then in the text. English words match as whole words (an "s" plural included), where
# only an ASCII letter breaks a word, so "API는" still matches "api". Korean words match
# at the start of a word, with any particle after them, so "정의" does not match inside
# "일정의". A missed keyword leaves the default (fast for a world fact), the cheap error.
KEYWORDS: dict[Volatility, list[str]] = {
    Volatility.FAST: """version release latest price pricing fee cost rank ranking score
        benchmark 가격 요금 비용 버전 릴리스 최신 순위 점수""".split(),
    Volatility.MEDIUM: """feature api policy support eligibility status limit plan
        기능 정책 지원 자격 상태 한도 플랜""".split(),
    Volatility.SLOW: "history concept principle definition 역사 개념 원칙 정의".split(),
}

# A price written in the text or value is a fast fact: a currency sign or code before
# the amount ("$19.99", "USD 20"), or a sign, code or word after it ("20€", "20 dollars",
# "300달러", "5,000원"), Korean counters included ("2만 9천원").
MONEY = re.compile(
    r"""
    [$€£¥₩]\s?\d
    | (?<![a-z])(?:usd|eur|gbp|jpy|krw)\s?\d
    | (?<![\d,.만천억])\d[\d,.]*+ (?>(?:\s?[만천억]++(?:\s?\d[\d,.]*+)?)*)
      \s?(?:[$€£¥₩]|원|달러|불|유로|(?:usd|eur|gbp|jpy|krw|dollars?|euros?)(?![a-z]))
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A fact about the newest version or release of a package or repository: the whole
# attribute names it ("latest_version", "latest_release", "최신 버전"). It must say latest,
# newest, current or 최신: a bare "version" or "release" may be a pinned one ("we pinned
# mcp version 2.3.0"), which a check would report as changed on every release. The text
# alone never qualifies. Such claims get no check method and show under due's
# needs_check_method, the cheap error (owner, 2026-10-13).
VERSION_ATTRIBUTE = re.compile(
    r"(?:latest|newest|current)\s+(?:stable\s+)?(?:version|release)s?"
    r"|최신\s*(?:버전|릴리스)"
)
# A bare year or a date (2025, 2024-06, 2024-06-20) is not a version string, although it
# parses as one (2024/06/20 does not parse). Dotted calendar versions (certifi's
# 2024.08.30) and compact dates (20240620) still count (owner, 2026-10-13).
YEAR_OR_DATE = re.compile(r"\d{4}(?:-\d{1,2}(?:-\d{1,2})?)?")
PYPI_URL = re.compile(r"https?://pypi\.org/project/([A-Za-z0-9][A-Za-z0-9._-]*)/?.*", re.I)
GITHUB_URL = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?(?:[/?#].*)?",
    re.I,
)
# First path segments of GitHub's own sections, which are not owners of repositories.
GITHUB_NOT_OWNERS = frozenset(
    """about account advisories apps blog changelog codespaces collections copilot
    customer-stories dashboard discussions education enterprise events explore features
    git-guides issues login marketplace new notifications orgs organizations pricing pulls
    readme resources search security settings site solutions sponsors stars topics trending
    users""".split()
)


def _words(text: str) -> str:
    """Lower case, with "_" and "-" as spaces, so "latest_version" reads as two words."""
    return text.lower().replace("_", " ").replace("-", " ")


def _mentions(text: str, word: str) -> bool:
    if word.isascii():
        return re.search(rf"(?<![a-z]){re.escape(word)}s?(?![a-z])", text) is not None
    return re.search(rf"(?<![{HANGUL}]){re.escape(word)}", text) is not None


def infer_volatility(attribute: str | None, text: str, value: str | None) -> Volatility | None:
    """The class the rules give a claim; None if no rule applies.

    Precedence: a price amount in the text or value means fast. Otherwise the attribute
    decides if it has a keyword, else the text; within one of them, fast keywords win
    over medium ones and medium over slow.
    """
    if MONEY.search(text) or (value and MONEY.search(value)):
        return Volatility.FAST
    for where in (attribute, text):
        if not where:
            continue
        where = _words(where)
        for volatility, words in KEYWORDS.items():
            if any(_mentions(where, w) for w in words):
                return volatility
    return None


def is_version_fact(attribute: str | None, value: str | None) -> bool:
    """Whether a claim states the latest version or release, as a version string.

    The attribute must name it ("latest_version", not "version", "python_version" or
    "release_date"), and the value must be a version string ("2.3 or later", "2025" and
    "2024-06-20" are not).
    """
    if not attribute or not value or YEAR_OR_DATE.fullmatch(value.strip()):
        return False
    if parse_version(value) is None:
        return False
    return VERSION_ATTRIBUTE.fullmatch(" ".join(_words(attribute).split())) is not None


def same_project(method: CheckMethod, a: str, b: str) -> bool:
    """PyPI names compare normalized ("-", "_" and "." are equal, PEP 503); GitHub names
    ignore case."""
    if method is CheckMethod.PYPI:
        a, b = (re.sub(r"[-_.]+", "-", name) for name in (a, b))
    return a.strip().lower() == b.strip().lower()


def project_from_url(url: str) -> tuple[CheckMethod, str] | None:
    """The PyPI project or GitHub owner/repo a URL points to; None for any other page."""
    url = url.strip()
    if m := PYPI_URL.fullmatch(url):
        return CheckMethod.PYPI, m.group(1)
    if (m := GITHUB_URL.fullmatch(url)) and m.group(1).lower() not in GITHUB_NOT_OWNERS:
        return CheckMethod.GITHUB_RELEASE, f"{m.group(1)}/{m.group(2)}"
    return None


def infer_check(
    check_target: str | None,
    source_url: str | None,
    attribute: str | None,
    value: str | None,
) -> tuple[CheckMethod, str] | None:
    """check_method and check_target for a latest-version fact whose source_url is a PyPI
    project or GitHub repository page; None if the rule does not apply.

    Only the attribute can make a claim a latest-version fact (is_version_fact).

    A caller's check_target is never replaced: the rule fires only if it is empty (the
    project from source_url becomes the target) or names the same project, and then it is
    kept exactly as given. A check_target that is a URL does not name a project, so the
    rule leaves such a claim alone.
    """
    if not source_url or not is_version_fact(attribute, value):
        return None
    found = project_from_url(source_url)
    if found is None:
        return None
    method, project = found
    if check_target is None:
        return method, project
    if same_project(method, check_target, project):
        return method, check_target
    return None

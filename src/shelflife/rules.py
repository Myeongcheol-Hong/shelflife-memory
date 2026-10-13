"""Write-time rules for the volatility and check_method a caller leaves empty (M2).

Rules only fill empty fields, and the claim records `rule` as their source. A value the
caller gave is never replaced (D5). Claude sets volatility only through `remember` (D4),
so these rules are the only classifier on the server.
"""

from __future__ import annotations

import re

from shelflife.models import CheckMethod, Volatility

# Words that mark how fast a fact changes (design 4.2), matched in the attribute first,
# then in the text. English words match as whole words (an "s" plural included), where
# only an ASCII letter breaks a word, so "API는" still matches "api". Korean words match
# anywhere, since particles attach to them.
KEYWORDS: dict[Volatility, list[str]] = {
    Volatility.FAST: """version release latest price pricing fee cost rank ranking score
        benchmark 가격 요금 비용 버전 릴리스 순위 점수""".split(),
    Volatility.MEDIUM: """feature api policy support eligibility status limit plan
        기능 정책 지원 자격 상태 한도 플랜""".split(),
    Volatility.SLOW: "history concept principle definition 역사 개념 원칙 정의".split(),
}

# A price written in the text or value ("$19.99", "300달러", "5,000원") is a fast fact.
MONEY = re.compile(r"[$€£¥₩]\s?\d|\d[\d,.]*\s?(?:원|달러|(?:usd|eur)(?![a-z]))", re.IGNORECASE)

# Facts about the newest version or release of a package or repository.
VERSION_WORDS = re.compile(r"version|release|latest|버전|릴리스|최신", re.IGNORECASE)
URL = re.compile(r"https?://", re.IGNORECASE)
PYPI_URL = re.compile(r"https?://pypi\.org/project/([A-Za-z0-9][A-Za-z0-9._-]*)/?.*", re.I)
GITHUB_URL = re.compile(
    r"https?://github\.com/([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?(?:[/?#].*)?", re.I
)


def _mentions(text: str, word: str) -> bool:
    if word.isascii():
        return re.search(rf"(?<![a-z]){re.escape(word)}s?(?![a-z])", text) is not None
    return word in text


def infer_volatility(attribute: str | None, text: str, value: str | None) -> Volatility | None:
    """The class whose keyword appears first in the attribute, then the text; None if none."""
    for where in (attribute, text):
        if not where:
            continue
        where = where.lower().replace("_", " ").replace("-", " ")
        for volatility, words in KEYWORDS.items():
            if any(_mentions(where, w) for w in words):
                return volatility
    if MONEY.search(text) or (value and MONEY.search(value)):
        return Volatility.FAST
    return None


def infer_check(
    check_target: str | None, source_url: str | None, attribute: str | None, text: str
) -> tuple[CheckMethod, str] | None:
    """check_method and check_target for a version fact whose URL is a PyPI or GitHub page.

    The URL is check_target when that is a URL, else source_url. A check_target that is
    not a URL is never replaced: the rule fires only if the URL names the same project.
    Only facts about a version or release qualify, so a GitHub repository URL behind a
    claim such as "X has no published eval" is not checked against the latest release.
    """
    if not VERSION_WORDS.search(f"{attribute or ''} {text}"):
        return None
    target_is_url = bool(check_target and URL.match(check_target))
    url = (check_target if target_is_url else source_url) or ""
    if m := PYPI_URL.fullmatch(url.strip()):
        found = CheckMethod.PYPI, m.group(1)
    elif m := GITHUB_URL.fullmatch(url.strip()):
        found = CheckMethod.GITHUB_RELEASE, m.group(1)
    else:
        return None
    if check_target and not target_is_url and check_target.lower() != found[1].lower():
        return None
    return found

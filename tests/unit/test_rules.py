from datetime import date, timedelta

import pytest

from shelflife.models import CheckMethod, FieldSource, Status, Volatility
from shelflife.rules import infer_check, infer_volatility

FAST, MEDIUM, SLOW = Volatility.FAST, Volatility.MEDIUM, Volatility.SLOW


# Each case has one path to its answer, so it tests what its comment names.
@pytest.mark.parametrize(
    ("attribute", "text", "value", "expected"),
    [
        ("exam_fee", "The AWS AIP-C01 exam is hard", None, FAST),  # keyword in the attribute
        (None, "Chatbox Pro costs a lot", None, FAST),  # plural "costs"
        (None, "Chatbox Pro is $19.99 a month", None, FAST),  # a price, no keyword
        (None, "Chatbox Pro per month", "$19.99", FAST),  # a price in the value only
        (None, "월 구독료는 5,000원이다", None, FAST),  # a price in won
        (None, "Chatbox Pro 가격은 비싸다", None, FAST),  # Korean keyword with a particle
        (None, "Chatbox Pro가격은 비싸다", None, FAST),  # Korean keyword fused to a Latin word
        (None, "Chatbox정책은 바뀌었다", None, MEDIUM),
        (None, "최신 모델은 Claude다", None, FAST),
        (None, "The refund policy allows 30 days", None, MEDIUM),
        (None, "Claude API는 빠르다", None, MEDIUM),  # particle on "API"
        (None, "Both plans include file uploads", None, MEDIUM),  # plural "plans"
        (None, "The concept of a write-ahead log", None, SLOW),
        (None, "개인정보의 정의는 법에 있다", None, SLOW),  # Korean keyword at a word start
        ("eligibility", "Partners pay the exam price", None, MEDIUM),  # attribute first
        (None, "We use the feedback form", None, None),  # "fee" is not a word here
        (None, "Frank drinks coffee", None, None),  # nor "rank" or "fee" here
        (None, "Seoul has 25 districts", None, None),
    ],
)  # fmt: skip
def test_infer_volatility(attribute, text, value, expected):
    assert infer_volatility(attribute, text, value) is expected


@pytest.mark.parametrize(
    ("attribute", "text", "value"),
    [
        (None, "ChatGPT Plus plan is $20 a month", None),  # medium keyword
        (None, "The all-time high in Bitcoin's history is $126,000", None),  # slow keyword
        ("pro_plan", "Chatbox Pro costs $19.99/month", None),  # keyword in the attribute
        ("plan", "Chatbox Pro per month", "$19.99"),  # price in the value only
        (None, "Claude Max 플랜은 월 100달러다", None),
        # Each price spelling, next to a medium keyword ("plan", "플랜").
        (None, "Claude Pro 플랜은 월 2만원이다", None),
        (None, "Pro 플랜은 월 2만 9천원이다", None),
        (None, "Pro 플랜은 월 2.9만 원이다", None),
        (None, "Pro 플랜은 월 20불이다", None),
        (None, "The Pro plan is 20 dollars a month", None),
        (None, "The Pro plan is USD 20 a month", None),
        (None, "The Pro plan is 20€ a month", None),
        (None, "The Pro plan is 20000 KRW", None),
        (None, "The Pro plan is 19.99 EUR", None),
    ],
)
def test_a_price_wins_over_every_keyword(attribute, text, value):
    assert infer_volatility(attribute, text, value) is FAST


@pytest.mark.parametrize(
    "text",
    [
        "The plan limit is 5 GB",
        "2만 명이 쓰는 플랜",  # 20,000 people, not won
        "The usda plan covers 20 states",
        "The plan includes 20 eurostar trips",
    ],
)
def test_a_number_without_a_currency_is_not_a_price(text):
    assert infer_volatility(None, text, None) is MEDIUM


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The support policy for the latest version", FAST),  # fast over medium
        ("The history of the Claude API", MEDIUM),  # medium over slow
    ],
)
def test_faster_classes_win_within_one_field(text, expected):
    assert infer_volatility(None, text, None) is expected


@pytest.mark.parametrize(
    "text",
    [
        "출시 일정의 변경은 없다",  # "정의" inside "일정의"
        "앱 설정의 기본값은 다크 모드다",  # "정의" inside "설정의"
    ],
)
def test_korean_keywords_do_not_match_inside_a_word(text):
    assert infer_volatility(None, text, None) is None


PYPI = "https://pypi.org/project/mcp/"
RELEASE = "https://github.com/getzep/graphiti/releases/tag/v0.30.2"
GH = CheckMethod.GITHUB_RELEASE


@pytest.mark.parametrize(
    ("check_target", "source_url", "attribute", "text", "value", "expected"),
    [
        (None, PYPI, "latest_version", "mcp is 2.3.0", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, PYPI, "최신 버전", "mcp", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, RELEASE, None, "The latest Graphiti release is v0.30.2", "v0.30.2",
         (GH, "getzep/graphiti")),
        (None, PYPI, None, "mcp 최신 버전은 2.3.0이다", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, "https://pypi.org/project/mcp/2.3.0/", "version", "x", "2.3.0",
         (CheckMethod.PYPI, "mcp")),  # a versioned PyPI page
        (None, "https://github.com/x/y.git", "release", "y", "1.0", (GH, "x/y")),
        (None, "https://www.github.com/getzep/graphiti", "latest_release", "x", "v0.30.2",
         (GH, "getzep/graphiti")),
        # A check_target naming the same project is kept exactly as given.
        ("MCP", PYPI, "version", "mcp", "2.3.0", (CheckMethod.PYPI, "MCP")),
        ("claude_agent_sdk", "https://pypi.org/project/claude-agent-sdk/", "latest_version",
         "x", "0.2.165", (CheckMethod.PYPI, "claude_agent_sdk")),  # PEP 503 names
        ("GetZep/Graphiti", RELEASE, "latest_release", "x", "v0.30.2",
         (GH, "GetZep/Graphiti")),
        ("claude-agent-sdk", "https://pypi.org/project/claude_agent_sdk/", "latest_version",
         "x", "0.2.165", (CheckMethod.PYPI, "claude-agent-sdk")),  # normalized URL side too
        # Other spellings of a latest-version fact.
        (None, PYPI, "current_version", "x", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, PYPI, "newest_release", "x", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, PYPI, "latest_stable_version", "x", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, PYPI, "Latest-Version", "x", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, PYPI, None, "The current version of mcp is 2.3.0", "2.3.0",
         (CheckMethod.PYPI, "mcp")),
        (None, PYPI, None, "The newest mcp release is 2.3.0", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, PYPI, None, "Latest Version of mcp: 2.3.0", "2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, RELEASE, "최신 릴리스", "x", "v0.30.2", (GH, "getzep/graphiti")),
        (None, RELEASE, "버전", "x", "v0.30.2", (GH, "getzep/graphiti")),
        (None, RELEASE, None, "Graphiti 최신 릴리스는 v0.30.2이다", "v0.30.2",
         (GH, "getzep/graphiti")),
        (None, RELEASE, None, "Graphiti의 최신 안정 버전은 v0.30.2이다", "v0.30.2",
         (GH, "getzep/graphiti")),
        # A repository page with a query or fragment.
        (None, "https://github.com/getzep/graphiti?tab=readme-ov-file", "latest_release", "x",
         "v0.30.2", (GH, "getzep/graphiti")),
        (None, "https://github.com/getzep/graphiti#readme", "latest_release", "x", "v0.30.2",
         (GH, "getzep/graphiti")),
    ],
)  # fmt: skip
def test_infer_check(check_target, source_url, attribute, text, value, expected):
    assert infer_check(check_target, source_url, attribute, text, value) == expected


@pytest.mark.parametrize(
    ("check_target", "source_url", "attribute", "text", "value"),
    [
        # The check_target is never replaced.
        ("other", PYPI, "version", "mcp", "2.3.0"),
        (PYPI, PYPI, "version", "mcp", "2.3.0"),  # a URL does not name a project
        ("https://example.com/changelog", PYPI, "version", "mcp", "2.3.0"),
        ("x/my_repo", "https://github.com/x/my-repo", "latest_release", "x", "1.0"),  # not PEP 503
        # Not a fact about the latest version or release.
        (None, "https://github.com/ac12644/MemGuard", "published_eval",
         "MemGuard has not published eval results", None),
        (None, "https://github.com/ac12644/MemGuard", None,
         "MemGuard has not released eval results", None),
        (None, PYPI, "python_version", "mcp requires Python version 3.10 or later", "3.10"),
        (None, PYPI, None, "mcp requires Python version 3.10 or later", "3.10"),
        (None, PYPI, "release_date", "mcp 2.0 was released on 2026-03-01", "2026-03-01"),
        (None, PYPI, None, "mcp 2.0 was released on 2026-03-01", "2026-03-01"),
        (None, RELEASE, "license", "Graphiti is released under the Apache-2.0 license",
         "Apache-2.0"),
        (None, PYPI, None, "The versioning policy of mcp is SemVer", "SemVer"),
        (None, PYPI, None, "The latest versioning policy of mcp is 2.0", "2.0"),
        # The attribute decides, even when the text names a latest release.
        (None, PYPI, "python_version", "The latest version of mcp requires Python 3.10",
         "3.10"),
        (None, PYPI, "release_date", "The latest mcp release came out on 2026-03-01",
         "2026-03-01"),
        # The text names a latest release, but the value is not a version.
        (None, RELEASE, None, "The latest Graphiti release supports Python 3.10 or later",
         "3.10 or later"),
        (None, PYPI, "latest_version", "The latest version of mcp", None),  # no value
        (None, PYPI, "latest_version", "The latest version of mcp", "2.3 or later"),
        # Not a PyPI project or GitHub repository page.
        (None, "https://github.com/orgs/anthropics/repositories", "latest_release", "x",
         "v1.0"),
        (None, "https://github.com/marketplace/actions/checkout", "latest_version", "x",
         "v4.2.2"),
        (None, "https://github.com/topics/mcp", "latest_release", "x", "v1.0"),
        (None, "https://github.com/advisories/GHSA-abcd-efgh-ijkl", "latest_release", "x",
         "2.3.1"),
        (None, "https://example.org/project/mcp/", "version", "x", "1.0"),
        (None, "https://example.com/pricing", "version", "x", "1.0"),
        (None, None, "version", "x", "1.0"),
    ],
)  # fmt: skip
def test_infer_check_does_not_apply(check_target, source_url, attribute, text, value):
    assert infer_check(check_target, source_url, attribute, text, value) is None


# --- applied at write time ------------------------------------------------------------


def test_rules_fill_empty_fields_and_record_their_source(store):
    claim = store.remember(
        "The latest version of mcp on PyPI is 2.3.0",
        "world_fact",
        attribute="latest_version",
        value="2.3.0",
        source_url=PYPI,
    )
    assert (claim.volatility, claim.volatility_source) == (Volatility.FAST, FieldSource.RULE)
    assert (claim.check_method, claim.check_method_source) == (CheckMethod.PYPI, FieldSource.RULE)
    assert claim.check_target == "mcp"
    assert claim.status is Status.FRESH  # checkable now, so not unverifiable


def test_rules_never_replace_caller_values(store):
    claim = store.remember(
        "The latest version of mcp on PyPI is 2.3.0",
        "world_fact",
        volatility="slow",
        check_method="web_page",
        check_target=PYPI,
    )
    assert (claim.volatility, claim.volatility_source) == (Volatility.SLOW, FieldSource.CALLER)
    assert (claim.check_method, claim.check_method_source) == (
        CheckMethod.WEB_PAGE,
        FieldSource.CALLER,
    )
    assert claim.check_target == PYPI


@pytest.mark.parametrize(
    ("text", "fields", "expected"),
    [
        ("mcp on PyPI is 2.3.0", {"attribute": "latest_version", "value": "2.3.0",
         "source_url": PYPI}, (FAST, CheckMethod.PYPI)),  # the attribute alone qualifies
        ("Partners pay the exam price", {"attribute": "eligibility"}, (MEDIUM, CheckMethod.NONE)),
        ("Chatbox Pro per month", {"value": "$19.99"}, (FAST, CheckMethod.NONE)),
        ("The refund policy allows 30 days", {}, (MEDIUM, CheckMethod.NONE)),
    ],
)  # fmt: skip
def test_rules_read_the_attribute_and_value_at_write_time(store, text, fields, expected):
    claim = store.remember(text, "world_fact", **fields)
    assert (claim.volatility, claim.check_method) == expected
    assert claim.volatility_source is FieldSource.RULE
    assert claim.next_check_at == date(2026, 10, 12) + timedelta(
        days=7 if expected[0] is FAST else 30
    )


@pytest.mark.parametrize(
    ("check_target", "method", "status"),
    [
        ("MCP", CheckMethod.PYPI, Status.FRESH),  # same project: the rule fires
        (PYPI, CheckMethod.NONE, Status.UNVERIFIABLE),
        ("https://example.com/changelog", CheckMethod.NONE, Status.UNVERIFIABLE),
    ],
)
def test_rules_keep_the_callers_check_target(store, check_target, method, status):
    claim = store.remember(
        "The latest version of mcp on PyPI is 2.3.0",
        "world_fact",
        attribute="latest_version",
        value="2.3.0",
        source_url=PYPI,
        check_target=check_target,
    )
    assert (claim.check_method, claim.check_target, claim.status) == (method, check_target, status)


def test_rules_apply_to_world_facts_only(store):
    claim = store.remember("We chose the cheapest price plan", "decision")
    assert (claim.volatility, claim.volatility_source) == (Volatility.NONE, FieldSource.DEFAULT)
    claim = store.remember("Chatbox Pro is $19.99 a month", "note")
    assert (claim.volatility, claim.volatility_source) == (Volatility.NONE, FieldSource.DEFAULT)
    # A decision about a version is never given a check (remember would refuse one).
    claim = store.remember(
        "We pin mcp to the latest version, 2.3.0",
        "decision",
        attribute="latest_version",
        value="2.3.0",
        source_url=PYPI,
    )
    assert (claim.check_method, claim.check_method_source) == (
        CheckMethod.NONE,
        FieldSource.DEFAULT,
    )

import pytest

from shelflife.models import CheckMethod, FieldSource, Status, Volatility
from shelflife.rules import infer_check, infer_volatility


@pytest.mark.parametrize(
    ("attribute", "text", "value", "expected"),
    [
        ("exam_fee", "The AWS AIP-C01 exam fee is $300", "$300", Volatility.FAST),
        (None, "Chatbox Pro costs $19.99 a month", None, Volatility.FAST),  # plural "costs"
        (None, "Chatbox Pro 가격은 월 $19.99이다", None, Volatility.FAST),
        (None, "월 구독료는 5,000원이다", None, Volatility.FAST),  # a price, no keyword
        (None, "The refund policy allows 30 days", None, Volatility.MEDIUM),
        (None, "Claude API는 스트리밍을 지원한다", None, Volatility.MEDIUM),  # particle on "API"
        (None, "The concept of a write-ahead log", None, Volatility.SLOW),
        ("eligibility", "Partners pay the exam price", None, Volatility.MEDIUM),  # attribute first
        (None, "We use the feedback form", None, None),  # "fee" is not a word here
        (None, "Seoul has 25 districts", None, None),
    ],
)
def test_infer_volatility(attribute, text, value, expected):
    assert infer_volatility(attribute, text, value) is expected


PYPI = "https://pypi.org/project/mcp/"
RELEASE = "https://github.com/getzep/graphiti/releases/tag/v0.30.2"


@pytest.mark.parametrize(
    ("check_target", "source_url", "attribute", "text", "expected"),
    [
        (None, PYPI, "latest_version", "mcp is 2.3.0", (CheckMethod.PYPI, "mcp")),
        (None, RELEASE, None, "The latest Graphiti release is v0.30.2",
         (CheckMethod.GITHUB_RELEASE, "getzep/graphiti")),
        ("https://github.com/x/y.git", None, "release", "y", (CheckMethod.GITHUB_RELEASE, "x/y")),
        ("MCP", PYPI, "version", "mcp", (CheckMethod.PYPI, "mcp")),  # target agrees
        ("other", PYPI, "version", "mcp", None),  # target disagrees: never replaced
        (None, "https://github.com/ac12644/MemGuard", "published_eval",
         "MemGuard has not published eval results", None),  # not a version fact
        (None, "https://example.com/pricing", "version", "x", None),
        (None, None, "version", "x", None),
    ],
)  # fmt: skip
def test_infer_check(check_target, source_url, attribute, text, expected):
    assert infer_check(check_target, source_url, attribute, text) == expected


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


def test_rules_apply_to_world_facts_only(store):
    claim = store.remember("We chose the cheapest price plan", "decision")
    assert (claim.volatility, claim.volatility_source) == (Volatility.NONE, FieldSource.DEFAULT)

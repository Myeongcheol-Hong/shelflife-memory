"""The web_page judgment: its template, render() and validate() (D10, design 5.3)."""

import hashlib
from datetime import date, datetime
from pathlib import Path

import pytest

from shelflife.models import CheckMethod, CheckResult, Claim, FieldSource, Kind, Status, Volatility
from shelflife.verifiers import judgment
from shelflife.verifiers.judgment import (
    InvalidJudgment,
    Judgment,
    fold,
    render,
    same_value,
    validate,
    value_in,
)
from shelflife.verifiers.section import Section, select_section
from shelflife.verifiers.web_page import decode, extract, normalize, page_text

PAGES = Path(__file__).parents[1] / "fixtures" / "pages"


def claim(value="$300", **changes):
    fields = dict(
        id="c1",
        text="The AWS AIP-C01 exam fee is $300",
        kind=Kind.WORLD_FACT,
        subject="AWS AIP-C01",
        attribute="exam_fee",
        value=value,
        volatility=Volatility.FAST,
        volatility_source=FieldSource.CALLER,
        check_method=CheckMethod.WEB_PAGE,
        check_method_source=FieldSource.CALLER,
        check_target="https://example.com/exam",
        source_url=None,
        source_quote=None,
        observed_at=date(2026, 10, 9),
        recorded_at=datetime(2026, 10, 9, 12, 0),
        last_checked_at=None,
        next_check_at=None,
        status=Status.FRESH,
    )
    return Claim(**(fields | changes))


# A page of three blocks; the section is the middle one.
BLOCKS = [
    "Other exams cost $150 each, and the retake fee is $150 too.",
    "The exam fee is $300 per attempt, paid when you book.",
    "Fees are listed in US dollars. The exam fee is $300 per attempt.",
]
PAGE = normalize("\n".join(BLOCKS))
START = PAGE.index(BLOCKS[1])
SECTION = Section(
    text=BLOCKS[1],
    heading=None,
    start=START,
    end=START + len(BLOCKS[1]),
    blocks=range(1, 2),
    core=range(1, 2),
    score=1.0,
    runner_up=0.0,
)


QUOTE = "$300 per attempt, paid when"  # once on the page, inside the section


def check(result, value="$300", **kwargs):
    return validate(result, value=value, page=PAGE, section=SECTION, **kwargs)


def test_the_template_is_pinned_to_its_version():
    # A change to the template needs a new PROMPT_VERSION, then a new hash here.
    digest = hashlib.sha256(judgment.TEMPLATE.encode()).hexdigest()
    assert (judgment.PROMPT_VERSION, digest) == (
        "j1",
        "901f0a4e554c7707e9133833da2f9de5b1546bad4fbc4113e4c44caa5b978de7",
    )


def test_render_fills_in_the_claim_and_fences_the_section():
    section = Section("Fee: $300 ``` not a fence ````", None, 0, 30, range(1), range(1), 1, 0)
    prompt = render(claim(), section, "https://example.com/exam")
    assert "Claim id: c1\n" in prompt
    assert "Remembered value: $300\n" in prompt
    assert "Remembered on: 2026-10-09\n" in prompt
    assert "Page: https://example.com/exam\n" in prompt
    assert "\n`````\nFee: $300 ``` not a fence ````\n`````\n" in prompt  # 5 > 4 backticks


def test_render_says_when_a_claim_has_no_value():
    prompt = render(claim(value=None, subject=None), SECTION, "https://example.com/exam")
    assert "Remembered value: (none: judge the claim as a whole)\n" in prompt
    assert "Subject: (none)\n" in prompt
    assert "\n```\n" + BLOCKS[1] + "\n```\n" in prompt


def test_same_with_the_value_in_the_quote():
    quote = " fee is\u200b $300  per attempt, paid"  # normalized before it is checked
    assert check("same", quote=quote) == Judgment(
        CheckResult.SAME, quote="fee is $300 per attempt, paid"
    )


def test_changed_with_a_new_value_in_the_quote():
    assert check("changed", value="$250", quote=QUOTE, new_value=" $300") == (
        Judgment(CheckResult.CHANGED, quote=QUOTE, new_value="$300")
    )


def test_cannot_tell_keeps_only_the_reason():
    assert check("cannot_tell", quote="anything", new_value="$1", reason=" page is a login ") == (
        Judgment(CheckResult.CANNOT_TELL, reason="page is a login")
    )
    assert check("cannot_tell", reason=" ") == Judgment(CheckResult.CANNOT_TELL)


@pytest.mark.parametrize(
    ("result", "kwargs", "error"),
    [
        ("error", {}, "server only"),
        ("unsure", {}, "result must be one of"),
        ("same", {}, "at least 20 characters"),
        ("same", {"quote": "exam fee is $300"}, "at least 20 characters"),  # 16 characters
        ("same", {"quote": "fee_is_$300_per_attempt"}, "3 words"),
        ("same", {"quote": "the exam fee is $300 per attempt"}, "not on the page"),  # case
        ("same", {"quote": "The exam fee is $300 per attempt"}, "more than once"),
        ("same", {"quote": "the retake fee is $150 too"}, "not inside the section"),
        ("same", {"quote": "per attempt, paid when you book"}, "does not contain the claim's"),
        ("changed", {"quote": QUOTE}, "needs new_value"),
        ("changed", {"quote": QUOTE, "new_value": "$250"}, "does not contain"),
        ("changed", {"quote": QUOTE, "new_value": "300 USD"}, "record same"),
    ],
)
def test_refused(result, kwargs, error):
    with (
        pytest.raises(InvalidJudgment, match=error)
        if result != "unsure"
        else pytest.raises(ValueError, match=error)
    ):
        check(result, **kwargs)


def test_a_quote_may_not_run_past_the_section():
    # Starts inside the section and ends in the next block.
    quote = "paid when you book. Fees are listed"
    assert PAGE.count(quote) == 1
    with pytest.raises(InvalidJudgment, match="not inside the section"):
        check("same", value=None, quote=quote)


def test_overlapping_places_count_twice():
    page = "na na na na na na na na"  # the quote below starts at 0 and at 3
    section = Section(page, None, 0, len(page), range(1), range(1), 1.0, 0.0)
    with pytest.raises(InvalidJudgment, match="more than once"):
        validate("same", value=None, page=page, section=section, quote="na na na na na na na")


def test_a_claim_without_a_value_gets_the_quote_rules_only():
    quote = "paid when you book"  # 18 characters: too short even without a value
    with pytest.raises(InvalidJudgment, match="at least 20"):
        check("same", value=None, quote=quote)
    quote = "per attempt, paid when you book"
    assert check("same", value=None, quote=quote).quote == quote
    assert check("changed", value=None, quote=quote).new_value is None
    with pytest.raises(InvalidJudgment, match="does not contain new_value"):
        check("changed", value=None, quote=quote, new_value="$250")  # given: must be quoted


@pytest.mark.parametrize(
    ("name", "text", "subject", "attribute", "value", "quote"),
    [
        (
            "aws-aip-c01",
            "The AWS AIP-C01 exam fee is $300",
            "AWS AIP-C01",
            "exam_fee",
            "$300",
            "multiple response Exam cost 300 USD",
        ),
        (
            "benchmarks-metagenomics",
            "The top MetagenomicsBench pass rate is about 60%",
            "MetagenomicsBench",
            "top_pass_rate",
            "60%",
            "Claude Code | Anthropic | 60.0%",
        ),
    ],
)
def test_a_real_quote_from_a_recorded_page(name, text, subject, attribute, value, quote):
    blocks = extract(decode((PAGES / f"{name}.html").read_bytes()))
    section = select_section(blocks, text=text, subject=subject, attribute=attribute, value=value)
    page = normalize(page_text(blocks))
    found = validate("same", value=value, page=page, section=section, quote=quote)
    assert found == Judgment(CheckResult.SAME, quote=quote)


@pytest.mark.parametrize(
    ("value", "text", "found"),
    [
        ("$300", "Exam cost 300 USD", True),
        ("$300", "USD 300 per exam", True),
        ("$300", "응시료는 300달러입니다", True),  # Hangul may run on
        ("$300", "US$300", True),
        ("$125", "Foundations $125 USD Prep courses", True),
        ("$300", "$300.00", True),
        ("$300", "AU$300", False),  # another currency
        ("$30", "$300", False),
        ("$300", "$1,300", False),
        ("월 9,900원", "월 9900원입니다", True),
        ("60%", "pass rate 60.0%", True),
        ("60%", "160%", False),
        ("60%", "1.60%", False),
        ("2.3", "version 2.3.0", False),  # a version is not folded
        ("2.3.0", "version 2.3", False),
        ("v2", "v2.1", False),
        ("Pro", "Professional", False),  # a Latin word must not run on
        ("Pro", "NonPro plan", False),
        ("AIP-C01", "AIP\u2013C01", True),  # dashes
        ("\u201cbeta\u201d", '"beta"', True),  # quote marks
        ("Partner Network", "partner network", False),  # case is kept
    ],
)
def test_value_in(value, text, found):
    assert value_in(value, text) is found


def test_values_are_compared_after_folding():
    assert same_value("$300", "300 USD")
    assert same_value("$125", "$125 USD")  # symbol and code together are one amount
    assert same_value("₩9,900", "9900원")
    assert not same_value("$300", "$250")
    assert fold("USD 1,000.0 \u2014 €5") == "1000 USD - 5 EUR"

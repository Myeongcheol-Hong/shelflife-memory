from pathlib import Path

import pytest

from shelflife.verifiers.section import Weights, select_section, terms
from shelflife.verifiers.web_page import Block, decode, extract, normalize, page_text

PAGES = Path(__file__).parents[1] / "fixtures" / "pages"


def page(name):
    return extract(decode((PAGES / f"{name}.html").read_bytes()))


def check_offsets(blocks, section):
    assert normalize(page_text(blocks))[section.start : section.end] == normalize(section.text)
    assert section.text == "\n".join(blocks[i].text for i in section.blocks)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The Exam_Fee is $300", {"exam", "fee", "300"}),
        ("Chatbox가격은 월 9,900원", {"chatbox", "가격은", "월", "900", "원"}),  # "9": one letter
        ("A b of the MCP", {"mcp"}),  # stop words and one-letter Latin words dropped
        (None, set()),
    ],
)
def test_terms(text, expected):
    assert terms(text) == expected


def test_a_short_page_is_returned_whole():
    blocks = [Block("Pricing", "h1", ()), Block("Pro: $20 a month", "p", ("main",))]
    section = select_section(blocks, text="Pro costs $20 a month", value="$20")
    assert (section.blocks, section.heading, section.value_found) == (range(2), None, True)
    check_offsets(blocks, section)


# The seed claims' fields, with the values the owner asked for in D10.
SEEDS = [
    ("skilljar-faq", "Claude certification exams are open only to employees of Claude "
     "Partner Network members", "Claude certification", "eligibility",
     "only to organizations in the Claude Partner Network",
     "Certification is currently available only to organizations in the Claude Partner Network."),
    ("skilljar-partner", "The Claude Certified Developer - Foundations exam fee is $125",
     "Claude Certified Developer - Foundations", "exam_fee", "$125",
     "Claude Certified Developer – Foundations Foundations $125 USD"),
    ("aws-aip-c01", "The AWS AIP-C01 exam fee is $300", "AWS AIP-C01", "exam_fee", "$300",
     "300 USD. Visit Exam pricing"),
    ("databricks-genai", "The Databricks GenAI Engineer Associate exam fee is $200, valid "
     "for 2 years", "Databricks GenAI Engineer Associate", "exam_fee", "$200",
     "Registration fee: $200"),
    ("benchmarks-metagenomics", "The top MetagenomicsBench pass rate is about 60%",
     "MetagenomicsBench", "top_pass_rate", "60%", "Claude Code | Anthropic | 60.0%"),
]  # fmt: skip


@pytest.mark.parametrize(("name", "text", "subject", "attribute", "value", "evidence"), SEEDS)
def test_the_section_holds_each_seeds_evidence(name, text, subject, attribute, value, evidence):
    blocks = page(name)
    section = select_section(blocks, text=text, subject=subject, attribute=attribute, value=value)
    assert evidence in normalize(section.text)
    assert len(section.text) <= Weights().budget
    check_offsets(blocks, section)


def test_the_aws_fee_is_found_under_its_heading():
    blocks = page("aws-aip-c01")
    section = select_section(blocks, text="The AWS AIP-C01 exam fee is $300", subject="AWS AIP-C01",
                             attribute="exam_fee", value="$300")  # fmt: skip
    assert section.heading == "Exam cost"  # "fee" matches "cost"
    assert len(normalize(page_text(blocks))) > Weights().budget  # it was selected, not whole


def test_the_aws_fee_is_found_after_the_price_changes():
    # Many headings say "Exam"; only "fee" -> "cost" finds the right one without the value.
    blocks = [
        Block(b.text.replace("300 USD", "350 USD"), b.tag, b.landmarks) for b in page("aws-aip-c01")
    ]
    section = select_section(blocks, text="The AWS AIP-C01 exam fee is $300", subject="AWS AIP-C01",
                             attribute="exam_fee", value="$300")  # fmt: skip
    assert section.heading == "Exam cost" and "350 USD" in section.text
    assert not section.value_found


def developer_fee(blocks):
    return select_section(
        blocks,
        text="The Claude Certified Developer - Foundations exam fee is $125",
        subject="Claude Certified Developer - Foundations",
        attribute="exam_fee",
        value="$125",
    )


def test_the_value_does_not_pick_the_section_on_a_changed_page():
    # The partner page lists $125 for two exams. When the Developer price changes, the
    # section must still hold the Developer row, not the Architect row that kept $125.
    blocks = page("skilljar-partner")
    row = next(i for i, b in enumerate(blocks) if b.text.startswith("Claude Certified Developer"))
    changed = blocks.copy()
    changed[row] = Block(blocks[row].text.replace("$125", "$150"), blocks[row].tag, ())
    before, after = developer_fee(blocks), developer_fee(changed)
    assert row in before.blocks and row in after.blocks
    assert (before.value_found, after.value_found) == (True, True)  # the Architect row
    assert "$150 USD" in after.text
    assert after.heading == before.heading == "All certifications"


def block(text, tag="p", landmarks=("main",)):
    return Block(text, tag, landmarks)


FILLER = [block("x" * 60) for _ in range(5)]


def two_sections(first, second):
    return [block("Plans", "h2"), first, *FILLER, block("Other plans", "h2"), second, *FILLER]


def test_the_value_only_breaks_ties():
    tied = two_sections(block("Team plan fee: $30"), block("Team plan fee: $25"))
    section = select_section(tied, text="The Team plan fee is $25", value="$25",
                             weights=Weights(budget=200))  # fmt: skip
    assert section.heading == "Other plans" and section.value_found

    # A segment that covers more of the claim's words wins without the value.
    better = two_sections(block("Team plan fee: $30"), block("Fee: $25"))
    section = select_section(better, text="The Team plan fee is $25", value="$25",
                             weights=Weights(budget=200))  # fmt: skip
    assert section.heading == "Plans" and section.score > section.runner_up


def test_long_words_match_by_their_first_six_letters():
    blocks = two_sections(block("Exam fee: $99"), block("Certified exam fee: $99"))
    section = select_section(blocks, text="The certification exam fee", weights=Weights(budget=200))
    assert section.heading == "Other plans"  # "certification" found "Certified"


def test_navigation_counts_half():
    # Two segments with the same words; one sits in the page's header navigation.
    nav = ("header", "nav")
    blocks = [
        block("Team plan", "h2", nav),
        block("fee", "li", nav),
        block("Team plan", "h2"),
        block("The fee is $25 a month"),
        *FILLER,
    ]
    section = select_section(blocks, text="The Team plan fee", weights=Weights(budget=200))
    assert (section.score, section.runner_up) == (5.0, 2.5)  # 3 words + 2 in the heading
    assert 3 in section.blocks
    even = select_section(blocks, text="The Team plan fee", weights=Weights(budget=200, chrome=1))
    assert (even.score, even.runner_up) == (5.0, 5.0)
    assert even.blocks.start == 0  # a tie: the earlier segment wins


def test_a_long_segment_is_cut_around_its_best_block():
    rows = [block(f"Row {i}: nothing here " + "y" * 40) for i in range(40)]
    rows[30] = block("Row 30: Team plan fee $25")
    blocks = [block("All plans", "h2"), *rows]
    section = select_section(blocks, text="Team plan fee", weights=Weights(budget=300))
    assert 31 in section.blocks and len(section.text) <= 300
    assert section.heading == "All plans"
    check_offsets(blocks, section)


def test_selection_is_deterministic():
    blocks = page("skilljar-faq")
    args = {"text": "Who can take a Claude certification exam", "attribute": "eligibility"}
    assert select_section(blocks, **args) == select_section(blocks, **args)

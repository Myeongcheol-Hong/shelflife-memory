import subprocess
import sys
from pathlib import Path

import pytest

from shelflife.verifiers import section as sel
from shelflife.verifiers.section import Weights, select_section, terms
from shelflife.verifiers.web_page import Block, decode, extract, normalize, page_text

PAGES = Path(__file__).parents[1] / "fixtures" / "pages"


def page(name):
    return extract(decode((PAGES / f"{name}.html").read_bytes()))


def check_offsets(blocks, section):
    assert normalize(page_text(blocks))[section.start : section.end] == normalize(section.text)


def block(text, tag="p", landmarks=("main",)):
    return Block(text, tag, landmarks)


FILLER = [block("x" * 60) for _ in range(5)]
SMALL = Weights(budget=200)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The Exam_Fee is $300", {"exam", "fee", "300"}),
        ("Chatbox의 가격은 월 9,900원", {"chatbox", "가격", "월", "9,900", "원"}),
        ("AI모델은 속도가 회의", {"ai", "모델", "속도", "회의"}),  # 2 characters must remain
        ("API에서는", {"api"}),  # a stacked particle is not left as a term
        ("mcp v2.3.0 and Claude Sonnet 5.5", {"mcp", "v2.3.0", "claude", "sonnet", "5.5"}),
        ("A b of the top 3 MCP", {"top", "3", "mcp"}),  # one-letter words, not digits, dropped
        (None, set()),
    ],
)
def test_terms(text, expected):
    assert terms(text) == expected


@pytest.mark.parametrize(
    ("word", "text", "found"),
    [
        ("pro", "pro plan", True),
        ("pro", "a product page", False),  # a short word is a whole word
        ("fee", "exam fee: $125", True),
        ("fee", "send us feedback", False),
        ("fee", "cost-effective training", False),  # a synonym, not inside a compound
        ("fee", "exam cost: 300 usd", True),
        ("certification", "claude certified developer", True),  # first six letters
        ("certification", "recertified", False),  # ... at the start of a word
        ("c01", "aws aip-c01 exam", True),
        ("5.5", "claude sonnet 5.5 | pi", True),
        ("5.5", "version 15.5", False),
        ("9,900", "월 9,900원", True),
        ("가격", "chatbox 가격은 월 9,900원", True),  # Hangul inside a word
        ("가격", "시험 수수료는 300달러", True),  # a synonym
    ],
)
def test_how_words_match(word, text, found):
    assert bool(sel._pattern(word).search(text)) is found


def test_a_short_page_is_returned_whole():
    blocks = [Block("Pricing", "h1", ()), Block("Pro: $20 a month", "p", ("main",))]
    section = select_section(blocks, text="Pro costs $20 a month", value="$20")
    assert (section.blocks, section.core, section.heading) == (range(2), range(2), None)
    check_offsets(blocks, section)


# Claims about the recorded pages. The first five are the seed claims, with the values the
# owner asked for in D10; the others are examples written for these tests. None of them is
# an eval label: tests, not eval/data.
CLAIMS = [
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
    ("skilljar-faq", "Claude certification exams last 120 minutes", "Claude certification exam",
     "exam_duration", "120 minutes", "You have 120 minutes to answer them"),
    ("skilljar-faq", "A Claude certification exam can be rescheduled up to 48 hours before the "
     "appointment", "Claude certification exam", "reschedule_deadline", "48 hours",
     "48 hours prior to"),
    ("skilljar-faq", "Claude certifications are valid for 12 months", "Claude certification",
     "validity_period", "12 months", "12 months from the date you earn it"),
    ("skilljar-faq", "A Claude exam retake costs the full exam fee", "Claude certification exam",
     "retake_fee", "full exam fee", "A retake is the full exam fee"),
    ("aws-aip-c01", "The AWS AIP-C01 exam duration is 180 minutes", "AWS AIP-C01",
     "exam_duration", "180 minutes", "180 minutes"),
    ("databricks-genai", "Application Development is 30% of the Databricks GenAI Engineer "
     "Associate exam", "Databricks GenAI Engineer Associate", "application_development_weight",
     "30%", "Application Development – 30%"),
    pytest.param("skilljar-faq", "A Claude certification exam registration is valid for 5 years",
                 "Claude certification exam", "registration_validity", "5 years",
                 "your registration is valid for 5 years",
                 marks=pytest.mark.xfail(strict=True, reason="ties with another FAQ entry")),
    pytest.param("skilljar-faq", "A Claude exam no-show forfeits the exam fee",
                 "Claude certification exam", "no_show_policy", "forfeit the exam fee",
                 "you forfeit the exam fee",
                 marks=pytest.mark.xfail(strict=True, reason="ties with another FAQ entry")),
]  # fmt: skip


@pytest.mark.parametrize(("name", "text", "subject", "attribute", "value", "evidence"), CLAIMS)
def test_the_section_holds_the_evidence(name, text, subject, attribute, value, evidence):
    blocks = page(name)
    section = select_section(blocks, text=text, subject=subject, attribute=attribute, value=value)
    assert evidence in normalize(section.text)
    assert len(section.text) <= Weights().budget
    check_offsets(blocks, section)


@pytest.mark.parametrize(
    ("index", "heading"),
    [
        # The FAQ claim's attribute word is in another question ("Which certifications
        # count towards Claude Partner Network eligibility?"); the evidence comes in only
        # because the section grows, so its core misses it.
        pytest.param(0, "Can customers or non-partners get certified?",
                     marks=pytest.mark.xfail(strict=True, reason="found by growth only")),
        (1, "All certifications"),
        (2, "Exam cost"),
        (3, "Assessment Details"),
    ],
)  # fmt: skip
def test_the_core_of_a_seed_section_holds_the_evidence(index, heading):
    name, text, subject, attribute, value, evidence = CLAIMS[index]
    blocks = page(name)
    section = select_section(blocks, text=text, subject=subject, attribute=attribute, value=value)
    assert section.heading == heading
    assert evidence in normalize(" ".join(blocks[i].text for i in section.core))


def test_the_aws_fee_is_found_after_the_price_changes():
    # Many headings say "Exam"; without the value, only "fee" -> "cost" finds this one.
    blocks = [Block(b.text.replace("300 USD", "350 USD"), b.tag, b.landmarks)
              for b in page("aws-aip-c01")]  # fmt: skip
    section = select_section(blocks, text="The AWS AIP-C01 exam fee is $300", subject="AWS AIP-C01",
                             attribute="exam_fee", value="$300")  # fmt: skip
    assert section.heading == "Exam cost" and "350 USD" in section.text


def test_the_value_does_not_pick_the_row_on_a_changed_page():
    # The partner page lists $125 for the Developer and the Architect exams. A budget this
    # small cuts the segment to one row; after the Developer price changes, the row must
    # still be the Developer one, not the Architect one that kept $125.
    blocks = page("skilljar-partner")
    row = next(i for i, b in enumerate(blocks) if b.text.startswith("Claude Certified Developer"))
    assert blocks[row + 1].text.startswith("Claude Certified Architect – Foundations")
    changed = blocks.copy()
    changed[row] = Block(blocks[row].text.replace("$125", "$150"), blocks[row].tag, ())
    claim = {
        "text": "The Claude Certified Developer - Foundations exam fee is $125",
        "subject": "Claude Certified Developer - Foundations",
        "attribute": "exam_fee",
        "value": "$125",
    }
    for pg in (blocks, changed):
        assert select_section(pg, weights=Weights(budget=120), **claim).core == range(row, row + 1)


def two_sections(first, second, headings=("Plans", "Other plans")):
    return [block(headings[0], "h2"), first, *FILLER, block(headings[1], "h2"), second, *FILLER]


def test_the_value_only_breaks_ties():
    tied = two_sections(block("Team plan fee: $30"), block("Team plan fee: $25"))
    section = select_section(tied, text="The Team plan fee is $25", value="$25", weights=SMALL)
    assert section.heading == "Other plans"
    better = two_sections(block("Team plan fee: $30"), block("Fee: $25"))
    section = select_section(better, text="The Team plan fee is $25", value="$25", weights=SMALL)
    assert section.heading == "Plans" and section.score > section.runner_up


def test_ties_go_to_the_earlier_segment():
    tied = two_sections(block("Team plan fee"), block("Team plan fee"), ("Monthly", "Yearly"))
    assert select_section(tied, text="Team plan fee", weights=SMALL).heading == "Monthly"


def test_subject_and_attribute_words_weigh_more():
    blocks = two_sections(
        block("Annual team discount"), block("Pro plan fee"), ("Monthly", "Yearly")
    )
    args = {"text": "Annual team discount for the pro plan fee", "subject": "Pro plan"}
    section = select_section(blocks, attribute="fee", weights=SMALL, **args)
    assert section.heading == "Yearly"  # pro, plan, fee: 2 each; annual, team, discount: 1
    even = select_section(blocks, attribute="fee", weights=Weights(budget=200, subject=1,
                          attribute=1), **args)  # fmt: skip
    assert (even.heading, even.score, even.runner_up) == ("Monthly", 3.0, 3.0)


def test_value_words_stay_attribute_words():
    # The value "full exam fee" shares "fee" with the attribute; "fee" must still count.
    first, second = block("Retake waiting period: 14 days"), block("Retake fee: full price")
    blocks = two_sections(first, second, ("Retakes", "Fees"))
    claim = {"text": "A retake costs the full exam fee", "attribute": "retake_fee"}
    section = select_section(blocks, value="full exam fee", weights=SMALL, **claim)
    assert section.heading == "Fees"


def test_subject_words_in_a_heading_get_no_bonus():
    # On a page about one subject every heading names it; the attribute decides.
    blocks = [block("Claude exam: how to sign up", "summary"), block("Use the portal."), *FILLER,
              block("Claude exam length", "summary"), block("120 minutes."), *FILLER]  # fmt: skip
    section = select_section(blocks, text="Claude exam duration", subject="Claude exam",
                             attribute="length", weights=SMALL)  # fmt: skip
    assert section.heading == "Claude exam length"


def test_headings_above_count_and_close_at_their_level():
    blocks = [block("Team plan", "h2"), block("Billing", "h3"), block("Monthly fee: $25"),
              *FILLER, block("Enterprise plan", "h2"), block("Billing", "h3"),
              block("Monthly fee: $90"), *FILLER]  # fmt: skip
    section = select_section(blocks, text="Team plan fee", weights=SMALL)
    # "Team plan" has nothing of its own before its h3, so it is only a heading above. The
    # h3's segment is longer than the budget, so it is cut to its best row.
    assert section.core == range(2, 3)  # under "Team plan", not under "Enterprise plan"
    assert (section.score, section.runner_up) == (3.0, 2.0)  # team, plan, fee / plan, fee


def test_navigation_words_count_at_the_chrome_weight():
    nav = ("header", "nav")
    blocks = [block("Team plan", "h2", nav), block("fee", "li", nav), block("Team plan", "h2"),
              block("The fee is $25 a month"), *FILLER]  # fmt: skip
    section = select_section(blocks, text="The Team plan fee", weights=SMALL)
    # Main: team, plan, fee, and team, plan again in its heading. Nav: team, plan, fee at
    # half weight, and no heading bonus.
    assert (section.score, section.runner_up) == (5.0, 1.5)
    assert section.core == range(3, 4)  # the main segment, cut to its row
    even = select_section(blocks, text="The Team plan fee", weights=Weights(budget=200, chrome=1))
    assert (even.score, even.runner_up) == (5.0, 3.0)


def test_growth_alternates_sides_and_stops_at_navigation():
    blocks = [block(f"row {i:02} " + "z" * 15) for i in range(12)]  # 22 characters each
    blocks[5] = block("Team plan fee: $25 ...", "h2")
    blocks[11] = block("Footer links " + "z" * 9, "li", ("footer",))
    section = select_section(blocks, text="Team plan fee", weights=Weights(budget=159))
    assert section.core == range(5, 11)  # the heading's segment, without the footer: 137
    assert section.blocks == range(5, 11)  # characters; one more block would not fit
    section = select_section(blocks, text="Team plan fee", weights=Weights(budget=183))
    assert section.blocks == range(3, 11)  # before, after is the footer, before again
    check_offsets(blocks, section)
    blocks[9] = block("Other plans", "h2")  # the segment is now 5-8, with room on both sides
    section = select_section(blocks, text="Team plan fee", weights=Weights(budget=114))
    assert (section.core, section.blocks) == (range(5, 9), range(4, 9))  # room for one: before


def test_a_long_segment_is_cut_to_its_best_row():
    rows = [block(f"Row {i}: nothing here " + "y" * 40) for i in range(40)]
    rows[30] = block("Row 30: Team plan fee $25")
    blocks = [block("Team plan fees", "h2"), *rows]  # the heading names the claim too
    section = select_section(blocks, text="Team plan fee", weights=Weights(budget=300))
    assert section.core == range(31, 32) and len(section.text) <= 300
    assert section.heading == "Team plan fees"
    check_offsets(blocks, section)


def test_a_block_longer_than_the_budget_is_cut_to_a_window():
    long_text = " ".join(["filler words"] * 200 + ["Team plan fee is $25"] + ["more"] * 200)
    blocks = [block("Plans", "h2"), block(long_text), *FILLER]
    section = select_section(blocks, text="Team plan fee", weights=SMALL)
    assert "Team plan fee is $25" in section.text and len(section.text) <= 200
    assert section.core == section.blocks == range(1, 2)
    check_offsets(blocks, section)


def test_a_korean_claim_finds_its_section():
    blocks = [block("Chatbox 소개", "h2"), block("대화형 도우미입니다. " * 10), *FILLER,
              block("요금", "h2"), block("Pro 요금은 월 9,900원입니다."), *FILLER]  # fmt: skip
    section = select_section(blocks, text="Chatbox의 가격은 월 9,900원", subject="Chatbox",
                             attribute="가격", value="월 9,900원", weights=SMALL)  # fmt: skip
    assert section.heading == "요금"  # 가격 and 요금 are synonyms


def test_selection_does_not_depend_on_the_hash_seed():
    # The two segments tie at 0.6: 0.3 + 0.3 against 0.3 + 0.2 + 0.1. Summed in set order,
    # the second is 0.6000000000000001 under some hash seeds and wins. Python 3.12+ sums
    # floats more exactly, so the 3.11 CI job is the one that catches this.
    script = """
from shelflife.verifiers.section import Weights, select_section
from shelflife.verifiers.web_page import Block
pad = [Block("filler " * 30, "p", ()) for _ in range(6)]
blocks = [Block("Part one", "h2", ()), Block("delta omega", "p", ()), *pad,
          Block("Part two", "h2", ()), Block("alpha beta gamma", "p", ()), *pad]
weights = Weights(subject=0.3, attribute=0.2, text=0.1, heading=0, budget=600)
s = select_section(blocks, text="alpha beta gamma delta omega", subject="alpha delta omega",
                   attribute="beta", weights=weights)
print(s.heading, repr(s.score), repr(s.runner_up))
"""
    runs = {
        subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": str(seed)},
        ).stdout  # fmt: skip
        for seed in range(8)
    }
    assert runs == {"Part one 0.6 0.6\n"}

"""Section selection: the part of a long page that a web_page claim is about (design 5.3).

The selector is plain code, so it is deterministic: the same page and claim always give the
same section, which is what M4's section hash needs (D10). It reports where the section is
and how it scored, so the 6.2 eval can tell a selection miss from a judgment miss. Its
weights are parameters, so 6.2 can change one at a time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shelflife.verifiers.web_page import Block, normalize

SELECTOR_VERSION = "s1"

# Heading rank: h1-h6, then <summary> (an FAQ question) and <dt> (a term) below them.
HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6, "summary": 7, "dt": 7}
CHROME = frozenset({"nav", "header", "footer", "aside"})
# Words a claim and a page use for the same attribute. Kept small: each entry is a guess
# that 6.2 can measure.
SYNONYMS = [frozenset("fee fees cost price pricing 가격 비용 요금 응시료".split())]
STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or per than that the "
    "this to was were with".split()
)
WORD = re.compile(r"[^\W_]+")
SCRIPT_BOUNDARY = re.compile(r"(?<=[가-힣])(?=[^가-힣])|(?<=[^가-힣])(?=[가-힣])")


@dataclass(frozen=True)
class Weights:
    subject: float = 2.0
    attribute: float = 2.0
    text: float = 1.0
    heading: float = 1.0  # added again for words in the segment's own heading
    chrome: float = 0.5  # a segment entirely inside nav, header, footer or aside
    budget: int = 3000  # characters; a page this short is returned whole


WEIGHTS = Weights()


@dataclass(frozen=True)
class Section:
    text: str  # the section's blocks, one per line
    heading: str | None  # the heading the section's best segment sits under
    start: int  # offsets into normalize(page_text(blocks)) of the whole page
    end: int
    blocks: range  # indexes of the section's blocks
    score: float  # the best segment's score
    runner_up: float  # the next best segment's score: a small margin means ambiguous
    value_found: bool  # whether the claim's value terms all appear in the section
    version: str = SELECTOR_VERSION


def terms(text: str | None) -> set[str]:
    """Search terms: lower-case words, Hangul split from other scripts, stop words and
    one-letter words dropped."""
    if not text:
        return set()
    words = WORD.findall(SCRIPT_BOUNDARY.sub(" ", text.casefold()))
    return {w for w in words if w not in STOPWORDS and (len(w) > 1 or "가" <= w <= "힣")}


def select_section(
    blocks: list[Block],
    *,
    text: str,
    subject: str | None = None,
    attribute: str | None = None,
    value: str | None = None,
    weights: Weights = WEIGHTS,
) -> Section:
    """The part of the page the claim is about.

    A page within the budget is returned whole. Otherwise the page is cut into segments,
    each a heading and the blocks up to the next heading. A segment scores the weights of
    the distinct claim words found in it or in the headings above it, plus those found in
    its own heading again: subject and attribute words weigh most, the claim's other
    words less. The claim's value only
    breaks ties, so a page where the value changed still finds the same segment. The best
    segment then grows into its neighbours, one block at a time on alternate sides, up to
    the budget; a segment longer than the budget is cut around its best block.
    """
    lengths = [len(b.text) + 1 for b in blocks]  # +1: the space normalize() joins them with
    if sum(lengths) - 1 <= weights.budget or not blocks:
        return _section(blocks, range(len(blocks)), None, 0.0, 0.0, value)

    value_terms = terms(value)
    wanted = _weighted_terms(text, subject, attribute, weights, exclude=value_terms)
    segments = _segments(blocks)
    ranked = sorted(
        (
            (_score(blocks, seg, path, wanted, weights), _found(blocks, seg, value_terms), -i)
            for i, (seg, path) in enumerate(segments)
        ),
        reverse=True,
    )
    (score, _, neg_i), runner_up = ranked[0], ranked[1][0] if len(ranked) > 1 else 0.0
    seg, path = segments[-neg_i]
    heading = blocks[seg.start].text if blocks[seg.start].tag in HEADING_LEVELS else None
    if heading is None and path:
        heading = blocks[path[-1]].text
    if sum(lengths[i] for i in seg) - 1 > weights.budget:  # cut around its best block
        path = (*path, seg.start)
        _, _, neg_j = max(
            (
                _score(blocks, range(j, j + 1), path, wanted, weights),
                _found(blocks, range(j, j + 1), value_terms),
                -j,
            )
            for j in seg
        )
        seg = range(-neg_j, -neg_j + 1)
    return _section(blocks, _grow(seg, lengths, weights.budget), heading, score, runner_up, value)


def _weighted_terms(
    text: str, subject: str | None, attribute: str | None, weights: Weights, exclude: set[str]
) -> dict[str, float]:
    """Claim words and their weights, without the value's words ("$125" in "the fee is
    $125"), which only break ties."""
    wanted: dict[str, float] = {}
    for words, weight in (
        (terms(text), weights.text),
        (terms(attribute and attribute.replace("_", " ")), weights.attribute),
        (terms(subject), weights.subject),
    ):
        for word in words - exclude:
            wanted[word] = max(wanted.get(word, 0.0), weight)
    return wanted


def _matches(word: str, text: str) -> bool:
    """A word matches if it, a synonym, or (for long words) its first six letters appear
    in the text, so "certification" finds "certified" and "fee" finds "cost"."""
    group = next((g for g in SYNONYMS if word in g), {word})
    return any((w[:6] if len(w) > 6 else w) in text for w in group)


def _segments(blocks: list[Block]) -> list[tuple[range, tuple[int, ...]]]:
    """(block range, indexes of the headings above it) for each heading's segment."""
    segments: list[tuple[range, tuple[int, ...]]] = []
    open_headings: list[int] = []  # outermost first
    start, above = 0, ()
    for i, block in enumerate(blocks):
        level = HEADING_LEVELS.get(block.tag)
        if level is None:
            continue
        if i > start:
            segments.append((range(start, i), above))
        while open_headings and HEADING_LEVELS[blocks[open_headings[-1]].tag] >= level:
            open_headings.pop()
        above = tuple(open_headings)
        open_headings.append(i)
        start = i
    segments.append((range(start, len(blocks)), above))
    return segments


def _score(
    blocks: list[Block],
    seg: range,
    path: tuple[int, ...],
    wanted: dict[str, float],
    weights: Weights,
) -> float:
    haystack = " ".join(blocks[i].text for i in (*path, *seg)).casefold()
    score = sum(weight for word, weight in wanted.items() if _matches(word, haystack))
    if blocks[seg.start].tag in HEADING_LEVELS:  # a heading names what its segment is about
        own = blocks[seg.start].text.casefold()
        score += weights.heading * sum(w for word, w in wanted.items() if _matches(word, own))
    if all(CHROME & set(blocks[i].landmarks) for i in seg):
        score *= weights.chrome
    return score


def _found(blocks: list[Block], seg: range, value_terms: set[str]) -> int:
    haystack = " ".join(blocks[i].text for i in seg).casefold()
    return sum(word in haystack for word in value_terms)


def _grow(seg: range, lengths: list[int], budget: int) -> range:
    """The segment, grown by whole blocks on alternate sides (before first) while it fits.
    One block is always kept, even if it alone is longer than the budget."""
    lo, hi = seg.start, seg.stop
    size = sum(lengths[i] for i in seg)
    before = True
    while True:
        grown = False
        for side in (True, False) if before else (False, True):
            if side and lo > 0 and size + lengths[lo - 1] <= budget + 1:
                lo, size, grown = lo - 1, size + lengths[lo - 1], True
                break
            if not side and hi < len(lengths) and size + lengths[hi] <= budget + 1:
                hi, size, grown = hi + 1, size + lengths[hi], True
                break
        if not grown:
            return range(lo, hi)
        before = not before


def _section(
    blocks: list[Block],
    chosen: range,
    heading: str | None,
    score: float,
    runner_up: float,
    value: str | None,
) -> Section:
    start = sum(len(blocks[i].text) + 1 for i in range(chosen.start))
    text = "\n".join(blocks[i].text for i in chosen)
    value_terms = terms(value)
    found = bool(value_terms) and all(w in text.casefold() for w in value_terms)
    return Section(
        text=text,
        heading=heading,
        start=start,
        end=start + len(normalize(text)),
        blocks=chosen,
        score=score,
        runner_up=runner_up,
        value_found=found,
    )

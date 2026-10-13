"""Section selection: the part of a long page that a web_page claim is about (design 5.3).

The selector is plain code, so the same page and claim always give the same section, which
M4 hashes (D10). It reports where the section is and how it scored, so the 6.2 eval can
tell a selection miss from a judgment miss, and its weights are parameters 6.2 can vary
one at a time.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from shelflife.store import PARTICLES
from shelflife.verifiers.web_page import Block

SELECTOR_VERSION = "s1"

# Heading rank: h1-h6, then <summary> (an FAQ question) and <dt> (a term) below them.
HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6, "summary": 7, "dt": 7}
CHROME = frozenset({"nav", "header", "footer", "aside"})
# Words a claim and a page use for the same attribute. Kept small: each one is a guess
# that 6.2 can measure.
SYNONYMS = [frozenset("fee fees cost price pricing 가격 비용 요금 응시료".split())]
STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or per than that the "
    "this to was were with".split()
)
# A word: a number with its separators ("9,900", "v2.3.0"), else a run of letters and digits.
WORD = re.compile(r"[^\W\d_]*\d+(?:[.,]\d+)+|[^\W_]+")
HANGUL = re.compile(r"[가-힣]+")
SCRIPT_RUNS = re.compile(r"[가-힣]+|[^가-힣]+")


@dataclass(frozen=True)
class Weights:
    subject: float = 2.0
    attribute: float = 2.0
    text: float = 1.0
    heading: float = 1.0  # attribute and text words in a segment's own heading count again
    chrome: float = 0.5  # a word found only in nav, header, footer or aside
    budget: int = 3000  # characters; a page this short is returned whole


WEIGHTS = Weights()


@dataclass(frozen=True)
class Section:
    text: str  # the section's blocks, one per line (or a window of one long block)
    heading: str | None  # the heading the best segment sits under
    start: int  # offsets of the text in normalize(page_text(blocks)), the whole page
    end: int
    blocks: range  # the blocks the section shows
    core: range  # the best segment (or row) before it grew into its neighbours
    score: float  # the best segment's score
    runner_up: float  # the next best segment's: a small margin means an ambiguous page
    version: str = SELECTOR_VERSION


def terms(text: str | None) -> set[str]:
    """Search terms: lower-case words and numbers, stop words and one-letter words dropped.

    A word that mixes Hangul with other letters is split where the scripts meet, and a
    Hangul part that is a particle is dropped, as recall does (D8): "Chatbox의" gives
    "chatbox"."""
    found: set[str] = set()
    for word in WORD.findall((text or "").casefold()):
        parts = SCRIPT_RUNS.findall(word) if HANGUL.search(word) else [word]
        if len(parts) > 1:
            parts = [p for p in parts if p not in PARTICLES]
        found.update(p for p in parts if p not in STOPWORDS and _long_enough(p))
    return found


def _long_enough(word: str) -> bool:
    return len(word) > 1 or not word.isalpha() or HANGUL.match(word) is not None


def _pattern(word: str) -> re.Pattern[str]:
    """How a claim word is found in page text (both lower case).

    Hangul matches anywhere, since particles attach to words. A number must not be part of
    a longer number, but a unit may follow it ("9,900원"). A word of three letters or
    fewer, and a synonym, must be a whole word ("fee" is not "feedback", "cost"
    is not "cost-effective"). A longer word must start a word, and one of seven letters or
    more matches by its first six ("certification" finds "certified")."""
    group = next((g for g in SYNONYMS if word in g), None)
    if group is not None:
        return re.compile("|".join(_pattern_one(w, synonym=True) for w in sorted(group)))
    return re.compile(_pattern_one(word, synonym=False))


def _pattern_one(word: str, synonym: bool) -> str:
    if HANGUL.match(word):
        return re.escape(word)
    if any(c.isdigit() for c in word):
        return rf"(?<![\w.,]){re.escape(word)}(?![\d]|[.,]\d)"  # "9,900원", not "19,900"
    if synonym:
        return rf"(?<!\w){re.escape(word)}(?![\w-])"
    if len(word) <= 3:
        return rf"(?<!\w){re.escape(word)}(?!\w)"
    return rf"(?<!\w){re.escape(word[:6])}"


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

    A page within the budget is returned whole. Otherwise each heading starts a segment
    that runs to the next heading. A segment scores the weights of the distinct claim
    words found in it or in the headings above it; subject and attribute words weigh
    most, the claim's other words less, and a word found only in nav, header, footer or
    aside counts at the chrome weight. Attribute and other words in the segment's own
    heading count again; subject words do not, because on a page about one subject every
    heading repeats them. The value's words are not scored: they only break ties, so a
    page whose value changed still finds the same segment. Then the earlier segment wins.

    A segment longer than the budget is cut to its best row, and a row longer than the
    budget to a window around its first match. The result then grows by whole blocks on
    alternate sides, before first, up to the budget, but not into nav, header, footer or
    aside.
    """
    lengths = [len(b.text) + 1 for b in blocks]  # +1: the space normalize() joins them with
    if sum(lengths) - 1 <= weights.budget:
        everything = range(len(blocks))
        return _section(blocks, everything, everything, None, 0.0, 0.0)

    lower = [b.text.casefold() for b in blocks]
    subject_words = terms(subject)
    attribute_words = terms(attribute and attribute.replace("_", " "))
    value_words = terms(value)
    wanted = {w: weights.text for w in terms(text) - value_words}
    wanted |= {w: weights.attribute for w in attribute_words}
    wanted |= {w: max(wanted.get(w, 0.0), weights.subject) for w in subject_words}
    patterns = {w: _pattern(w) for w in sorted(wanted)}
    value_patterns = [_pattern(w) for w in sorted(value_words)]
    heading_words = set(wanted) - subject_words

    chrome = [bool(CHROME & set(b.landmarks)) for b in blocks]

    def found(indexes: tuple[int, ...] | range, words: set[str] | None = None) -> set[str]:
        text = " ".join(lower[i] for i in indexes)
        return {w for w, p in patterns.items() if (words is None or w in words) and p.search(text)}

    def weigh(words: set[str]) -> float:
        return math.fsum(wanted[w] for w in sorted(words))

    def score(seg: range, above: tuple[int, ...]) -> float:
        main = found(tuple(i for i in (*above, *seg) if not chrome[i]))
        side = found(tuple(i for i in (*above, *seg) if chrome[i])) - main
        total = weigh(main) + weights.chrome * weigh(side)
        if blocks[seg.start].tag in HEADING_LEVELS and not chrome[seg.start]:
            total += weights.heading * weigh(found((seg.start,), heading_words))
        return total

    def value_hits(seg: range) -> int:
        joined = " ".join(lower[i] for i in seg)
        return sum(bool(p.search(joined)) for p in value_patterns)

    segments = _segments(blocks, chrome)
    ranked = sorted(
        ((score(seg, above), value_hits(seg), -i) for i, (seg, above) in enumerate(segments)),
        reverse=True,
    )
    (best, _, neg_i), runner_up = ranked[0], ranked[1][0] if len(ranked) > 1 else 0.0
    seg, above = segments[-neg_i]
    is_heading = blocks[seg.start].tag in HEADING_LEVELS
    heading = blocks[seg.start].text if is_heading else (blocks[above[-1]].text if above else None)

    core = seg
    if sum(lengths[i] for i in seg) - 1 > weights.budget:  # cut to its best row
        rows = range(seg.start + 1, seg.stop) if is_heading and len(seg) > 1 else seg
        _, _, neg_j = max(
            (score(range(j, j + 1), ()), value_hits(range(j, j + 1)), -j) for j in rows
        )
        core = range(-neg_j, -neg_j + 1)
    if len(core) == 1 and lengths[core.start] - 1 > weights.budget:  # cut inside the row
        return _window(blocks, core.start, patterns, wanted, heading, best, runner_up, weights)
    shown = _grow(core, lengths, blocks, weights.budget)
    return _section(blocks, shown, core, heading, best, runner_up)


def _segments(blocks: list[Block], chrome: list[bool]) -> list[tuple[range, tuple[int, ...]]]:
    """(block range, indexes of the headings above it) for each segment.

    A segment starts at each heading, and where nav, header, footer or aside starts or
    ends, so page chrome never joins a content segment. A heading with nothing under it
    before the next heading is not a segment of its own; it stays a heading above.
    """
    segments: list[tuple[range, tuple[int, ...]]] = []
    open_headings: list[int] = []  # outermost first
    start, above = 0, ()
    for i, block in enumerate(blocks):
        level = HEADING_LEVELS.get(block.tag)
        if level is None and (i == 0 or chrome[i] == chrome[i - 1]):
            continue
        bare = i - start == 1 and blocks[start].tag in HEADING_LEVELS
        if i > start and not bare:
            segments.append((range(start, i), above))
        if level is not None:
            while open_headings and HEADING_LEVELS[blocks[open_headings[-1]].tag] >= level:
                open_headings.pop()
            above = tuple(open_headings)
            open_headings.append(i)
        else:
            above = tuple(open_headings)
        start = i
    segments.append((range(start, len(blocks)), above))
    return segments


def _grow(core: range, lengths: list[int], blocks: list[Block], budget: int) -> range:
    """The core, grown by whole blocks on alternate sides (before first) while it fits.
    Growth on a side stops at a block that does not fit or sits in nav, header, footer
    or aside."""
    lo, hi = core.start, core.stop
    size = sum(lengths[i] for i in core)
    open_sides = {"before", "after"}
    side = "before"
    while open_sides:
        if side not in open_sides:
            side = next(iter(open_sides))
        i = lo - 1 if side == "before" else hi
        fits = 0 <= i < len(blocks) and size + lengths[i] <= budget + 1
        if fits and not CHROME & set(blocks[i].landmarks):
            size += lengths[i]
            lo, hi = (i, hi) if side == "before" else (lo, i + 1)
            side = "after" if side == "before" else "before"
        else:
            open_sides.discard(side)
    return range(lo, hi)


def _window(
    blocks: list[Block],
    index: int,
    patterns: dict[str, re.Pattern[str]],
    wanted: dict[str, float],
    heading: str | None,
    best: float,
    runner_up: float,
    weights: Weights,
) -> Section:
    """A window of one block longer than the budget, around the first match of its
    heaviest claim word, cut at spaces."""
    text = blocks[index].text
    lower = text.casefold()
    hits = sorted((-wanted[w], m.start()) for w, p in patterns.items() if (m := p.search(lower)))
    at = hits[0][1] if hits else 0
    lo = max(0, at - weights.budget // 2)
    if lo > 0 and text[lo - 1] != " ":
        lo = text.find(" ", lo) + 1 or at  # start at the next word
    hi = min(len(text), lo + weights.budget)
    if hi < len(text) and text[hi] != " ":
        hi = max(text.rfind(" ", lo, hi), lo + 1)  # end before a cut word
    window = text[lo:hi].strip()
    offset = sum(len(b.text) + 1 for b in blocks[:index]) + lo
    return Section(
        text=window,
        heading=heading,
        start=offset,
        end=offset + len(window),
        blocks=range(index, index + 1),
        core=range(index, index + 1),
        score=best,
        runner_up=runner_up,
    )


def _section(
    blocks: list[Block],
    shown: range,
    core: range,
    heading: str | None,
    best: float,
    runner_up: float,
) -> Section:
    start = sum(len(blocks[i].text) + 1 for i in range(shown.start))
    text = "\n".join(blocks[i].text for i in shown)
    return Section(
        text=text,
        heading=heading,
        start=start,
        end=start + len(text),  # the same length once "\n" becomes " "
        blocks=shown,
        core=core,
        score=best,
        runner_up=runner_up,
    )

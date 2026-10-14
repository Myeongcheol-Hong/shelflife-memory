"""The 6.1 replay (M6, D12): claims about a project's latest version, questions about
them, and the policies that decide when to check them.

Ground truth is changes() over the collected timelines (D11). A day's checks and
questions see the state at the end of that day, and checks run first. Every random draw
is a random() call on a stream tied to (seed, split, project, claim), so every policy
faces the same claims and questions, and a run repeats exactly on any Python version.
"""

from __future__ import annotations

import hashlib
import random
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Callable
from dataclasses import astuple, dataclass
from datetime import date, timedelta

from eval.replay.timelines import DEV, LABELS, TEST, Timeline, changes, latest_on
from shelflife.models import Volatility
from shelflife.scheduler import next_check_at

SPLITS = {"dev": DEV, "test": TEST}
CLAIMS_PER_PROJECT = 20
QUESTION_RATES = {"2 a month": 2 / 30, "1 a week": 1 / 7, "1 a day": 1.0}  # per claim-day
FIXED = (3, 7, 14, 30, 60, 90, 180)  # days, for the fixed-interval curve


@dataclass(frozen=True)
class Truth:
    """One project's latest version on any day of a split, from changes()."""

    days: tuple[date, ...]  # the days the latest changed, ascending
    values: tuple[str | None, ...]  # the latest from each of those days on
    before: str | None  # the latest on the day before the split

    def on(self, day: date) -> str | None:
        i = bisect_right(self.days, day)
        return self.values[i - 1] if i else self.before

    def change_after(self, day: date) -> date | None:
        """The first day after `day` the latest changed."""
        i = bisect_right(self.days, day)
        return self.days[i] if i < len(self.days) else None


def truth(timeline: Timeline, split: str) -> Truth:
    start, end = SPLITS[split]
    found = changes(timeline, start, end)
    before = latest_on(timeline, start - timedelta(days=1))
    return Truth(tuple(d for d, _ in found), tuple(v for _, v in found), before)


def first_day(truth: Truth, split: str) -> date | None:
    """The first day of the split the project has a latest version, or None."""
    if truth.before is not None:
        return SPLITS[split][0]
    return truth.days[0] if truth.days else None


@dataclass(frozen=True)
class Claim:
    project: str
    label: str  # the maintainer's volatility label
    created: date  # it claims the latest of this day; checks and questions come after
    end: date  # the split's last day, when the claim stops
    questions: tuple[date, ...]


def stream(*parts: object) -> random.Random:
    """The random stream of one draw site. sha256 of the parts, never hash(): hash() of a
    string changes from one Python process to the next."""
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def claims(
    project: str, label: str, truth: Truth, split: str, seed: int, rate: float
) -> list[Claim]:
    """CLAIMS_PER_PROJECT claims, each created on a uniform random day from the project's
    first day with a latest to the day before the split ends (D12). On each later day a
    question comes with probability `rate`; a draw per day keeps every draw on random()."""
    end, first = SPLITS[split][1], first_day(truth, split)
    if first is None or first >= end:
        return []
    out = []
    for i in range(CLAIMS_PER_PROJECT):
        rng = stream(seed, split, project, i)
        created = first + timedelta(days=int(rng.random() * (end - first).days))
        days = (created + timedelta(days=k) for k in range(1, (end - created).days + 1))
        out.append(
            Claim(project, label, created, end, tuple(d for d in days if rng.random() < rate))
        )
    return out


# A policy gives the days it checks a claim, ascending, after its creation and up to its
# end. No check depends on what an earlier one found: after same or changed the next is
# the check day plus the interval (D9), and the replay's verifier is always right.
Policy = Callable[[Claim, Truth, random.Random], list[date]]


def never(claim: Claim, truth: Truth, rng: random.Random) -> list[date]:
    return []


def every_read(claim: Claim, truth: Truth, rng: random.Random) -> list[date]:
    return sorted(set(claim.questions))


def oracle(claim: Claim, truth: Truth, rng: random.Random) -> list[date]:
    """A check on each day the latest changed: the lower bound on cost and staleness."""
    return changes_in(claim, truth)


def changes_in(claim: Claim, truth: Truth) -> list[date]:
    """The days the latest changed while the claim lived."""
    return list(
        truth.days[bisect_right(truth.days, claim.created) : bisect_right(truth.days, claim.end)]
    )


def interval(days: int | None, jitter: bool = False) -> Policy:
    """A check every `days` days, or with None every class interval of the claim's label
    (scheduler.next_check_at(), design 4.2), counted from the creation and then from each
    check (D9). With jitter, each check moves by a whole number of days drawn from -j..j,
    where j is a tenth of that interval rounded half up (D12)."""

    def policy(claim: Claim, truth: Truth, rng: random.Random) -> list[date]:
        out, day = [], claim.created
        while True:
            if days is None:
                nxt = next_check_at(Volatility(claim.label), day)
                assert nxt is not None  # labels are fast, medium or slow: never None
            else:
                nxt = day + timedelta(days=days)
            if jitter:
                j = ((nxt - day).days + 5) // 10
                nxt += timedelta(days=int(rng.random() * (2 * j + 1)) - j)
            if nxt > claim.end:
                return out
            out.append(nxt)
            day = nxt

    return policy


POLICIES: dict[str, Policy] = {"never": never, "every read": every_read, "oracle": oracle}
POLICIES |= {f"fixed {n}": interval(n) for n in FIXED}
POLICIES["per-class"] = interval(None)
POLICIES |= {
    f"{name} + jitter": interval(n, jitter=True)
    for name, n in (("per-class", None), ("fixed 7", 7), ("fixed 30", 30))
}


@dataclass
class Counts:
    """What a claim, or the claims summed, gave under one policy."""

    claims: float = 0
    questions: float = 0
    stale_answers: float = 0
    days: float = 0  # claim-days: each day after the creation to the end
    stale_days: float = 0  # claim-days on which the stored value was not the latest
    checks: float = 0
    detected: float = 0  # changes of the latest a check found while the claim lived
    delay_days: float = 0  # over the detected: days from the change to the check
    undetected: float = 0  # changes no check found before the claim ended (censored)

    def __add__(self, other: Counts) -> Counts:
        return Counts(*(a + b for a, b in zip(astuple(self), astuple(other), strict=True)))


def outcome(claim: Claim, truth: Truth, checks: list[date]) -> Counts:
    """The claim's counts when checked on `checks`. A check adopts the latest of its day.
    The latest never returns to an earlier value (D12), so the stored value is stale on a
    day exactly when the latest changed since the creation or the last check."""
    anchors = [claim.created, *checks]
    c = Counts(claims=1, days=(claim.end - claim.created).days, checks=len(checks))
    for k, anchor in enumerate(anchors):
        until = anchors[k + 1] - timedelta(days=1) if k + 1 < len(anchors) else claim.end
        if (x := truth.change_after(anchor)) is not None and x <= until:
            c.stale_days += (until - x).days + 1
    for q in claim.questions:
        x = truth.change_after(anchors[bisect_right(anchors, q) - 1])
        c.questions += 1
        c.stale_answers += x is not None and x <= q
    for x in changes_in(claim, truth):
        if (i := bisect_left(checks, x)) < len(checks):
            c.detected += 1
            c.delay_days += (checks[i] - x).days
        else:
            c.undetected += 1
    return c


@dataclass(frozen=True)
class Row:
    """One project's claims under one policy for one seed."""

    seed: int
    project: str
    policy: str
    counts: Counts
    daily: Counter[date]  # checks per day


def replay(
    timelines: list[Timeline],
    labels: dict[str, str],
    split: str,
    seeds: list[int],
    rate: float,
    policies: dict[str, Policy] = POLICIES,
) -> list[Row]:
    """Every policy over every project's claims, for each seed. `labels` maps a project to
    the maintainer's volatility label; a project without one is refused."""
    if missing := [t.project for t in timelines if labels.get(t.project) not in LABELS]:
        raise ValueError(f"no volatility label for {missing[:3]}")
    rows = []
    for t in timelines:
        tr = truth(t, split)
        for seed in seeds:
            cs = claims(t.project, labels[t.project], tr, split, seed, rate)
            for name, policy in policies.items():
                counts, daily = Counts(), Counter()
                for i, claim in enumerate(cs):
                    checks = policy(claim, tr, stream(seed, split, t.project, i, name))
                    counts += outcome(claim, tr, checks)
                    daily.update(checks)
                rows.append(Row(seed, t.project, name, counts, daily))
    return rows

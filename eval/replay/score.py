"""Metrics and intervals for the 6.1 replay (M6, D12), from replay() rows alone."""

from __future__ import annotations

import functools
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from statistics import fmean

from eval.replay.replay import SPLITS, Counts, Row, stream

# Each metric is a ratio of summed counts: (numerator, denominator) of one claim or a sum.
METRICS: dict[str, Callable[[Counts], tuple[float, float]]] = {
    "stale-answer rate": lambda c: (c.stale_answers, c.questions),
    "stale claim-days": lambda c: (c.stale_days, c.days),
    "checks per claim-month": lambda c: (30 * c.checks, c.days),
    # Right-censored: a change late in a claim's life counts only if found quickly, which
    # flatters long intervals. Always reported with the undetected share (D12).
    "mean days to detect": lambda c: (c.delay_days, c.detected),
    "undetected share": lambda c: (c.undetected, c.detected + c.undetected),
}
RESAMPLES = 2000


def value(metric: str, counts: Counts) -> float | None:
    num, den = METRICS[metric](counts)
    return num / den if den else None


def per_project(rows: list[Row], policy: str) -> dict[str, Counts]:
    """Each project's counts under one policy, averaged over the seeds (D12)."""
    by: defaultdict[str, list[Counts]] = defaultdict(list)
    for r in rows:
        if r.policy == policy:
            by[r.project].append(r.counts)
    mean = {
        p: Counts(*(sum(x) / len(cs) for x in zip(*(vars(c).values() for c in cs), strict=True)))
        for p, cs in by.items()
    }
    return {p: c for p, c in mean.items() if c.claims}  # no claim in the split: not a unit


def total(projects: dict[str, Counts]) -> Counts:
    return sum(projects.values(), Counts())


def ci(
    metric: str, projects: dict[str, Counts], minus: dict[str, Counts] | None = None
) -> tuple[float, float] | None:
    """The 95% percentile interval of a metric, or of its paired difference from the same
    projects under another policy (`minus`), over RESAMPLES resamples of whole projects;
    each ratio is taken from the summed counts. It covers project sampling: claims about
    one project share its timeline, so projects, not claims, are the units (D12)."""
    names = sorted(projects)
    a = [METRICS[metric](projects[p]) for p in names]
    b = [METRICS[metric](minus[p]) for p in names] if minus is not None else None
    found = []
    for pick in _resamples(len(names)):
        v = _ratio(a, pick)
        if b is not None and v is not None:
            w = _ratio(b, pick)
            v = None if w is None else v - w
        if v is not None:
            found.append(v)
    return percentiles(found) if found else None


def percentiles(values: list[float]) -> tuple[float, float]:
    """The 2.5th and 97.5th percentiles by nearest rank."""
    values = sorted(values)
    return values[math.ceil(0.025 * len(values)) - 1], values[math.ceil(0.975 * len(values)) - 1]


def peak(rows: list[Row], policy: str, split: str) -> tuple[float, float]:
    """The busiest day's checks, all projects together, and that peak over the mean day's,
    each averaged over the seeds. The peak is taken per seed, before averaging: averaging
    the days over seeds first would erase the clusters it measures."""
    start, end = SPLITS[split]
    days = (end - start).days + 1
    by_seed: defaultdict[int, Counter] = defaultdict(Counter)
    for r in rows:
        if r.policy == policy:
            by_seed[r.seed].update(r.daily)
    peaks = [max(c.values(), default=0) for c in by_seed.values()]
    ratios = [max(c.values()) * days / c.total() if c.total() else 0.0 for c in by_seed.values()]
    return fmean(peaks), fmean(ratios)


def peak_ci(
    rows: list[Row], policy: str, split: str, minus: str | None = None
) -> tuple[float, float]:
    """The 95% interval of peak(), or of its paired difference from another policy, over
    the same resamples of whole projects as ci(); the peak is taken per seed each time."""
    names = sorted(per_project(rows, policy))
    a = _daily(rows, policy, split)
    b = _daily(rows, minus, split) if minus is not None else None
    if b is not None and not b:
        raise ValueError(f"no rows for {minus!r}")
    found = []
    for pick in _resamples(len(names)):
        chosen = [names[i] for i in pick]
        found.append(_peak(a, chosen) - (_peak(b, chosen) if b is not None else 0))
    return percentiles(found)


def _daily(rows: list[Row], policy: str, split: str) -> dict[int, dict[str, list[int]]]:
    """Each seed's checks per day of the split, per project."""
    start, end = SPLITS[split]
    out: defaultdict[int, dict[str, list[int]]] = defaultdict(dict)
    for r in rows:
        if r.policy == policy:
            days = [0] * ((end - start).days + 1)
            for day, n in r.daily.items():
                days[(day - start).days] += n
            out[r.seed][r.project] = days
    return out


def _peak(daily: dict[int, dict[str, list[int]]], chosen: list[str]) -> float:
    return fmean(max(map(sum, zip(*(by[p] for p in chosen), strict=True))) for by in daily.values())


def _resamples(n: int) -> tuple[tuple[int, ...], ...]:
    """RESAMPLES draws of n project indices with replacement, the same for every metric and
    policy, so differences are paired."""
    return _draw(n, RESAMPLES)


@functools.cache
def _draw(n: int, count: int) -> tuple[tuple[int, ...], ...]:
    rng = stream("resample", n)
    return tuple(tuple(int(rng.random() * n) for _ in range(n)) for _ in range(count))


def _ratio(pairs: list[tuple[float, float]], pick: Sequence[int]) -> float | None:
    num = sum(pairs[i][0] for i in pick)
    den = sum(pairs[i][1] for i in pick)
    return num / den if den else None

"""M7's adaptive policy (D12): each claim learns its own change rate from its checks and
schedules the next check from it.

A check says only whether the value changed since the last one, t days before. With a
change rate λ that has probability 1 - e^(-λt), so a claim's checks have the likelihood
∏ (1 - e^(-λt)) over the changed ones times ∏ e^(-λt) over the others (Cho &
Garcia-Molina 2003). λ is the posterior mode under a Gamma(α, α × the label's class
interval) prior, whose mean is one change per class interval, and the next check comes
after -ln(1 - p) / λ days, the interval in which a change has probability p
(Avrachenkov et al. 2020), in whole days from 1 to `cap`.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from datetime import date, timedelta

from eval.replay.replay import Claim, Policy, Truth
from shelflife.models import Volatility
from shelflife.scheduler import DEFAULT_INTERVAL_DAYS

# The dev grid, 30 points (D12): p, then the prior's strength α, then the longest wait.
GRID = [(p, a, cap) for p in (0.05, 0.1, 0.2, 0.3, 0.5) for a in (0.5, 1, 2) for cap in (180, 365)]
LABEL_FREE_DAYS = 30  # the exploratory prior's interval for every claim (D12)
BISECTIONS = 40  # halvings of a bracket [λ, 2λ]: 2^-40 of λ


def name(p: float, alpha: float, cap: int, label_free: bool = False) -> str:
    return f"adaptive p={p:g} a={alpha:g} max={cap}" + (" label-free" if label_free else "")


def rate(alpha: float, beta: float, changed: Counter[int], unchanged: int) -> float:
    """The posterior mode of λ, in changes a day, after checks that found a change after
    t days (`changed`, a count per t) and checks that found none (`unchanged`, their days
    summed). It is 0 while α - 1 plus the changes seen is at most 0. Otherwise it is the
    one root of the score (α - 1) / λ - β - unchanged + Σ t / (e^(λt) - 1), which falls
    from +∞ while positive, so a bisection finds it."""
    if alpha - 1 + sum(changed.values()) <= 0:
        return 0.0

    def score(lam: float) -> float:
        # t / (e^(λt) - 1) is below 1e-300 once λt passes 700, and expm1 would overflow.
        seen = sum(k * t / math.expm1(lam * t) for t, k in changed.items() if lam * t < 700)
        return (alpha - 1) / lam - beta - unchanged + seen

    lo = hi = 1.0
    if score(1.0) > 0:
        while score(hi) > 0:
            lo, hi = hi, hi * 2
    else:
        while score(lo) <= 0:
            lo, hi = lo / 2, lo
    for _ in range(BISECTIONS):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if score(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def wait(p: float, lam: float, cap: int) -> int:
    """Days to the next check: -ln(1 - p) / λ rounded half up, from 1 to `cap`; `cap`
    when λ is 0."""
    if lam == 0:
        return cap
    return max(1, min(cap, math.floor(-math.log1p(-p) / lam + 0.5)))


def policy(p: float, alpha: float, cap: int, label_free: bool = False) -> Policy:
    """The checks of one grid point. With label_free, every claim's prior is centred on
    LABEL_FREE_DAYS instead of its label's class interval (exploratory, D12)."""

    def checks(claim: Claim, truth: Truth, rng: random.Random) -> list[date]:
        days = LABEL_FREE_DAYS if label_free else DEFAULT_INTERVAL_DAYS[Volatility(claim.label)]
        beta = alpha * days
        changed: Counter[int] = Counter()
        unchanged, out, last = 0, [], claim.created
        while True:
            nxt = last + timedelta(wait(p, rate(alpha, beta, changed, unchanged), cap))
            if nxt > claim.end:
                return out
            # What the check sees: whether the latest changed since the last read.
            t = (nxt - last).days
            if (x := truth.change_after(last)) is not None and x <= nxt:
                changed[t] += 1
            else:
                unchanged += t
            out.append(nxt)
            last = nxt

    return checks

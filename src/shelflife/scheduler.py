"""When a claim should be checked next.

M1 has the per-class default from design 4.2; M2 adds the date after a check (D9). Later
milestones add the daily due run, the weekly digest and the replayed policies.
"""

from __future__ import annotations

from datetime import date, timedelta

from shelflife.models import CheckResult, Volatility

DEFAULT_INTERVAL_DAYS: dict[Volatility, int | None] = {
    Volatility.FAST: 7,
    Volatility.MEDIUM: 30,
    Volatility.SLOW: 180,
    Volatility.NONE: None,
}

# After this many error or cannot_tell results in a row, a claim waits a class interval
# before its next try instead of staying due (D9).
INCONCLUSIVE_LIMIT = 3


def next_check_at(volatility: Volatility, observed_at: date) -> date | None:
    """observed_at plus the class interval, or None for claims that are never checked."""
    days = DEFAULT_INTERVAL_DAYS[volatility]
    return None if days is None else observed_at + timedelta(days=days)


def next_check_after(
    volatility: Volatility,
    result: CheckResult,
    checked_on: date,
    scheduled: date | None,
    inconclusive_in_a_row: int,
) -> date | None:
    """next_check_at after a check on `checked_on` (D9).

    same or changed: checked_on plus the class interval. error or cannot_tell: the
    scheduled date stays, so the claim stays due and is tried again, until the
    INCONCLUSIVE_LIMIT-th such result in a row (this one counted), which also moves the
    next check out by the class interval.
    """
    conclusive = result in (CheckResult.SAME, CheckResult.CHANGED)
    if conclusive or inconclusive_in_a_row >= INCONCLUSIVE_LIMIT:
        return next_check_at(volatility, checked_on)
    return scheduled

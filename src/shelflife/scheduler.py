"""When a claim should be checked next.

M1 has only the per-class default from design 4.2. Later milestones add the daily due run,
the weekly digest and the replayed policies.
"""

from __future__ import annotations

from datetime import date, timedelta

from shelflife.models import Volatility

DEFAULT_INTERVAL_DAYS: dict[Volatility, int | None] = {
    Volatility.FAST: 7,
    Volatility.MEDIUM: 30,
    Volatility.SLOW: 180,
    Volatility.NONE: None,
}


def next_check_at(volatility: Volatility, observed_at: date) -> date | None:
    """observed_at plus the class interval, or None for claims that are never checked."""
    days = DEFAULT_INTERVAL_DAYS[volatility]
    return None if days is None else observed_at + timedelta(days=days)

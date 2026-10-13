from datetime import date

import pytest

from shelflife.models import CheckResult, Volatility
from shelflife.scheduler import INCONCLUSIVE_LIMIT, next_check_after, next_check_at


@pytest.mark.parametrize(
    ("volatility", "expected"),
    [
        (Volatility.FAST, date(2026, 10, 15)),
        (Volatility.MEDIUM, date(2026, 11, 7)),
        (Volatility.SLOW, date(2027, 4, 6)),
        (Volatility.NONE, None),
    ],
)
def test_next_check_at_adds_the_class_interval(volatility, expected):
    assert next_check_at(volatility, date(2026, 10, 8)) == expected


CHECKED = date(2026, 10, 12)
SCHEDULED = date(2026, 10, 10)


@pytest.mark.parametrize("result", [CheckResult.SAME, CheckResult.CHANGED])
def test_a_conclusive_check_schedules_one_interval_after_the_check(result):
    assert next_check_after(Volatility.MEDIUM, result, CHECKED, SCHEDULED, 0) == date(2026, 11, 11)


@pytest.mark.parametrize("result", [CheckResult.ERROR, CheckResult.CANNOT_TELL])
def test_an_inconclusive_check_keeps_the_date_until_the_limit(result):
    for in_a_row in range(1, INCONCLUSIVE_LIMIT):
        assert next_check_after(Volatility.FAST, result, CHECKED, SCHEDULED, in_a_row) == SCHEDULED
    after = next_check_after(Volatility.FAST, result, CHECKED, SCHEDULED, INCONCLUSIVE_LIMIT)
    assert after == date(2026, 10, 19)


def test_a_claim_without_an_interval_stays_unscheduled():
    assert next_check_after(Volatility.NONE, CheckResult.SAME, CHECKED, None, 0) is None

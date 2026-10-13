from datetime import date

import pytest

from shelflife.models import Volatility
from shelflife.scheduler import next_check_at


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
